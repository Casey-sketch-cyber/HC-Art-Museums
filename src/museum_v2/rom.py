"""Differentiable 5-zone RC-psychrometric building Reduced-Order Model (Layer A).

Models 5 coupled museum thermal zones matching the Sinergym ``5ZoneAutoDXVAV``
floorplan topology (`SPACE1-1` through `SPACE5-1`), with:
  * Zone air temperature ``T_air`` [deg C] and interior thermal mass ``T_mass`` [deg C]
  * Zone air humidity ratio ``W_air`` [kg_v/kg_da] and hygroscopic moisture buffer ``W_buffer`` [kg_v/kg_da]
  * Relative humidity ``RH_air`` [%] derived via psychrometrics from ``(T_air, W_air)``
  * Symmetric inter-zone partition conduction (``G_inter``) and doorway air exchange (``m_inter``)
  * Schur-eliminated Backward Euler integration (unconditionally stable at dt = 1 h,
    exact discrete conservation of total enthalpy and total water mass when unforced/adiabatic)
  * Disaggregated IdealLoads HVAC model: sensible heating, sensible cooling,
    steam humidification, apparatus-dew-point condensation dehumidification, and supply reheat,
    converted to site electricity, primary energy, and CO2 emissions.

Supports both PyTorch tensors (for ``autograd`` optimization and batched rollouts)
and NumPy arrays cleanly without requiring PyTorch at import time.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import math

import numpy as np
import yaml

try:
    import torch
    import torch.nn.functional as F
except ImportError:  # pragma: no cover - optional runtime dependency
    torch = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]

from .psychro import (
    CP_DRY_AIR_J_KG_K,
    STANDARD_ATM_PRESSURE_PA,
    dew_point_from_w,
    humidity_ratio_from_temp_rh,
    latent_heat_vaporization_j_per_kg,
    rh_from_temp_w,
)

ArrayLike = Any

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[2] / "configs"


def _is_torch(value: Any) -> bool:
    return torch is not None and isinstance(value, torch.Tensor)


def _softplus(x: Any, beta: float) -> Any:
    if _is_torch(x):
        # threshold=20 matches PyTorch default stability while keeping exact derivative
        return F.softplus(x, beta=beta, threshold=20.0)
    bx = np.asarray(x, dtype=np.float64) * beta
    # Numerically stable log(1 + exp(bx)) / beta
    out = np.where(bx > 20.0, bx, np.log1p(np.exp(np.minimum(bx, 20.0))))
    return out / beta


def _smooth_cap(u: Any, cap: Any, eps: Any) -> Any:
    """Smooth monotone C-infinity approximation to min(u, cap) with f(0) == 0."""
    if _is_torch(u):
        diff = u - cap
        root = torch.sqrt(diff * diff + eps * eps)
        root0 = torch.sqrt(cap * cap + eps * eps)
        return 0.5 * (u + cap - root) - 0.5 * (cap - root0)
    u_arr = np.asarray(u, dtype=np.float64)
    diff = u_arr - cap
    root = np.sqrt(diff * diff + eps * eps)
    root0 = np.sqrt(cap * cap + eps * eps)
    return 0.5 * (u_arr + cap - root) - 0.5 * (cap - root0)


def _smooth_pos_diff(a: Any, b: Any, eps: float) -> Any:
    """Smooth approximation to max(a - b, 0) that is identically 0 when a == 0."""
    if _is_torch(a):
        diff = a - b
        t1 = diff + torch.sqrt(diff * diff + eps * eps)
        t0 = -b + torch.sqrt(b * b + eps * eps)
        return 0.5 * (t1 - t0)
    a_arr = np.asarray(a, dtype=np.float64)
    b_arr = np.asarray(b, dtype=np.float64)
    diff = a_arr - b_arr
    t1 = diff + np.sqrt(diff * diff + eps * eps)
    t0 = -b_arr + np.sqrt(b_arr * b_arr + eps * eps)
    return 0.5 * (t1 - t0)


@dataclass(frozen=True)
class BuildingConstants:
    rho_air_kg_m3: float = 1.2041
    cp_air_j_kg_k: float = CP_DRY_AIR_J_KG_K
    solar_to_air_fraction: float = 0.30
    internal_rad_fraction: float = 0.50
    person_sensible_w: float = 75.0
    person_latent_kg_s: float = 1.85e-5


@dataclass(frozen=True)
class EnvelopeConfig:
    u_wall_w_m2_k: float
    u_roof_w_m2_k: float
    u_window_w_m2_k: float
    u_ground_w_m2_k: float
    u_interzone_wall_w_m2_k: float
    window_shgc: float
    infiltration_ach_design: float
    interzone_air_exchange_ach: float
    thermal_mass_multiplier: float = 1.0
    moisture_buffer_multiplier: float = 1.0


@dataclass(frozen=True)
class HVACConfig:
    cop_cooling: float
    eta_heating: float
    eta_reheat: float
    eta_humidification: float
    fan_w_per_w_sensible: float
    coil_approach_dt_c: float
    q_heat_max_w_per_m2: float
    q_cool_max_w_per_m2: float
    m_hum_max_kg_s_per_m2: float
    m_dehum_max_kg_s_per_m2: float
    smooth_beta_t: float
    smooth_beta_w: float
    electricity_primary_factor: float
    electricity_co2_kg_per_kwh: float


@dataclass(frozen=True)
class ZoneConfig:
    name: str
    label: str
    floor_area_m2: float
    volume_m3: float
    ext_wall_opaque_m2: float
    window_area_m2: float
    roof_area_m2: float
    solar_weight: float
    design_people: float
    design_lights_w: float
    design_equip_w: float
    h_am_w_k: float
    c_mass_j_k: float
    m_buffer_kg: float
    tau_buffer_h: float


@dataclass(frozen=True)
class InterzonePartition:
    zone_a: str
    zone_b: str
    area_m2: float


@dataclass(frozen=True)
class MuseumROMConfig:
    schema_version: int
    tier: str
    description: str
    constants: BuildingConstants
    envelope: EnvelopeConfig
    hvac: HVACConfig
    zones: tuple[ZoneConfig, ...]
    interzone_partitions: tuple[InterzonePartition, ...]
    provenance: dict[str, str]

    @property
    def zone_names(self) -> tuple[str, ...]:
        return tuple(z.name for z in self.zones)

    @property
    def n_zones(self) -> int:
        return len(self.zones)

    def zone_index(self, name: str) -> int:
        for idx, z in enumerate(self.zones):
            if z.name == name:
                return idx
        raise KeyError(f"Unknown zone name: {name}")


def load_building_config(path: str | Path) -> MuseumROMConfig:
    """Load a building ROM YAML configuration into validated dataclasses."""
    cfg_path = Path(path)
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Expected mapping in {cfg_path}")

    constants = BuildingConstants(**raw["constants"])
    envelope = EnvelopeConfig(**raw["envelope"])
    hvac = HVACConfig(**raw["hvac"])
    zones = tuple(ZoneConfig(**z) for z in raw["zones"])
    partitions = tuple(
        InterzonePartition(zone_a=p["zones"][0], zone_b=p["zones"][1], area_m2=float(p["area_m2"]))
        for p in raw.get("interzone_partitions", [])
    )
    provenance = {str(k): str(v) for k, v in raw.get("provenance", {}).items()}
    return MuseumROMConfig(
        schema_version=int(raw["schema_version"]),
        tier=str(raw["tier"]),
        description=str(raw.get("description", "")).strip(),
        constants=constants,
        envelope=envelope,
        hvac=hvac,
        zones=zones,
        interzone_partitions=partitions,
        provenance=provenance,
    )


def load_building_tier(tier: str, config_dir: str | Path | None = None) -> MuseumROMConfig:
    """Load one of the standard 3 building tiers ('historic', 'retrofitted', 'modern')."""
    base = Path(config_dir) if config_dir is not None else DEFAULT_CONFIG_DIR
    tier_norm = tier.strip().lower()
    if tier_norm not in {"historic", "retrofitted", "modern"}:
        raise ValueError(f"Unknown building tier '{tier}'. Expected historic, retrofitted, or modern.")
    return load_building_config(base / f"building_{tier_norm}.yaml")


def make_adiabatic_config(base: MuseumROMConfig) -> MuseumROMConfig:
    """Return a copy of ``base`` with zero exterior conduction, zero ground heat loss, and zero infiltration."""
    env = EnvelopeConfig(
        u_wall_w_m2_k=0.0,
        u_roof_w_m2_k=0.0,
        u_window_w_m2_k=0.0,
        u_ground_w_m2_k=0.0,
        u_interzone_wall_w_m2_k=base.envelope.u_interzone_wall_w_m2_k,
        window_shgc=0.0,
        infiltration_ach_design=0.0,
        interzone_air_exchange_ach=base.envelope.interzone_air_exchange_ach,
        thermal_mass_multiplier=base.envelope.thermal_mass_multiplier,
        moisture_buffer_multiplier=base.envelope.moisture_buffer_multiplier,
    )
    return MuseumROMConfig(
        schema_version=base.schema_version,
        tier=f"{base.tier}_adiabatic",
        description=base.description,
        constants=base.constants,
        envelope=env,
        hvac=base.hvac,
        zones=base.zones,
        interzone_partitions=base.interzone_partitions,
        provenance=dict(base.provenance),
    )


_BaseModule = torch.nn.Module if torch is not None else object


def _matvec(mat: Any, vec: Any, use_torch: bool) -> Any:
    if use_torch:
        if mat.ndim == 3 and vec.ndim == 2:
            return torch.bmm(mat, vec.unsqueeze(-1)).squeeze(-1)
        return torch.einsum("...ij,...j->...i", mat, vec)
    return np.einsum("...ij,...j->...i", mat, vec)


def _clamp_min_w(val: Any, min_w: float, use_torch: bool) -> Any:
    if use_torch:
        return torch.clamp(val, min=min_w)
    return np.maximum(val, min_w)


def _zeros_like(val: Any, use_torch: bool) -> Any:
    if use_torch:
        return torch.zeros_like(val)
    return np.zeros_like(val, dtype=np.float64)


if torch is not None:

    @torch.jit.script
    def _torch_smooth_cap(u: torch.Tensor, cap: torch.Tensor, root0: torch.Tensor, eps_sq: float) -> torch.Tensor:
        diff = u - cap
        return 0.5 * (u + cap - torch.sqrt(diff * diff + eps_sq)) - 0.5 * (cap - root0)

    @torch.jit.script
    def _torch_w_from_t_rh(t_c: torch.Tensor, rh_pct: torch.Tensor, pressure_pa: float) -> torch.Tensor:
        t_safe = torch.clamp(t_c, min=-80.0, max=80.0)
        p_ws = 610.94 * torch.exp(17.625 * t_safe / (t_safe + 243.04))
        p_w = torch.clamp((rh_pct / 100.0) * p_ws, min=0.0, max=0.95 * pressure_pa)
        return 0.621945 * p_w / (pressure_pa - p_w)

    @torch.jit.script
    def _torch_state_rollout(
        t_a: torch.Tensor,
        t_m: torch.Tensor,
        w_a: torch.Tensor,
        w_b: torch.Tensor,
        src_t: torch.Tensor,
        src_m: torch.Tensor,
        src_w: torch.Tensor,
        inv_at_all: torch.Tensor,
        inv_aw_all: torch.Tensor,
        t_h_sp: torch.Tensor,
        t_c_sp: torch.Tensor,
        rh_h_sp: torch.Tensor,
        rh_d_sp: torch.Tensor,
        c_a_dt: torch.Tensor,
        c_m_dt_over_dm: torch.Tensor,
        h_am: torch.Tensor,
        alpha_m: torch.Tensor,
        m_a_dt: torch.Tensor,
        m_b_dt_over_db: torch.Tensor,
        k_ab: torch.Tensor,
        alpha_b: torch.Tensor,
        q_heat_max: torch.Tensor,
        q_cool_max: torch.Tensor,
        m_hum_max: torch.Tensor,
        m_dehum_max: torch.Tensor,
        smooth_beta_t: float,
        smooth_beta_w: float,
        pressure_pa: float,
        hvac_active: bool,
    ) -> tuple[
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
    ]:
        T_len = src_t.shape[1]
        const_mat = inv_at_all.shape[1] == 1
        inv_at0 = inv_at_all[:, 0]
        inv_aw0 = inv_aw_all[:, 0]
        diag_at0 = torch.diagonal(inv_at0, dim1=-2, dim2=-1)
        diag_aw0 = torch.diagonal(inv_aw0, dim1=-2, dim2=-1)

        root0_qh = torch.sqrt(q_heat_max * q_heat_max + 1.0)
        root0_qc = torch.sqrt(q_cool_max * q_cool_max + 1.0)
        root0_mh = torch.sqrt(m_hum_max * m_hum_max + 1.0e-12)
        root0_md = torch.sqrt(m_dehum_max * m_dehum_max + 1.0e-12)

        t_a_list: list[torch.Tensor] = []
        t_m_list: list[torch.Tensor] = []
        w_a_list: list[torch.Tensor] = []
        w_b_list: list[torch.Tensor] = []
        t_af_list: list[torch.Tensor] = []
        w_af_list: list[torch.Tensor] = []
        q_sh_list: list[torch.Tensor] = []
        q_sc_list: list[torch.Tensor] = []
        m_hu_list: list[torch.Tensor] = []
        m_de_list: list[torch.Tensor] = []
        w_ds_list: list[torch.Tensor] = []

        for t in range(T_len):
            inv_at = inv_at0 if const_mat else inv_at_all[:, t]
            inv_aw = inv_aw0 if const_mat else inv_aw_all[:, t]
            diag_at = diag_at0 if const_mat else torch.diagonal(inv_at, dim1=-2, dim2=-1)
            diag_aw = diag_aw0 if const_mat else torch.diagonal(inv_aw, dim1=-2, dim2=-1)

            term_m = t_m * c_m_dt_over_dm + src_m[:, t]
            r_t = t_a * c_a_dt + src_t[:, t] + h_am * term_m
            t_a_free = torch.bmm(inv_at, r_t.unsqueeze(-1)).squeeze(-1)

            term_b = w_b * m_b_dt_over_db
            r_w = w_a * m_a_dt + src_w[:, t] + k_ab * term_b
            w_a_free = torch.bmm(inv_aw, r_w.unsqueeze(-1)).squeeze(-1)

            if not hvac_active:
                zeros = torch.zeros_like(t_a_free)
                t_a = t_a_free
                w_a = w_a_free
                q_sh = zeros
                q_sc = zeros
                m_hu = zeros
                m_de = zeros
                w_dehum_sp = _torch_w_from_t_rh(t_a, rh_d_sp[:, t], pressure_pa)
            else:
                c_eff = 1.0 / diag_at
                m_eff = 1.0 / diag_aw
                d_t_heat = F.softplus(t_h_sp[:, t] - t_a_free, smooth_beta_t, 20.0)
                d_t_cool = F.softplus(t_a_free - t_c_sp[:, t], smooth_beta_t, 20.0)
                q_sh = _torch_smooth_cap(c_eff * d_t_heat, q_heat_max, root0_qh, 1.0)
                q_sc = _torch_smooth_cap(c_eff * d_t_cool, q_cool_max, root0_qc, 1.0)
                t_a = t_a_free + torch.bmm(inv_at, (q_sh - q_sc).unsqueeze(-1)).squeeze(-1)

                w_hum_sp = _torch_w_from_t_rh(t_a, rh_h_sp[:, t], pressure_pa)
                w_dehum_sp = _torch_w_from_t_rh(t_a, rh_d_sp[:, t], pressure_pa)
                d_w_hum = F.softplus(w_hum_sp - w_a_free, smooth_beta_w, 20.0)
                d_w_dehum = F.softplus(w_a_free - w_dehum_sp, smooth_beta_w, 20.0)
                m_hu = _torch_smooth_cap(m_eff * d_w_hum, m_hum_max, root0_mh, 1.0e-12)
                m_de = _torch_smooth_cap(m_eff * d_w_dehum, m_dehum_max, root0_md, 1.0e-12)
                w_a = torch.clamp(
                    w_a_free + torch.bmm(inv_aw, (m_hu - m_de).unsqueeze(-1)).squeeze(-1),
                    min=1.0e-7,
                )

            t_m = alpha_m * t_a + term_m
            w_b = alpha_b * w_a + term_b

            t_a_list.append(t_a)
            t_m_list.append(t_m)
            w_a_list.append(w_a)
            w_b_list.append(w_b)
            t_af_list.append(t_a_free)
            w_af_list.append(w_a_free)
            q_sh_list.append(q_sh)
            q_sc_list.append(q_sc)
            m_hu_list.append(m_hu)
            m_de_list.append(m_de)
            w_ds_list.append(w_dehum_sp)

        return (
            torch.stack(t_a_list, dim=1),
            torch.stack(t_m_list, dim=1),
            torch.stack(w_a_list, dim=1),
            torch.stack(w_b_list, dim=1),
            torch.stack(t_af_list, dim=1),
            torch.stack(w_af_list, dim=1),
            torch.stack(q_sh_list, dim=1),
            torch.stack(q_sc_list, dim=1),
            torch.stack(m_hu_list, dim=1),
            torch.stack(m_de_list, dim=1),
            torch.stack(w_ds_list, dim=1),
        )


class MuseumROM(_BaseModule):  # type: ignore[misc]
    """Differentiable 5-zone RC-psychrometric museum Reduced-Order Model.

    Can execute over NumPy arrays (returning NumPy arrays) or PyTorch tensors
    (preserving full end-to-end ``autograd`` gradients across 8760-hour trajectories).
    """

    def __init__(self, config: MuseumROMConfig) -> None:
        if torch is not None:
            super().__init__()
        self.config = config
        self.n_zones = config.n_zones

        c = config.constants
        env = config.envelope
        hv = config.hvac

        volumes = np.array([z.volume_m3 for z in config.zones], dtype=np.float64)
        floor_areas = np.array([z.floor_area_m2 for z in config.zones], dtype=np.float64)

        self.floor_areas_np = floor_areas
        self.volumes_np = volumes
        self.c_air_np = c.rho_air_kg_m3 * c.cp_air_j_kg_k * volumes
        self.c_mass_np = np.array([z.c_mass_j_k for z in config.zones], dtype=np.float64)
        self.h_am_np = np.array([z.h_am_w_k for z in config.zones], dtype=np.float64)

        self.m_air_np = c.rho_air_kg_m3 * volumes
        self.m_buffer_np = np.array([z.m_buffer_kg for z in config.zones], dtype=np.float64)
        self.k_ab_np = np.array(
            [z.m_buffer_kg / (z.tau_buffer_h * 3600.0) for z in config.zones], dtype=np.float64
        )

        # Exterior conductive UA [W/K] per zone
        self.h_ext_np = np.array(
            [
                env.u_wall_w_m2_k * z.ext_wall_opaque_m2
                + env.u_roof_w_m2_k * z.roof_area_m2
                + env.u_window_w_m2_k * z.window_area_m2
                for z in config.zones
            ],
            dtype=np.float64,
        )
        # Ground UA [W/K] on interior mass node per zone
        self.h_ground_np = env.u_ground_w_m2_k * floor_areas

        # Design infiltration mass flow rate [kg_da/s]
        self.m_inf_design_np = c.rho_air_kg_m3 * volumes * (env.infiltration_ach_design / 3600.0)

        # Solar apertures (transmitted gain per unit incident irradiance) [m^2]
        self.solar_aperture_np = np.array(
            [z.window_area_m2 * env.window_shgc * z.solar_weight for z in config.zones],
            dtype=np.float64,
        )

        # Design internal gain capacities
        self.design_lights_w_np = np.array([z.design_lights_w for z in config.zones], dtype=np.float64)
        self.design_equip_w_np = np.array([z.design_equip_w for z in config.zones], dtype=np.float64)
        self.design_people_np = np.array([z.design_people for z in config.zones], dtype=np.float64)

        # HVAC capacities [W] or [kg_v/s] per zone
        self.q_heat_max_np = hv.q_heat_max_w_per_m2 * floor_areas
        self.q_cool_max_np = hv.q_cool_max_w_per_m2 * floor_areas
        self.m_hum_max_np = hv.m_hum_max_kg_s_per_m2 * floor_areas
        self.m_dehum_max_np = hv.m_dehum_max_kg_s_per_m2 * floor_areas

        # Symmetric inter-zone coupling matrices G_inter [W/K], m_inter [kg_da/s], Laplacians L_T, L_W
        n = self.n_zones
        g_cond = np.zeros((n, n), dtype=np.float64)
        m_exch = np.zeros((n, n), dtype=np.float64)
        for p in config.interzone_partitions:
            i = config.zone_index(p.zone_a)
            j = config.zone_index(p.zone_b)
            g_ij = env.u_interzone_wall_w_m2_k * p.area_m2
            v_min = min(volumes[i], volumes[j])
            m_ij = c.rho_air_kg_m3 * v_min * (env.interzone_air_exchange_ach / 3600.0)
            g_cond[i, j] += g_ij
            g_cond[j, i] += g_ij
            m_exch[i, j] += m_ij
            m_exch[j, i] += m_ij

        self.g_inter_cond_np = g_cond
        self.m_inter_air_np = m_exch
        self.h_inter_total_np = g_cond + c.cp_air_j_kg_k * m_exch

        self.laplacian_t_np = np.diag(self.h_inter_total_np.sum(axis=1)) - self.h_inter_total_np
        self.laplacian_w_np = np.diag(self.m_inter_air_np.sum(axis=1)) - self.m_inter_air_np

    def total_thermal_energy_j(self, t_air_c: ArrayLike, t_mass_c: ArrayLike) -> Any:
        """Compute total zone air + thermal mass enthalpy relative to 0 deg C [J]."""
        if _is_torch(t_air_c):
            c_air = torch.as_tensor(self.c_air_np, dtype=t_air_c.dtype, device=t_air_c.device)
            c_mass = torch.as_tensor(self.c_mass_np, dtype=t_air_c.dtype, device=t_air_c.device)
            return torch.sum(t_air_c * c_air + t_mass_c * c_mass, dim=-1)
        t_a = np.asarray(t_air_c, dtype=np.float64)
        t_m = np.asarray(t_mass_c, dtype=np.float64)
        return np.sum(t_a * self.c_air_np + t_m * self.c_mass_np, axis=-1)

    def total_water_mass_kg(self, w_air_kg_kg: ArrayLike, w_buffer_kg_kg: ArrayLike) -> Any:
        """Compute total water vapor mass in zone air + moisture buffer nodes [kg_v]."""
        if _is_torch(w_air_kg_kg):
            m_air = torch.as_tensor(self.m_air_np, dtype=w_air_kg_kg.dtype, device=w_air_kg_kg.device)
            m_buf = torch.as_tensor(self.m_buffer_np, dtype=w_air_kg_kg.dtype, device=w_air_kg_kg.device)
            return torch.sum(w_air_kg_kg * m_air + w_buffer_kg_kg * m_buf, dim=-1)
        w_a = np.asarray(w_air_kg_kg, dtype=np.float64)
        w_b = np.asarray(w_buffer_kg_kg, dtype=np.float64)
        return np.sum(w_a * self.m_air_np + w_b * self.m_buffer_np, axis=-1)

    def forward(
        self,
        *,
        t_out_c: ArrayLike,
        rh_out_percent: ArrayLike | None = None,
        w_out_kg_kg: ArrayLike | None = None,
        solar_rad_w_m2: ArrayLike | None = None,
        occupancy_frac: ArrayLike | None = None,
        lighting_frac: ArrayLike | None = None,
        equipment_frac: ArrayLike | None = None,
        infiltration_scale: ArrayLike | None = None,
        t_ground_c: ArrayLike | None = None,
        q_extra_air_w: ArrayLike | None = None,
        q_extra_mass_w: ArrayLike | None = None,
        m_extra_vapor_kg_s: ArrayLike | None = None,
        t_heat_sp_c: ArrayLike | None = None,
        t_cool_sp_c: ArrayLike | None = None,
        rh_hum_sp_percent: ArrayLike | None = None,
        rh_dehum_sp_percent: ArrayLike | None = None,
        hvac_active: bool = True,
        t_air_init_c: ArrayLike | None = None,
        t_mass_init_c: ArrayLike | None = None,
        w_air_init_kg_kg: ArrayLike | None = None,
        w_buffer_init_kg_kg: ArrayLike | None = None,
        dt_hours: float = 1.0,
        pressure_pa: float = STANDARD_ATM_PRESSURE_PA,
    ) -> dict[str, Any]:
        """Simulate the 5-zone museum trajectory over ``T`` steps of duration ``dt_hours``."""
        if rh_out_percent is None and w_out_kg_kg is None:
            raise ValueError("Provide either 'rh_out_percent' or 'w_out_kg_kg'.")
        if dt_hours <= 0.0:
            raise ValueError(f"dt_hours must be > 0, got {dt_hours}.")

        use_torch = any(
            _is_torch(x)
            for x in (
                t_out_c,
                rh_out_percent,
                w_out_kg_kg,
                solar_rad_w_m2,
                occupancy_frac,
                t_heat_sp_c,
                t_cool_sp_c,
                rh_hum_sp_percent,
                rh_dehum_sp_percent,
                t_air_init_c,
            )
            if x is not None
        )

        if use_torch:
            return self._forward_torch(
                t_out_c=t_out_c,
                rh_out_percent=rh_out_percent,
                w_out_kg_kg=w_out_kg_kg,
                solar_rad_w_m2=solar_rad_w_m2,
                occupancy_frac=occupancy_frac,
                lighting_frac=lighting_frac,
                equipment_frac=equipment_frac,
                infiltration_scale=infiltration_scale,
                t_ground_c=t_ground_c,
                q_extra_air_w=q_extra_air_w,
                q_extra_mass_w=q_extra_mass_w,
                m_extra_vapor_kg_s=m_extra_vapor_kg_s,
                t_heat_sp_c=t_heat_sp_c,
                t_cool_sp_c=t_cool_sp_c,
                rh_hum_sp_percent=rh_hum_sp_percent,
                rh_dehum_sp_percent=rh_dehum_sp_percent,
                hvac_active=hvac_active,
                t_air_init_c=t_air_init_c,
                t_mass_init_c=t_mass_init_c,
                w_air_init_kg_kg=w_air_init_kg_kg,
                w_buffer_init_kg_kg=w_buffer_init_kg_kg,
                dt_hours=dt_hours,
                pressure_pa=pressure_pa,
            )
        return self._forward_numpy(
            t_out_c=t_out_c,
            rh_out_percent=rh_out_percent,
            w_out_kg_kg=w_out_kg_kg,
            solar_rad_w_m2=solar_rad_w_m2,
            occupancy_frac=occupancy_frac,
            lighting_frac=lighting_frac,
            equipment_frac=equipment_frac,
            infiltration_scale=infiltration_scale,
            t_ground_c=t_ground_c,
            q_extra_air_w=q_extra_air_w,
            q_extra_mass_w=q_extra_mass_w,
            m_extra_vapor_kg_s=m_extra_vapor_kg_s,
            t_heat_sp_c=t_heat_sp_c,
            t_cool_sp_c=t_cool_sp_c,
            rh_hum_sp_percent=rh_hum_sp_percent,
            rh_dehum_sp_percent=rh_dehum_sp_percent,
            hvac_active=hvac_active,
            t_air_init_c=t_air_init_c,
            t_mass_init_c=t_mass_init_c,
            w_air_init_kg_kg=w_air_init_kg_kg,
            w_buffer_init_kg_kg=w_buffer_init_kg_kg,
            dt_hours=dt_hours,
            pressure_pa=pressure_pa,
        )

    def _prepare_forcing_numpy(
        self,
        *,
        t_out_c: ArrayLike,
        rh_out_percent: ArrayLike | None,
        w_out_kg_kg: ArrayLike | None,
        solar_rad_w_m2: ArrayLike | None,
        occupancy_frac: ArrayLike | None,
        lighting_frac: ArrayLike | None,
        equipment_frac: ArrayLike | None,
        infiltration_scale: ArrayLike | None,
        t_ground_c: ArrayLike | None,
        q_extra_air_w: ArrayLike | None,
        q_extra_mass_w: ArrayLike | None,
        m_extra_vapor_kg_s: ArrayLike | None,
        t_heat_sp_c: ArrayLike | None,
        t_cool_sp_c: ArrayLike | None,
        rh_hum_sp_percent: ArrayLike | None,
        rh_dehum_sp_percent: ArrayLike | None,
        t_air_init_c: ArrayLike | None,
        t_mass_init_c: ArrayLike | None,
        w_air_init_kg_kg: ArrayLike | None,
        w_buffer_init_kg_kg: ArrayLike | None,
        pressure_pa: float,
    ) -> tuple[bool, dict[str, np.ndarray]]:
        t_out_raw = np.asarray(t_out_c, dtype=np.float64)
        if t_out_raw.ndim not in (1, 2):
            raise ValueError(f"t_out_c must have shape (T,) or (B, T), got {t_out_raw.shape}.")
        batched = t_out_raw.ndim == 2
        t_out = t_out_raw if batched else t_out_raw[None, :]
        B, T = t_out.shape
        N = self.n_zones

        def _bt(x: ArrayLike | None, default: float) -> np.ndarray:
            if x is None:
                return np.full((B, T), default, dtype=np.float64)
            arr = np.asarray(x, dtype=np.float64)
            if arr.ndim == 0:
                return np.full((B, T), float(arr), dtype=np.float64)
            if arr.ndim == 1:
                if arr.shape[0] != T:
                    raise ValueError(f"Expected length {T}, got {arr.shape}.")
                return np.broadcast_to(arr[None, :], (B, T)).copy()
            return np.broadcast_to(arr, (B, T)).copy()

        def _btz(x: ArrayLike | None, default: float) -> np.ndarray:
            if x is None:
                return np.full((B, T, N), default, dtype=np.float64)
            arr = np.asarray(x, dtype=np.float64)
            if arr.ndim == 0:
                return np.full((B, T, N), float(arr), dtype=np.float64)
            if arr.ndim == 1:
                if arr.shape[0] == N:
                    return np.broadcast_to(arr[None, None, :], (B, T, N)).copy()
                if arr.shape[0] == T:
                    return np.broadcast_to(arr[None, :, None], (B, T, N)).copy()
                raise ValueError(f"Cannot broadcast shape {arr.shape} to (B={B}, T={T}, N={N}).")
            if arr.ndim == 2:
                if arr.shape == (T, N):
                    return np.broadcast_to(arr[None, :, :], (B, T, N)).copy()
                if arr.shape == (B, T):
                    return np.broadcast_to(arr[:, :, None], (B, T, N)).copy()
                raise ValueError(f"Cannot broadcast shape {arr.shape} to (B={B}, T={T}, N={N}).")
            return np.broadcast_to(arr, (B, T, N)).copy()

        def _bz(x: ArrayLike | None, default_vec: np.ndarray) -> np.ndarray:
            if x is None:
                return np.broadcast_to(default_vec[None, :], (B, N)).copy()
            arr = np.asarray(x, dtype=np.float64)
            if arr.ndim == 0:
                return np.full((B, N), float(arr), dtype=np.float64)
            if arr.ndim == 1:
                return np.broadcast_to(arr[None, :], (B, N)).copy()
            return np.broadcast_to(arr, (B, N)).copy()

        if w_out_kg_kg is not None:
            w_out = _bt(w_out_kg_kg, 0.0)
        else:
            rh_out = _bt(rh_out_percent, 50.0)
            w_out = humidity_ratio_from_temp_rh(t_out, rh_out, pressure_pa=pressure_pa)

        solar = _btz(solar_rad_w_m2, 0.0)
        occ = _btz(occupancy_frac, 0.0)
        lights = _btz(lighting_frac, 0.0) if lighting_frac is not None else occ
        equip = _btz(equipment_frac, 0.0) if equipment_frac is not None else occ
        inf_scale = _bt(infiltration_scale, 1.0)
        t_gnd = _bt(t_ground_c, float(np.mean(t_out))) if t_ground_c is None else _bt(t_ground_c, 15.0)

        c = self.config.constants
        q_sol_total = solar * self.solar_aperture_np[None, None, :]
        q_lights_total = lights * self.design_lights_w_np[None, None, :]
        q_equip_total = equip * self.design_equip_w_np[None, None, :]
        q_ppl_sens = occ * self.design_people_np[None, None, :] * c.person_sensible_w
        m_ppl_lat = occ * self.design_people_np[None, None, :] * c.person_latent_kg_s

        q_int_total = q_lights_total + q_equip_total + q_ppl_sens
        f_sol_air = c.solar_to_air_fraction
        f_int_rad = c.internal_rad_fraction

        q_air = (
            f_sol_air * q_sol_total
            + (1.0 - f_int_rad) * q_int_total
            + _btz(q_extra_air_w, 0.0)
        )
        q_mass = (
            (1.0 - f_sol_air) * q_sol_total
            + f_int_rad * q_int_total
            + _btz(q_extra_mass_w, 0.0)
        )
        m_vapor = m_ppl_lat + _btz(m_extra_vapor_kg_s, 0.0)

        w_default_init = float(humidity_ratio_from_temp_rh(20.0, 50.0, pressure_pa=pressure_pa))
        prepared = {
            "t_out": t_out,
            "w_out": w_out,
            "inf_scale": inf_scale,
            "t_ground": t_gnd,
            "q_air": q_air,
            "q_mass": q_mass,
            "m_vapor": m_vapor,
            "t_heat_sp": _btz(t_heat_sp_c, 19.0),
            "t_cool_sp": _btz(t_cool_sp_c, 24.0),
            "rh_hum_sp": _btz(rh_hum_sp_percent, 40.0),
            "rh_dehum_sp": _btz(rh_dehum_sp_percent, 60.0),
            "t_air_init": _bz(t_air_init_c, np.full(N, 20.0)),
            "t_mass_init": _bz(t_mass_init_c, np.full(N, 20.0)),
            "w_air_init": _bz(w_air_init_kg_kg, np.full(N, w_default_init)),
            "w_buffer_init": _bz(w_buffer_init_kg_kg, np.full(N, w_default_init)),
        }
        return batched, prepared

    def _apply_hvac_control_step(
        self,
        *,
        t_a_free: Any,
        w_a_free: Any,
        t_heat_sp: Any,
        t_cool_sp: Any,
        rh_hum_sp: Any,
        rh_dehum_sp: Any,
        diag_inv_at: Any,
        diag_inv_aw: Any,
        inv_at: Any,
        inv_aw: Any,
        pressure_pa: float,
        q_heat_max: Any,
        q_cool_max: Any,
        m_hum_max: Any,
        m_dehum_max: Any,
        hvac_active: bool,
        use_torch: bool,
    ) -> dict[str, Any]:
        """Apply dual-setpoint IdealLoads sensible and latent control step."""
        hv = self.config.hvac

        if not hvac_active:
            zeros = _zeros_like(t_a_free, use_torch)
            return {
                "t_a_next": t_a_free,
                "w_a_next": w_a_free,
                "q_sens_heat_w": zeros,
                "q_sens_cool_w": zeros,
                "m_hum_kg_s": zeros,
                "m_dehum_kg_s": zeros,
                "w_dehum_sp": humidity_ratio_from_temp_rh(t_a_free, rh_dehum_sp, pressure_pa=pressure_pa),
            }

        c_eff = 1.0 / diag_inv_at
        m_eff = 1.0 / diag_inv_aw

        d_t_heat = _softplus(t_heat_sp - t_a_free, beta=hv.smooth_beta_t)
        d_t_cool = _softplus(t_a_free - t_cool_sp, beta=hv.smooth_beta_t)

        q_sens_heat = _smooth_cap(c_eff * d_t_heat, q_heat_max, 1.0)
        q_sens_cool = _smooth_cap(c_eff * d_t_cool, q_cool_max, 1.0)
        q_sens_net = q_sens_heat - q_sens_cool

        t_a_next = t_a_free + _matvec(inv_at, q_sens_net, use_torch)

        w_hum_sp = humidity_ratio_from_temp_rh(t_a_next, rh_hum_sp, pressure_pa=pressure_pa)
        w_dehum_sp = humidity_ratio_from_temp_rh(t_a_next, rh_dehum_sp, pressure_pa=pressure_pa)

        d_w_hum = _softplus(w_hum_sp - w_a_free, beta=hv.smooth_beta_w)
        d_w_dehum = _softplus(w_a_free - w_dehum_sp, beta=hv.smooth_beta_w)

        m_hum = _smooth_cap(m_eff * d_w_hum, m_hum_max, 1e-6)
        m_dehum = _smooth_cap(m_eff * d_w_dehum, m_dehum_max, 1e-6)
        m_net = m_hum - m_dehum

        w_a_next = _clamp_min_w(
            w_a_free + _matvec(inv_aw, m_net, use_torch),
            1e-7,
            use_torch,
        )

        return {
            "t_a_next": t_a_next,
            "w_a_next": w_a_next,
            "q_sens_heat_w": q_sens_heat,
            "q_sens_cool_w": q_sens_cool,
            "m_hum_kg_s": m_hum,
            "m_dehum_kg_s": m_dehum,
            "w_dehum_sp": w_dehum_sp,
        }

    def _package_outputs(
        self,
        *,
        t_air: Any,
        t_mass: Any,
        w_air: Any,
        w_buffer: Any,
        t_a_free: Any,
        w_a_free: Any,
        q_sens_heat: Any,
        q_sens_cool: Any,
        m_hum: Any,
        m_dehum: Any,
        w_dehum_sp: Any,
        hvac_active: bool,
        dt_hours: float,
        pressure_pa: float,
        batched: bool,
        use_torch: bool,
    ) -> dict[str, Any]:
        hv = self.config.hvac
        c = self.config.constants
        w_to_kwh = dt_hours / 1000.0

        rh_air = rh_from_temp_w(t_air, w_air, pressure_pa=pressure_pa, clip_upper=False)

        if not hvac_active:
            zeros = _zeros_like(t_air, use_torch)
            q_hum = t_coil = m_proc = q_dehum_latent = q_dehum_sens = q_dehum_coil = q_reheat = q_cool_total = q_heat_total = zeros
        else:
            q_hum = m_hum * latent_heat_vaporization_j_per_kg(t_air)
            t_dp_target = dew_point_from_w(w_dehum_sp, pressure_pa=pressure_pa)
            t_coil = t_dp_target - hv.coil_approach_dt_c
            w_coil = humidity_ratio_from_temp_rh(t_coil, 100.0, pressure_pa=pressure_pa)

            delta_w_coil = _softplus(w_a_free - w_coil, beta=hv.smooth_beta_w) + 2.0e-4
            m_proc = m_dehum / delta_w_coil
            delta_t_coil = _softplus(t_a_free - t_coil, beta=hv.smooth_beta_t)

            q_dehum_latent = m_dehum * latent_heat_vaporization_j_per_kg(t_coil)
            q_dehum_sens = m_proc * c.cp_air_j_kg_k * delta_t_coil
            q_dehum_coil = q_dehum_latent + q_dehum_sens

            q_reheat = _smooth_pos_diff(q_dehum_sens, q_sens_cool, eps=1.0)
            q_extra_sens_cool = _smooth_pos_diff(q_sens_cool, q_dehum_sens, eps=1.0)

            q_cool_total = q_dehum_coil + q_extra_sens_cool
            q_heat_total = q_sens_heat + q_reheat

        e_cool_elec = (q_cool_total * w_to_kwh) / hv.cop_cooling
        e_heat_elec = (q_sens_heat * w_to_kwh) / hv.eta_heating
        e_reheat_elec = (q_reheat * w_to_kwh) / hv.eta_reheat
        e_hum_elec = (q_hum * w_to_kwh) / hv.eta_humidification
        e_fan_elec = (
            hv.fan_w_per_w_sensible
            * (q_cool_total + q_sens_heat + q_reheat + q_hum)
            * w_to_kwh
        )
        e_total_elec = e_cool_elec + e_heat_elec + e_reheat_elec + e_hum_elec + e_fan_elec
        e_primary = e_total_elec * hv.electricity_primary_factor
        co2_kg = e_total_elec * hv.electricity_co2_kg_per_kwh

        out: dict[str, Any] = {
            "t_air_c": t_air,
            "t_mass_c": t_mass,
            "w_air_kg_kg": w_air,
            "w_buffer_kg_kg": w_buffer,
            "rh_air_percent": rh_air,
            "q_sens_heat_w": q_sens_heat,
            "q_sens_cool_w": q_sens_cool,
            "q_hum_w": q_hum,
            "m_hum_kg_s": m_hum,
            "m_dehum_kg_s": m_dehum,
            "m_proc_air_kg_s": m_proc,
            "t_coil_dewpoint_c": t_coil,
            "q_dehum_latent_w": q_dehum_latent,
            "q_dehum_sens_w": q_dehum_sens,
            "q_dehum_coil_w": q_dehum_coil,
            "q_reheat_w": q_reheat,
            "q_cool_total_w": q_cool_total,
            "q_heat_total_w": q_heat_total,
            "e_sens_heat_kwh": q_sens_heat * w_to_kwh,
            "e_sens_cool_kwh": q_sens_cool * w_to_kwh,
            "e_hum_kwh": q_hum * w_to_kwh,
            "e_dehum_coil_kwh": q_dehum_coil * w_to_kwh,
            "e_reheat_kwh": q_reheat * w_to_kwh,
            "e_cool_elec_kwh": e_cool_elec,
            "e_heat_elec_kwh": e_heat_elec,
            "e_reheat_elec_kwh": e_reheat_elec,
            "e_hum_elec_kwh": e_hum_elec,
            "e_fan_elec_kwh": e_fan_elec,
            "e_total_elec_kwh": e_total_elec,
            "e_primary_kwh": e_primary,
            "co2_kg": co2_kg,
        }

        if use_torch:
            out["total_elec_kwh"] = torch.sum(e_total_elec, dim=-1)
            out["total_primary_kwh"] = torch.sum(e_primary, dim=-1)
            out["total_co2_kg"] = torch.sum(co2_kg, dim=-1)
            out["total_sens_heat_kwh"] = torch.sum(out["e_sens_heat_kwh"], dim=-1)
            out["total_sens_cool_kwh"] = torch.sum(out["e_sens_cool_kwh"], dim=-1)
            out["total_hum_kwh"] = torch.sum(out["e_hum_kwh"], dim=-1)
            out["total_dehum_coil_kwh"] = torch.sum(out["e_dehum_coil_kwh"], dim=-1)
            out["total_reheat_kwh"] = torch.sum(out["e_reheat_kwh"], dim=-1)
        else:
            out["total_elec_kwh"] = np.sum(e_total_elec, axis=-1)
            out["total_primary_kwh"] = np.sum(e_primary, axis=-1)
            out["total_co2_kg"] = np.sum(co2_kg, axis=-1)
            out["total_sens_heat_kwh"] = np.sum(out["e_sens_heat_kwh"], axis=-1)
            out["total_sens_cool_kwh"] = np.sum(out["e_sens_cool_kwh"], axis=-1)
            out["total_hum_kwh"] = np.sum(out["e_hum_kwh"], axis=-1)
            out["total_dehum_coil_kwh"] = np.sum(out["e_dehum_coil_kwh"], axis=-1)
            out["total_reheat_kwh"] = np.sum(out["e_reheat_kwh"], axis=-1)

        if not batched:
            out = {k: v[0] for k, v in out.items()}
        return out

    def _forward_numpy(
        self,
        *,
        t_out_c: ArrayLike,
        rh_out_percent: ArrayLike | None,
        w_out_kg_kg: ArrayLike | None,
        solar_rad_w_m2: ArrayLike | None,
        occupancy_frac: ArrayLike | None,
        lighting_frac: ArrayLike | None,
        equipment_frac: ArrayLike | None,
        infiltration_scale: ArrayLike | None,
        t_ground_c: ArrayLike | None,
        q_extra_air_w: ArrayLike | None,
        q_extra_mass_w: ArrayLike | None,
        m_extra_vapor_kg_s: ArrayLike | None,
        t_heat_sp_c: ArrayLike | None,
        t_cool_sp_c: ArrayLike | None,
        rh_hum_sp_percent: ArrayLike | None,
        rh_dehum_sp_percent: ArrayLike | None,
        hvac_active: bool,
        t_air_init_c: ArrayLike | None,
        t_mass_init_c: ArrayLike | None,
        w_air_init_kg_kg: ArrayLike | None,
        w_buffer_init_kg_kg: ArrayLike | None,
        dt_hours: float,
        pressure_pa: float,
    ) -> dict[str, Any]:
        batched, prep = self._prepare_forcing_numpy(
            t_out_c=t_out_c,
            rh_out_percent=rh_out_percent,
            w_out_kg_kg=w_out_kg_kg,
            solar_rad_w_m2=solar_rad_w_m2,
            occupancy_frac=occupancy_frac,
            lighting_frac=lighting_frac,
            equipment_frac=equipment_frac,
            infiltration_scale=infiltration_scale,
            t_ground_c=t_ground_c,
            q_extra_air_w=q_extra_air_w,
            q_extra_mass_w=q_extra_mass_w,
            m_extra_vapor_kg_s=m_extra_vapor_kg_s,
            t_heat_sp_c=t_heat_sp_c,
            t_cool_sp_c=t_cool_sp_c,
            rh_hum_sp_percent=rh_hum_sp_percent,
            rh_dehum_sp_percent=rh_dehum_sp_percent,
            t_air_init_c=t_air_init_c,
            t_mass_init_c=t_mass_init_c,
            w_air_init_kg_kg=w_air_init_kg_kg,
            w_buffer_init_kg_kg=w_buffer_init_kg_kg,
            pressure_pa=pressure_pa,
        )
        t_out = prep["t_out"]
        B, T = t_out.shape
        N = self.n_zones
        dt_sec = dt_hours * 3600.0
        cp = self.config.constants.cp_air_j_kg_k

        # Schur parameters (constant across time)
        c_a_dt = self.c_air_np / dt_sec
        c_m_dt = self.c_mass_np / dt_sec
        d_m = c_m_dt + self.h_am_np + self.h_ground_np
        alpha_m = self.h_am_np / d_m
        h_am_eff = self.h_am_np * (1.0 - alpha_m)

        m_a_dt = self.m_air_np / dt_sec
        m_b_dt = self.m_buffer_np / dt_sec
        d_b = m_b_dt + self.k_ab_np
        alpha_b = self.k_ab_np / d_b
        k_ab_eff = self.k_ab_np * (1.0 - alpha_b)

        # Time-varying infiltration & batched matrix inversions (B, T, N, N)
        m_inf = prep["inf_scale"][:, :, None] * self.m_inf_design_np[None, None, :]
        h_inf = cp * m_inf

        diag_t = (c_a_dt + self.h_ext_np + h_am_eff)[None, None, :] + h_inf
        diag_w = (m_a_dt + k_ab_eff)[None, None, :] + m_inf

        eye = np.eye(N, dtype=np.float64)[None, None, :, :]
        mat_t = self.laplacian_t_np[None, None, :, :] + diag_t[:, :, :, None] * eye
        mat_w = self.laplacian_w_np[None, None, :, :] + diag_w[:, :, :, None] * eye
        inv_at_all = np.linalg.inv(mat_t)
        inv_aw_all = np.linalg.inv(mat_w)
        diag_inv_at_all = np.diagonal(inv_at_all, axis1=-2, axis2=-1)
        diag_inv_aw_all = np.diagonal(inv_aw_all, axis1=-2, axis2=-1)

        t_a = prep["t_air_init"].copy()
        t_m = prep["t_mass_init"].copy()
        w_a = prep["w_air_init"].copy()
        w_b = prep["w_buffer_init"].copy()

        buf_names = (
            "t_air_c",
            "t_mass_c",
            "w_air_kg_kg",
            "w_buffer_kg_kg",
            "t_a_free",
            "w_a_free",
            "q_sens_heat_w",
            "q_sens_cool_w",
            "m_hum_kg_s",
            "m_dehum_kg_s",
            "w_dehum_sp",
        )
        buffers = {k: np.empty((B, T, N), dtype=np.float64) for k in buf_names}

        w_out = prep["w_out"]
        t_gnd = prep["t_ground"]
        q_air_arr = prep["q_air"]
        q_mass_arr = prep["q_mass"]
        m_vap_arr = prep["m_vapor"]
        t_h_sp = prep["t_heat_sp"]
        t_c_sp = prep["t_cool_sp"]
        rh_h_sp = prep["rh_hum_sp"]
        rh_d_sp = prep["rh_dehum_sp"]

        for t in range(T):
            inv_at = inv_at_all[:, t]
            inv_aw = inv_aw_all[:, t]
            diag_inv_at = diag_inv_at_all[:, t]
            diag_inv_aw = diag_inv_aw_all[:, t]

            term_m = (t_m * c_m_dt + t_gnd[:, t : t + 1] * self.h_ground_np + q_mass_arr[:, t]) / d_m
            r_t = (
                t_a * c_a_dt
                + t_out[:, t : t + 1] * (self.h_ext_np + h_inf[:, t])
                + self.h_am_np * term_m
                + q_air_arr[:, t]
            )
            t_a_free = np.einsum("bij,bj->bi", inv_at, r_t)

            term_b = (w_b * m_b_dt) / d_b
            r_w = (
                w_a * m_a_dt
                + w_out[:, t : t + 1] * m_inf[:, t]
                + self.k_ab_np * term_b
                + m_vap_arr[:, t]
            )
            w_a_free = np.einsum("bij,bj->bi", inv_aw, r_w)

            step_res = self._apply_hvac_control_step(
                t_a_free=t_a_free,
                w_a_free=w_a_free,
                t_heat_sp=t_h_sp[:, t],
                t_cool_sp=t_c_sp[:, t],
                rh_hum_sp=rh_h_sp[:, t],
                rh_dehum_sp=rh_d_sp[:, t],
                diag_inv_at=diag_inv_at,
                diag_inv_aw=diag_inv_aw,
                inv_at=inv_at,
                inv_aw=inv_aw,
                pressure_pa=pressure_pa,
                q_heat_max=self.q_heat_max_np,
                q_cool_max=self.q_cool_max_np,
                m_hum_max=self.m_hum_max_np,
                m_dehum_max=self.m_dehum_max_np,
                hvac_active=hvac_active,
                use_torch=False,
            )

            t_a = step_res["t_a_next"]
            w_a = step_res["w_a_next"]
            t_m = alpha_m * t_a + term_m
            w_b = alpha_b * w_a + term_b

            buffers["t_air_c"][:, t] = t_a
            buffers["t_mass_c"][:, t] = t_m
            buffers["w_air_kg_kg"][:, t] = w_a
            buffers["w_buffer_kg_kg"][:, t] = w_b
            buffers["t_a_free"][:, t] = t_a_free
            buffers["w_a_free"][:, t] = w_a_free
            buffers["q_sens_heat_w"][:, t] = step_res["q_sens_heat_w"]
            buffers["q_sens_cool_w"][:, t] = step_res["q_sens_cool_w"]
            buffers["m_hum_kg_s"][:, t] = step_res["m_hum_kg_s"]
            buffers["m_dehum_kg_s"][:, t] = step_res["m_dehum_kg_s"]
            buffers["w_dehum_sp"][:, t] = step_res["w_dehum_sp"]

        return self._package_outputs(
            t_air=buffers["t_air_c"],
            t_mass=buffers["t_mass_c"],
            w_air=buffers["w_air_kg_kg"],
            w_buffer=buffers["w_buffer_kg_kg"],
            t_a_free=buffers["t_a_free"],
            w_a_free=buffers["w_a_free"],
            q_sens_heat=buffers["q_sens_heat_w"],
            q_sens_cool=buffers["q_sens_cool_w"],
            m_hum=buffers["m_hum_kg_s"],
            m_dehum=buffers["m_dehum_kg_s"],
            w_dehum_sp=buffers["w_dehum_sp"],
            hvac_active=hvac_active,
            dt_hours=dt_hours,
            pressure_pa=pressure_pa,
            batched=batched,
            use_torch=False,
        )

    def _forward_torch(
        self,
        *,
        t_out_c: ArrayLike,
        rh_out_percent: ArrayLike | None,
        w_out_kg_kg: ArrayLike | None,
        solar_rad_w_m2: ArrayLike | None,
        occupancy_frac: ArrayLike | None,
        lighting_frac: ArrayLike | None,
        equipment_frac: ArrayLike | None,
        infiltration_scale: ArrayLike | None,
        t_ground_c: ArrayLike | None,
        q_extra_air_w: ArrayLike | None,
        q_extra_mass_w: ArrayLike | None,
        m_extra_vapor_kg_s: ArrayLike | None,
        t_heat_sp_c: ArrayLike | None,
        t_cool_sp_c: ArrayLike | None,
        rh_hum_sp_percent: ArrayLike | None,
        rh_dehum_sp_percent: ArrayLike | None,
        hvac_active: bool,
        t_air_init_c: ArrayLike | None,
        t_mass_init_c: ArrayLike | None,
        w_air_init_kg_kg: ArrayLike | None,
        w_buffer_init_kg_kg: ArrayLike | None,
        dt_hours: float,
        pressure_pa: float,
    ) -> dict[str, Any]:
        assert torch is not None

        # Infer reference tensor dtype & device from first tensor input
        ref_tensor: torch.Tensor | None = None
        for cand in (
            t_heat_sp_c,
            t_cool_sp_c,
            rh_hum_sp_percent,
            rh_dehum_sp_percent,
            t_out_c,
            rh_out_percent,
            t_air_init_c,
        ):
            if isinstance(cand, torch.Tensor):
                ref_tensor = cand
                break
        assert ref_tensor is not None
        dtype = ref_tensor.dtype if ref_tensor.is_floating_point() else torch.float64
        device = ref_tensor.device

        def _as_t(x: Any) -> torch.Tensor:
            if isinstance(x, torch.Tensor):
                return x.to(device=device, dtype=dtype)
            return torch.as_tensor(x, dtype=dtype, device=device)

        t_out_raw = _as_t(t_out_c)
        if t_out_raw.ndim not in (1, 2):
            raise ValueError(f"t_out_c must have shape (T,) or (B, T), got {tuple(t_out_raw.shape)}.")
        batched = t_out_raw.ndim == 2
        t_out = t_out_raw if batched else t_out_raw.unsqueeze(0)
        B, T = t_out.shape
        N = self.n_zones

        def _bt(x: Any, default: float) -> torch.Tensor:
            if x is None:
                return torch.full((B, T), default, dtype=dtype, device=device)
            t = _as_t(x)
            if t.ndim == 0:
                return t.expand(B, T)
            if t.ndim == 1:
                if t.shape[0] != T:
                    raise ValueError(f"Expected length {T}, got {tuple(t.shape)}.")
                return t.unsqueeze(0).expand(B, T)
            return t.expand(B, T)

        def _btz(x: Any, default: float) -> torch.Tensor:
            if x is None:
                return torch.full((B, T, N), default, dtype=dtype, device=device)
            t = _as_t(x)
            if t.ndim == 0:
                return t.expand(B, T, N)
            if t.ndim == 1:
                if t.shape[0] == N:
                    return t.view(1, 1, N).expand(B, T, N)
                if t.shape[0] == T:
                    return t.view(1, T, 1).expand(B, T, N)
                raise ValueError(f"Cannot broadcast shape {tuple(t.shape)} to ({B}, {T}, {N}).")
            if t.ndim == 2:
                if t.shape == (T, N):
                    return t.unsqueeze(0).expand(B, T, N)
                if t.shape == (B, T):
                    return t.unsqueeze(-1).expand(B, T, N)
                raise ValueError(f"Cannot broadcast shape {tuple(t.shape)} to ({B}, {T}, {N}).")
            return t.expand(B, T, N)

        def _bz(x: Any, default_vec: np.ndarray) -> torch.Tensor:
            if x is None:
                return _as_t(default_vec).unsqueeze(0).expand(B, N)
            t = _as_t(x)
            if t.ndim == 0:
                return t.expand(B, N)
            if t.ndim == 1:
                return t.unsqueeze(0).expand(B, N)
            return t.expand(B, N)

        if w_out_kg_kg is not None:
            w_out = _bt(w_out_kg_kg, 0.0)
        else:
            rh_out = _bt(rh_out_percent, 50.0)
            w_out = humidity_ratio_from_temp_rh(t_out, rh_out, pressure_pa=pressure_pa)

        solar = _btz(solar_rad_w_m2, 0.0)
        occ = _btz(occupancy_frac, 0.0)
        lights = _btz(lighting_frac, 0.0) if lighting_frac is not None else occ
        equip = _btz(equipment_frac, 0.0) if equipment_frac is not None else occ
        inf_scale = _bt(infiltration_scale, 1.0)
        t_gnd = torch.mean(t_out, dim=1, keepdim=True).expand(B, T) if t_ground_c is None else _bt(t_ground_c, 15.0)

        c = self.config.constants
        q_sol_total = solar * _as_t(self.solar_aperture_np).view(1, 1, N)
        q_lights_total = lights * _as_t(self.design_lights_w_np).view(1, 1, N)
        q_equip_total = equip * _as_t(self.design_equip_w_np).view(1, 1, N)
        q_ppl_sens = occ * _as_t(self.design_people_np).view(1, 1, N) * c.person_sensible_w
        m_ppl_lat = occ * _as_t(self.design_people_np).view(1, 1, N) * c.person_latent_kg_s

        q_int_total = q_lights_total + q_equip_total + q_ppl_sens
        f_sol_air = c.solar_to_air_fraction
        f_int_rad = c.internal_rad_fraction

        q_air = f_sol_air * q_sol_total + (1.0 - f_int_rad) * q_int_total + _btz(q_extra_air_w, 0.0)
        q_mass = (1.0 - f_sol_air) * q_sol_total + f_int_rad * q_int_total + _btz(q_extra_mass_w, 0.0)
        m_vapor = m_ppl_lat + _btz(m_extra_vapor_kg_s, 0.0)

        t_h_sp = _btz(t_heat_sp_c, 19.0)
        t_c_sp = _btz(t_cool_sp_c, 24.0)
        rh_h_sp = _btz(rh_hum_sp_percent, 40.0)
        rh_d_sp = _btz(rh_dehum_sp_percent, 60.0)

        w_default_init = float(humidity_ratio_from_temp_rh(20.0, 50.0, pressure_pa=pressure_pa))
        t_a = _bz(t_air_init_c, np.full(N, 20.0))
        t_m = _bz(t_mass_init_c, np.full(N, 20.0))
        w_a = _bz(w_air_init_kg_kg, np.full(N, w_default_init))
        w_b = _bz(w_buffer_init_kg_kg, np.full(N, w_default_init))

        dt_sec = dt_hours * 3600.0
        c_air = _as_t(self.c_air_np)
        c_mass = _as_t(self.c_mass_np)
        h_am = _as_t(self.h_am_np)
        h_ext = _as_t(self.h_ext_np)
        h_ground = _as_t(self.h_ground_np)
        m_air = _as_t(self.m_air_np)
        m_buffer = _as_t(self.m_buffer_np)
        k_ab = _as_t(self.k_ab_np)
        m_inf_design = _as_t(self.m_inf_design_np)
        lap_t = _as_t(self.laplacian_t_np)
        lap_w = _as_t(self.laplacian_w_np)
        q_heat_max = _as_t(self.q_heat_max_np)
        q_cool_max = _as_t(self.q_cool_max_np)
        m_hum_max = _as_t(self.m_hum_max_np)
        m_dehum_max = _as_t(self.m_dehum_max_np)

        c_a_dt = c_air / dt_sec
        c_m_dt = c_mass / dt_sec
        d_m = c_m_dt + h_am + h_ground
        alpha_m = h_am / d_m
        h_am_eff = h_am * (1.0 - alpha_m)

        m_a_dt = m_air / dt_sec
        m_b_dt = m_buffer / dt_sec
        d_b = m_b_dt + k_ab
        alpha_b = k_ab / d_b
        k_ab_eff = k_ab * (1.0 - alpha_b)

        # Precompute all T inverses and boundary source vectors before entering TorchScript kernel.
        hv = self.config.hvac
        constant_inf = infiltration_scale is None
        eye = torch.eye(N, dtype=dtype, device=device)
        if constant_inf:
            h_inf_all = (c.cp_air_j_kg_k * m_inf_design).view(1, 1, N)
            m_inf_all = m_inf_design.view(1, 1, N)
            mat_t_const = lap_t + torch.diag(c_a_dt + h_ext + h_am_eff + c.cp_air_j_kg_k * m_inf_design)
            mat_w_const = lap_w + torch.diag(m_a_dt + k_ab_eff + m_inf_design)
            inv_at_all = torch.linalg.inv(mat_t_const).view(1, 1, N, N).expand(B, 1, N, N)
            inv_aw_all = torch.linalg.inv(mat_w_const).view(1, 1, N, N).expand(B, 1, N, N)
        else:
            m_inf_all = inf_scale.unsqueeze(-1) * m_inf_design.view(1, 1, N)
            h_inf_all = c.cp_air_j_kg_k * m_inf_all
            diag_t = (c_a_dt + h_ext + h_am_eff).view(1, 1, N) + h_inf_all
            diag_w = (m_a_dt + k_ab_eff).view(1, 1, N) + m_inf_all
            mat_t = lap_t.view(1, 1, N, N) + diag_t.unsqueeze(-1) * eye.view(1, 1, N, N)
            mat_w = lap_w.view(1, 1, N, N) + diag_w.unsqueeze(-1) * eye.view(1, 1, N, N)
            inv_at_all = torch.linalg.inv(mat_t)
            inv_aw_all = torch.linalg.inv(mat_w)

        src_m = (t_gnd.unsqueeze(-1) * h_ground.view(1, 1, N) + q_mass) / d_m.view(1, 1, N)
        src_t = t_out.unsqueeze(-1) * (h_ext.view(1, 1, N) + h_inf_all) + q_air
        src_w = w_out.unsqueeze(-1) * m_inf_all + m_vapor

        (
            t_air,
            t_mass,
            w_air,
            w_buffer,
            t_a_free,
            w_a_free,
            q_sens_heat,
            q_sens_cool,
            m_hum,
            m_dehum,
            w_dehum_sp,
        ) = _torch_state_rollout(
            t_a,
            t_m,
            w_a,
            w_b,
            src_t,
            src_m,
            src_w,
            inv_at_all,
            inv_aw_all,
            t_h_sp,
            t_c_sp,
            rh_h_sp,
            rh_d_sp,
            c_a_dt,
            c_m_dt / d_m,
            h_am,
            alpha_m,
            m_a_dt,
            m_b_dt / d_b,
            k_ab,
            alpha_b,
            q_heat_max,
            q_cool_max,
            m_hum_max,
            m_dehum_max,
            float(hv.smooth_beta_t),
            float(hv.smooth_beta_w),
            float(pressure_pa),
            bool(hvac_active),
        )

        return self._package_outputs(
            t_air=t_air,
            t_mass=t_mass,
            w_air=w_air,
            w_buffer=w_buffer,
            t_a_free=t_a_free,
            w_a_free=w_a_free,
            q_sens_heat=q_sens_heat,
            q_sens_cool=q_sens_cool,
            m_hum=m_hum,
            m_dehum=m_dehum,
            w_dehum_sp=w_dehum_sp,
            hvac_active=hvac_active,
            dt_hours=dt_hours,
            pressure_pa=pressure_pa,
            batched=batched,
            use_torch=True,
        )
