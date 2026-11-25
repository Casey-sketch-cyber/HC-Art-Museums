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

from dataclasses import dataclass, fields, replace
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


def _sigmoid_np(x: np.ndarray) -> np.ndarray:
    """Numerically stable NumPy logistic sigmoid matching ``torch.sigmoid``."""
    x_safe = np.clip(np.asarray(x, dtype=np.float64), -60.0, 60.0)
    return 1.0 / (1.0 + np.exp(-x_safe))


def _coupled_deadband_solve_numpy(
    inv_mat: np.ndarray,
    x_free: np.ndarray,
    sp_lo: np.ndarray,
    sp_hi: np.ndarray,
    beta: float,
    cap_pos: np.ndarray,
    cap_neg: np.ndarray,
    eps_cap: float,
    eps_pos_sq: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Exact 5-zone coupled IdealLoads complementarity solve without inter-zone overshoot."""
    diag_inv = np.diagonal(inv_mat, axis1=-2, axis2=-1)
    eff = 1.0 / diag_inv
    s_lo = _sigmoid_np(beta * (sp_lo - x_free))
    s_hi = _sigmoid_np(beta * (x_free - sp_hi))
    g = s_lo + s_hi
    d = _softplus(sp_lo - x_free, beta=beta) - _softplus(x_free - sp_hi, beta=beta)
    n = inv_mat.shape[-1]
    eye = np.eye(n, dtype=np.float64)[None, :, :]
    m_sys = eye + g[:, :, None] * (eff[:, :, None] * inv_mat - eye)
    rhs = (g * eff * d)[:, :, None]
    u_unc = np.linalg.solve(m_sys, rhs)[:, :, 0]
    u_pos_raw = g * 0.5 * (u_unc + np.sqrt(u_unc * u_unc + eps_pos_sq))
    u_neg_raw = g * 0.5 * (-u_unc + np.sqrt(u_unc * u_unc + eps_pos_sq))
    u_pos = _smooth_cap(u_pos_raw, cap_pos, eps_cap)
    u_neg = _smooth_cap(u_neg_raw, cap_neg, eps_cap)
    x_next = x_free + np.einsum("bij,bj->bi", inv_mat, u_pos - u_neg)
    return x_next, u_pos, u_neg


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
    effective_mbv_g_m2_rh: float = 0.50
    oa_flow_per_person_m3_s: float = 0.0038  # ASHRAE 62.1 Table 6-1 Museums/galleries: 3.8 L/(s*person)
    oa_flow_per_area_m3_s_m2: float = 0.0003  # ASHRAE 62.1 Table 6-1 Museums/galleries: 0.3 L/(s*m2)


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
    t_sup_cool_min_c: float | None = 13.0


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
    hygroscopic_area_m2: float = 0.0
    weak_m_buffer_kg: float | None = None


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


def _coerce_numeric_dataclass(cls: type[Any], raw_map: dict[str, Any]) -> Any:
    str_fields = {f.name for f in fields(cls) if f.name in {"name", "label"}}
    coerced = {
        k: (float(v) if (v is not None and k not in str_fields) else v)
        for k, v in raw_map.items()
    }
    return cls(**coerced)


def load_building_config(path: str | Path) -> MuseumROMConfig:
    """Load a building ROM YAML configuration into validated dataclasses."""
    cfg_path = Path(path)
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Expected mapping in {cfg_path}")

    constants = _coerce_numeric_dataclass(BuildingConstants, raw["constants"])
    envelope = _coerce_numeric_dataclass(EnvelopeConfig, raw["envelope"])
    hvac = _coerce_numeric_dataclass(HVACConfig, raw["hvac"])
    zones = tuple(_coerce_numeric_dataclass(ZoneConfig, z) for z in raw["zones"])
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
    """Return a copy of ``base`` with zero exterior conduction, ground heat loss, infiltration, and ventilation."""
    env = replace(
        base.envelope,
        u_wall_w_m2_k=0.0,
        u_roof_w_m2_k=0.0,
        u_window_w_m2_k=0.0,
        u_ground_w_m2_k=0.0,
        window_shgc=0.0,
        infiltration_ach_design=0.0,
        oa_flow_per_person_m3_s=0.0,
        oa_flow_per_area_m3_s_m2=0.0,
    )
    return replace(base, tier=f"{base.tier}_adiabatic", envelope=env)


def museum_operating_schedules(
    n_hours: int = 8760,
    *,
    start_day_of_week: str = "Monday",
) -> dict[str, np.ndarray]:
    """Return EnergyPlus-matched hourly museum schedules (``OCCUPY-1``, ``LIGHTS-1``, ``EQUIP-1``).

    Follows the museum schedule definition in ``build_model.py``: Monday closed (5% staff,
    25% daytime lighting, 35% daytime equipment) and Tuesday-Sunday 09:00-17:00 open.
    Day 0 defaults to ``Monday`` matching ``5ZoneAutoDXVAV_multizone.epJSON`` ``RunPeriod 1``.
    """
    days = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    s_norm = start_day_of_week.strip().lower()
    if s_norm not in days:
        raise ValueError(f"Unknown start_day_of_week '{start_day_of_week}'. Expected one of {days}.")
    start_idx = days.index(s_norm)

    occ = np.zeros(n_hours, dtype=np.float64)
    lights = np.zeros(n_hours, dtype=np.float64)
    equip = np.zeros(n_hours, dtype=np.float64)

    for h in range(n_hours):
        day_idx = (start_idx + (h // 24)) % 7
        hod = h % 24  # EnergyPlus Hour 1..24 maps 0..23 -> Until: (hod + 1):00
        is_monday = day_idx == 0

        if is_monday:
            occ[h] = 0.05 if 9 <= hod < 17 else 0.0
            if hod < 8:
                lights[h], equip[h] = 0.05, 0.15
            elif hod == 8:
                # 08:00-08:30 low, 08:30-09:00 open -> mean over hour
                lights[h], equip[h] = 0.5 * (0.05 + 0.25), 0.5 * (0.15 + 0.35)
            elif 9 <= hod < 17:
                lights[h], equip[h] = 0.25, 0.35
            elif hod == 17:
                # 17:00-17:30 active, 17:30-18:00 low -> mean over hour
                lights[h], equip[h] = 0.5 * (0.25 + 0.05), 0.5 * (0.35 + 0.15)
            else:
                lights[h], equip[h] = 0.05, 0.15
        else:
            if 9 <= hod < 11:
                occ[h] = 0.65
            elif 11 <= hod < 14:
                occ[h] = 0.90
            elif 14 <= hod < 16:
                occ[h] = 0.85
            elif hod == 16:
                occ[h] = 0.50

            if hod < 8:
                lights[h], equip[h] = 0.05, 0.15
            elif hod == 8:
                lights[h], equip[h] = 0.5 * (0.05 + 0.80), 0.5 * (0.15 + 0.70)
            elif 9 <= hod < 17:
                lights[h], equip[h] = 0.80, 0.70
            elif hod == 17:
                lights[h], equip[h] = 0.5 * (0.80 + 0.05), 0.5 * (0.70 + 0.15)
            else:
                lights[h], equip[h] = 0.05, 0.15

    return {"occupancy_frac": occ, "lighting_frac": lights, "equipment_frac": equip}


def scale_moisture_buffer(base: MuseumROMConfig, factor: float) -> MuseumROMConfig:
    """Return a copy of ``base`` with every zone's ``m_buffer_kg`` scaled by ``factor`` (> 0)."""
    if factor <= 0.0:
        raise ValueError(f"factor must be > 0, got {factor}.")
    zones = tuple(replace(z, m_buffer_kg=z.m_buffer_kg * factor) for z in base.zones)
    env = replace(
        base.envelope,
        moisture_buffer_multiplier=base.envelope.moisture_buffer_multiplier * factor,
    )
    return replace(base, tier=f"{base.tier}_buf{factor:.2g}x", envelope=env, zones=zones)


def make_weak_buffer_config(base: MuseumROMConfig) -> MuseumROMConfig:
    """Restore the original S1.1 uncalibrated weak-buffer values as a sensitivity lower bound."""
    zones = tuple(
        replace(z, m_buffer_kg=float(z.weak_m_buffer_kg))
        if z.weak_m_buffer_kg is not None
        else replace(z, m_buffer_kg=z.m_buffer_kg * 0.1)
        for z in base.zones
    )
    return replace(base, tier=f"{base.tier}_weak_buffer", zones=zones)


def with_smooth_betas(
    base: MuseumROMConfig,
    smooth_beta_t: float,
    smooth_beta_w: float,
) -> MuseumROMConfig:
    """Return a copy of ``base`` with updated softplus deadband sharpness parameters."""
    if smooth_beta_t <= 0.0 or smooth_beta_w <= 0.0:
        raise ValueError("smooth_beta_t and smooth_beta_w must be > 0.")
    hv = replace(base.hvac, smooth_beta_t=float(smooth_beta_t), smooth_beta_w=float(smooth_beta_w))
    return replace(base, hvac=hv)


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
    def _torch_wsat_from_t(t_c: torch.Tensor, pressure_pa: float) -> torch.Tensor:
        t_safe = torch.clamp(t_c, min=-80.0, max=80.0)
        p_w = torch.clamp(610.94 * torch.exp(17.625 * t_safe / (t_safe + 243.04)), min=0.0, max=0.95 * pressure_pa)
        return 0.621945 * p_w / (pressure_pa - p_w)

    @torch.jit.script
    def _torch_coupled_deadband_solve(
        inv_mat: torch.Tensor,
        eff: torch.Tensor,
        sub_mat: torch.Tensor,
        x_free: torch.Tensor,
        sp_lo: torch.Tensor,
        sp_hi: torch.Tensor,
        beta: float,
        cap_pos: torch.Tensor,
        cap_neg: torch.Tensor,
        root0_pos: torch.Tensor,
        root0_neg: torch.Tensor,
        eps_cap_sq: float,
        eps_pos_sq: float,
        eye5: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Exact 5-zone coupled IdealLoads complementarity solve using precomputed sub-matrices."""
        s_lo = torch.sigmoid(beta * (sp_lo - x_free))
        s_hi = torch.sigmoid(beta * (x_free - sp_hi))
        g = s_lo + s_hi
        d = F.softplus(sp_lo - x_free, beta, 20.0) - F.softplus(x_free - sp_hi, beta, 20.0)
        m_sys = eye5 + g.unsqueeze(-1) * sub_mat
        rhs = (g * eff * d).unsqueeze(-1)
        u_unc = torch.linalg.solve(m_sys, rhs).squeeze(-1)
        u_pos_raw = g * 0.5 * (u_unc + torch.sqrt(u_unc * u_unc + eps_pos_sq))
        u_neg_raw = g * 0.5 * (-u_unc + torch.sqrt(u_unc * u_unc + eps_pos_sq))
        u_pos = _torch_smooth_cap(u_pos_raw, cap_pos, root0_pos, eps_cap_sq)
        u_neg = _torch_smooth_cap(u_neg_raw, cap_neg, root0_neg, eps_cap_sq)
        x_next = x_free + torch.bmm(inv_mat, (u_pos - u_neg).unsqueeze(-1)).squeeze(-1)
        return x_next, u_pos, u_neg

    @torch.jit.script
    def _torch_state_rollout(
        t_a: torch.Tensor,
        t_m: torch.Tensor,
        w_a: torch.Tensor,
        w_b: torch.Tensor,
        src_t: torch.Tensor,
        src_m: torch.Tensor,
        src_w: torch.Tensor,
        t_out: torch.Tensor,
        w_out: torch.Tensor,
        m_vent: torch.Tensor,
        inv_at_all: torch.Tensor,
        eff_at_all: torch.Tensor,
        sub_at_all: torch.Tensor,
        inv_aw_all: torch.Tensor,
        eff_aw_all: torch.Tensor,
        sub_aw_all: torch.Tensor,
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
        cp_air: float,
        t_sup_cool_min_c: float,
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
        torch.Tensor,
    ]:
        T_len = src_t.shape[1]
        const_mat = inv_at_all.shape[1] == 1
        const_vent = m_vent.shape[1] == 1
        inv_at0 = inv_at_all[:, 0]
        eff_at0 = eff_at_all[:, 0]
        sub_at0 = sub_at_all[:, 0]
        inv_aw0 = inv_aw_all[:, 0]
        eff_aw0 = eff_aw_all[:, 0]
        sub_aw0 = sub_aw_all[:, 0]
        m_vent0 = m_vent[:, 0]
        eye5 = torch.eye(src_t.shape[2], dtype=src_t.dtype, device=src_t.device).unsqueeze(0)

        src_t_u = src_t.unbind(1)
        src_m_u = src_m.unbind(1)
        src_w_u = src_w.unbind(1)
        t_out_u = t_out.unsqueeze(-1).unbind(1)
        w_out_u = w_out.unsqueeze(-1).unbind(1)
        t_h_sp_u = t_h_sp.unbind(1)
        t_c_sp_u = t_c_sp.unbind(1)
        rh_h_sp_u = rh_h_sp.unbind(1)
        rh_d_sp_u = rh_d_sp.unbind(1)
        m_vent_u = m_vent.unbind(1)
        inv_at_u = inv_at_all.unbind(1)
        eff_at_u = eff_at_all.unbind(1)
        sub_at_u = sub_at_all.unbind(1)
        inv_aw_u = inv_aw_all.unbind(1)
        eff_aw_u = eff_aw_all.unbind(1)
        sub_aw_u = sub_aw_all.unbind(1)

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
        m_cond_list: list[torch.Tensor] = []
        w_ds_list: list[torch.Tensor] = []

        for t in range(T_len):
            inv_at = inv_at0 if const_mat else inv_at_u[t]
            eff_at = eff_at0 if const_mat else eff_at_u[t]
            sub_at = sub_at0 if const_mat else sub_at_u[t]
            inv_aw = inv_aw0 if const_mat else inv_aw_u[t]
            eff_aw = eff_aw0 if const_mat else eff_aw_u[t]
            sub_aw = sub_aw0 if const_mat else sub_aw_u[t]
            m_vent_t = m_vent0 if const_vent else m_vent_u[t]

            term_m = t_m * c_m_dt_over_dm + src_m_u[t]
            r_t = t_a * c_a_dt + src_t_u[t] + h_am * term_m
            t_a_free = torch.bmm(inv_at, r_t.unsqueeze(-1)).squeeze(-1)

            term_b = w_b * m_b_dt_over_db
            r_w = w_a * m_a_dt + src_w_u[t] + k_ab * term_b

            if not hvac_active:
                zeros = torch.zeros_like(t_a_free)
                w_a_free = torch.bmm(inv_aw, r_w.unsqueeze(-1)).squeeze(-1)
                t_a = t_a_free
                w_a = w_a_free
                q_sh = zeros
                q_sc = zeros
                m_hu = zeros
                m_de = zeros
                m_cond = zeros
                w_dehum_sp = _torch_w_from_t_rh(t_a, rh_d_sp_u[t], pressure_pa)
            else:
                t_a, q_sh, q_sc = _torch_coupled_deadband_solve(
                    inv_at,
                    eff_at,
                    sub_at,
                    t_a_free,
                    t_h_sp_u[t],
                    t_c_sp_u[t],
                    smooth_beta_t,
                    q_heat_max,
                    q_cool_max,
                    root0_qh,
                    root0_qc,
                    1.0,
                    1.0e-2,
                    eye5,
                )

                if t_sup_cool_min_c > -100.0:
                    q_oa_cool = m_vent_t * cp_air * (t_out_u[t] - t_a)
                    q_zone_cool = F.softplus(q_sc - q_oa_cool, 0.02, 20.0)
                    dt_sup_max = torch.clamp(t_a - t_sup_cool_min_c, min=0.5)
                    m_sup_req = q_zone_cool / (cp_air * dt_sup_max)
                    active_cool = torch.sigmoid(0.05 * (q_sc - 5.0))
                    m_sup = torch.maximum(m_sup_req, m_vent_t * active_cool)
                    m_ret = F.softplus(m_sup - m_vent_t, 500.0, 20.0)
                    m_oa_coil = m_sup - m_ret
                    t_sup = t_a - q_zone_cool / (cp_air * torch.clamp(m_sup, min=1.0e-6))
                    w_sup_sat = _torch_wsat_from_t(t_sup, pressure_pa)
                    w_mix = (m_oa_coil * w_out_u[t] + m_ret * w_a) / torch.clamp(m_sup, min=1.0e-6)
                    m_cond = active_cool * m_sup * F.softplus(w_mix - w_sup_sat, smooth_beta_w, 20.0)
                else:
                    m_cond = torch.zeros_like(q_sc)

                w_a_free = torch.bmm(inv_aw, (r_w - m_cond).unsqueeze(-1)).squeeze(-1)
                w_hum_sp = _torch_w_from_t_rh(t_a, rh_h_sp_u[t], pressure_pa)
                w_dehum_sp = _torch_w_from_t_rh(t_a, rh_d_sp_u[t], pressure_pa)
                w_a_raw, m_hu, m_de = _torch_coupled_deadband_solve(
                    inv_aw,
                    eff_aw,
                    sub_aw,
                    w_a_free,
                    w_hum_sp,
                    w_dehum_sp,
                    smooth_beta_w,
                    m_hum_max,
                    m_dehum_max,
                    root0_mh,
                    root0_md,
                    1.0e-12,
                    1.0e-14,
                    eye5,
                )
                w_a = torch.clamp(w_a_raw, min=1.0e-7)

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
            m_cond_list.append(m_cond)
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
            torch.stack(m_cond_list, dim=1),
            torch.stack(w_ds_list, dim=1),
        )

    def _torch_coupled_step_vec(
        t_a: torch.Tensor,
        t_m: torch.Tensor,
        w_a: torch.Tensor,
        w_b: torch.Tensor,
        src_t: torch.Tensor,
        src_m: torch.Tensor,
        src_w: torch.Tensor,
        t_out: torch.Tensor,
        w_out: torch.Tensor,
        m_vent_t: torch.Tensor,
        inv_at: torch.Tensor,
        eff_at: torch.Tensor,
        sub_at: torch.Tensor,
        inv_aw: torch.Tensor,
        eff_aw: torch.Tensor,
        sub_aw: torch.Tensor,
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
        cp_air: float,
        t_sup_cool_min_c: float,
    ) -> tuple[torch.Tensor, ...]:
        """Single vectorized coupled step over flattened batch ``M = B * T`` for exact adjoint."""
        eye5 = torch.eye(t_a.shape[-1], dtype=t_a.dtype, device=t_a.device).unsqueeze(0)
        root0_qh = torch.sqrt(q_heat_max * q_heat_max + 1.0)
        root0_qc = torch.sqrt(q_cool_max * q_cool_max + 1.0)
        root0_mh = torch.sqrt(m_hum_max * m_hum_max + 1.0e-12)
        root0_md = torch.sqrt(m_dehum_max * m_dehum_max + 1.0e-12)

        term_m = t_m * c_m_dt_over_dm + src_m
        r_t = t_a * c_a_dt + src_t + h_am * term_m
        t_a_free = torch.bmm(inv_at, r_t.unsqueeze(-1)).squeeze(-1)

        t_a_next, q_sh, q_sc = _torch_coupled_deadband_solve(
            inv_at,
            eff_at,
            sub_at,
            t_a_free,
            t_h_sp,
            t_c_sp,
            smooth_beta_t,
            q_heat_max,
            q_cool_max,
            root0_qh,
            root0_qc,
            1.0,
            1.0e-2,
            eye5,
        )

        if t_sup_cool_min_c > -100.0:
            q_oa_cool = m_vent_t * cp_air * (t_out.unsqueeze(-1) - t_a_next)
            q_zone_cool = F.softplus(q_sc - q_oa_cool, 0.02, 20.0)
            dt_sup_max = torch.clamp(t_a_next - t_sup_cool_min_c, min=0.5)
            m_sup_req = q_zone_cool / (cp_air * dt_sup_max)
            active_cool = torch.sigmoid(0.05 * (q_sc - 5.0))
            m_sup = torch.maximum(m_sup_req, m_vent_t * active_cool)
            m_ret = F.softplus(m_sup - m_vent_t, 500.0, 20.0)
            m_oa_coil = m_sup - m_ret
            t_sup = t_a_next - q_zone_cool / (cp_air * torch.clamp(m_sup, min=1.0e-6))
            w_sup_sat = _torch_wsat_from_t(t_sup, pressure_pa)
            w_mix = (m_oa_coil * w_out.unsqueeze(-1) + m_ret * w_a) / torch.clamp(m_sup, min=1.0e-6)
            m_cond = active_cool * m_sup * F.softplus(w_mix - w_sup_sat, smooth_beta_w, 20.0)
        else:
            m_cond = torch.zeros_like(q_sc)

        term_b = w_b * m_b_dt_over_db
        r_w = w_a * m_a_dt + src_w + k_ab * term_b
        w_a_free = torch.bmm(inv_aw, (r_w - m_cond).unsqueeze(-1)).squeeze(-1)
        w_hum_sp = _torch_w_from_t_rh(t_a_next, rh_h_sp, pressure_pa)
        w_dehum_sp = _torch_w_from_t_rh(t_a_next, rh_d_sp, pressure_pa)
        w_a_raw, m_hu, m_de = _torch_coupled_deadband_solve(
            inv_aw,
            eff_aw,
            sub_aw,
            w_a_free,
            w_hum_sp,
            w_dehum_sp,
            smooth_beta_w,
            m_hum_max,
            m_dehum_max,
            root0_mh,
            root0_md,
            1.0e-12,
            1.0e-14,
            eye5,
        )
        w_a_next = torch.clamp(w_a_raw, min=1.0e-7)
        t_m_next = alpha_m * t_a_next + term_m
        w_b_next = alpha_b * w_a_next + term_b
        return (
            t_a_next,
            t_m_next,
            w_a_next,
            w_b_next,
            t_a_free,
            w_a_free,
            q_sh,
            q_sc,
            m_hu,
            m_de,
            m_cond,
            w_dehum_sp,
        )

    class _MuseumRolloutFn(torch.autograd.Function):
        """Fast nograd forward + time-parallel batched VJP backward over T-step rollout."""

        @staticmethod
        def forward(ctx: Any, *args: Any) -> tuple[torch.Tensor, ...]:
            tensors = args[:20]
            consts = args[20]
            (
                t_a0,
                t_m0,
                w_a0,
                w_b0,
                src_t,
                src_m,
                src_w,
                t_out,
                w_out,
                m_vent_roll,
                inv_at_all,
                eff_at_all,
                sub_at_all,
                inv_aw_all,
                eff_aw_all,
                sub_aw_all,
                t_h_sp,
                t_c_sp,
                rh_h_sp,
                rh_d_sp,
            ) = tensors
            with torch.no_grad():
                outputs = _torch_state_rollout(
                    t_a0,
                    t_m0,
                    w_a0,
                    w_b0,
                    src_t,
                    src_m,
                    src_w,
                    t_out,
                    w_out,
                    m_vent_roll,
                    inv_at_all,
                    eff_at_all,
                    sub_at_all,
                    inv_aw_all,
                    eff_aw_all,
                    sub_aw_all,
                    t_h_sp,
                    t_c_sp,
                    rh_h_sp,
                    rh_d_sp,
                    *consts,
                )
            ctx.save_for_backward(*tensors, outputs[0], outputs[1], outputs[2], outputs[3])
            ctx.consts = consts
            return outputs

        @staticmethod
        def backward(ctx: Any, *grads_out: torch.Tensor) -> tuple[Any, ...]:
            saved = ctx.saved_tensors
            tensors = saved[:20]
            t_a_all, t_m_all, w_a_all, w_b_all = saved[20:24]
            t_a0, t_m0, w_a0, w_b0 = tensors[:4]
            consts = ctx.consts
            c_m_dt_over_dm = consts[1]
            alpha_m = consts[3]
            m_b_dt_over_db = consts[5]
            alpha_b = consts[7]

            B, T_len, N = t_a_all.shape
            M = B * T_len
            dtype = t_a_all.dtype
            device = t_a_all.device

            g_states = torch.cat(
                [
                    (grads_out[k] if grads_out[k] is not None else torch.zeros_like(t_a_all))
                    for k in range(4)
                ],
                dim=-1,
            )  # (B, T, 4*N)

            with torch.enable_grad():
                prev_ta = torch.cat([t_a0.unsqueeze(1), t_a_all[:, :-1]], dim=1).reshape(M, N).detach().requires_grad_(True)
                prev_tm = torch.cat([t_m0.unsqueeze(1), t_m_all[:, :-1]], dim=1).reshape(M, N).detach().requires_grad_(True)
                prev_wa = torch.cat([w_a0.unsqueeze(1), w_a_all[:, :-1]], dim=1).reshape(M, N).detach().requires_grad_(True)
                prev_wb = torch.cat([w_b0.unsqueeze(1), w_b_all[:, :-1]], dim=1).reshape(M, N).detach().requires_grad_(True)

                flat_x: list[torch.Tensor] = []
                is_full_time: list[bool] = []
                active_x_tensors: list[torch.Tensor] = []
                active_x_slots: list[int] = []

                for idx in range(4, 20):
                    raw = tensors[idx]
                    full_t = raw.shape[1] == T_len
                    is_full_time.append(full_t)
                    exp = raw if full_t else raw.expand((B, T_len) + raw.shape[2:])
                    fl = exp.reshape((M,) + raw.shape[2:]).detach()
                    if ctx.needs_input_grad[idx]:
                        fl = fl.requires_grad_(True)
                        active_x_tensors.append(fl)
                        active_x_slots.append(idx - 4)
                    flat_x.append(fl)

                step_outs = _torch_coupled_step_vec(
                    prev_ta,
                    prev_tm,
                    prev_wa,
                    prev_wb,
                    *flat_x,
                    *consts[:-1],
                )
                ta_n, tm_n, wa_n, wb_n = step_outs[:4]
                aux_outs = step_outs[4:]

                # Pass 1: Auxiliary direct contributions to (prev_s, active_x)
                active_aux_y: list[torch.Tensor] = []
                active_aux_g: list[torch.Tensor] = []
                for k, y_k in enumerate(aux_outs):
                    gk = grads_out[4 + k]
                    if gk is not None:
                        active_aux_y.append(y_k)
                        active_aux_g.append(gk.reshape(M, N))

                dx_flat: list[torch.Tensor | None] = [None] * 16
                if active_aux_y:
                    aux_targets = [prev_ta, prev_tm, prev_wa, prev_wb, *active_x_tensors]
                    aux_grads = torch.autograd.grad(
                        active_aux_y,
                        aux_targets,
                        active_aux_g,
                        retain_graph=True,
                        allow_unused=True,
                    )
                    u_prev_flat = torch.cat(
                        [
                            (aux_grads[i] if aux_grads[i] is not None else torch.zeros((M, N), dtype=dtype, device=device))
                            for i in range(4)
                        ],
                        dim=-1,
                    ).reshape(B, T_len, 4 * N)
                    for pos, slot in enumerate(active_x_slots):
                        g_ax = aux_grads[4 + pos]
                        if g_ax is not None:
                            dx_flat[slot] = g_ax
                else:
                    u_prev_flat = torch.zeros((B, T_len, 4 * N), dtype=dtype, device=device)

                # Pass 2: 2*N batched Jacobian of (ta_n, wa_n) wrt (prev_ta, prev_tm, prev_wa, prev_wb)
                eye_2n = torch.eye(2 * N, dtype=dtype, device=device).unsqueeze(1).expand(2 * N, M, 2 * N)
                j_parts = torch.autograd.grad(
                    torch.cat([ta_n, wa_n], dim=-1),
                    (prev_ta, prev_tm, prev_wa, prev_wb),
                    eye_2n,
                    is_grads_batched=True,
                    retain_graph=bool(active_x_tensors),
                    allow_unused=True,
                )
                j_cat = torch.cat(
                    [
                        (jp if jp is not None else torch.zeros((2 * N, M, N), dtype=dtype, device=device))
                        for jp in j_parts
                    ],
                    dim=-1,
                )  # (2*N, M, 4*N)
                j_mats = j_cat.permute(1, 0, 2).reshape(B, T_len, 2 * N, 4 * N)

                # Pass 3: Exact reverse sweep over t = T-1 .. 0
                lam_all = torch.empty((B, T_len, 4 * N), dtype=dtype, device=device)
                carry_s = torch.zeros((B, 4 * N), dtype=dtype, device=device)
                for t in range(T_len - 1, -1, -1):
                    lam_t = g_states[:, t] + carry_s
                    lam_all[:, t] = lam_t
                    l_ta = lam_t[:, :N]
                    l_tm = lam_t[:, N : 2 * N]
                    l_wa = lam_t[:, 2 * N : 3 * N]
                    l_wb = lam_t[:, 3 * N : 4 * N]
                    v_hat = torch.cat([l_ta + alpha_m * l_tm, l_wa + alpha_b * l_wb], dim=-1)
                    back_s = torch.bmm(v_hat.unsqueeze(1), j_mats[:, t]).squeeze(1)
                    back_s[:, N : 2 * N] = back_s[:, N : 2 * N] + c_m_dt_over_dm * l_tm
                    back_s[:, 3 * N : 4 * N] = back_s[:, 3 * N : 4 * N] + m_b_dt_over_db * l_wb
                    carry_s = back_s + u_prev_flat[:, t]

                g_s0 = carry_s
                g_ta0 = g_s0[:, :N] if ctx.needs_input_grad[0] else None
                g_tm0 = g_s0[:, N : 2 * N] if ctx.needs_input_grad[1] else None
                g_wa0 = g_s0[:, 2 * N : 3 * N] if ctx.needs_input_grad[2] else None
                g_wb0 = g_s0[:, 3 * N : 4 * N] if ctx.needs_input_grad[3] else None

                # Pass 4: Exact state-mediated gradients wrt active_x_tensors
                if active_x_tensors:
                    lam_flat = lam_all.reshape(M, 4 * N)
                    s_grads = torch.autograd.grad(
                        [ta_n, tm_n, wa_n, wb_n],
                        active_x_tensors,
                        [
                            lam_flat[:, :N],
                            lam_flat[:, N : 2 * N],
                            lam_flat[:, 2 * N : 3 * N],
                            lam_flat[:, 3 * N : 4 * N],
                        ],
                        allow_unused=True,
                    )
                    for pos, slot in enumerate(active_x_slots):
                        gs = s_grads[pos]
                        if gs is not None:
                            cur = dx_flat[slot]
                            dx_flat[slot] = gs if cur is None else (cur + gs)

                gx_out: list[torch.Tensor | None] = []
                for slot in range(16):
                    g_fl = dx_flat[slot]
                    if g_fl is None:
                        gx_out.append(None)
                    else:
                        orig = tensors[4 + slot]
                        g_reshaped = g_fl.reshape((B, T_len) + orig.shape[2:])
                        if not is_full_time[slot]:
                            g_reshaped = g_reshaped.sum(dim=1, keepdim=True)
                        gx_out.append(g_reshaped)

            return (g_ta0, g_tm0, g_wa0, g_wb0, *gx_out, None)


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

        # ASHRAE 62.1 mechanical outdoor-air ventilation mass flow coefficients [kg_da/s]
        self.m_vent_person_design_np = c.rho_air_kg_m3 * env.oa_flow_per_person_m3_s * self.design_people_np
        self.m_vent_area_design_np = c.rho_air_kg_m3 * env.oa_flow_per_area_m3_s_m2 * floor_areas

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
        m_vent_kg_s: ArrayLike | None = None,
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
                m_vent_kg_s,
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
                m_vent_kg_s=m_vent_kg_s,
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
            m_vent_kg_s=m_vent_kg_s,
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
        m_vent_kg_s: ArrayLike | None,
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
        if m_vent_kg_s is not None:
            m_vent = _btz(m_vent_kg_s, 0.0)
        elif not hvac_active:
            m_vent = np.zeros((B, T, N), dtype=np.float64)
        else:
            occ_vent = occ if occupancy_frac is not None else _btz(
                museum_operating_schedules(T)["occupancy_frac"], 0.0
            )
            m_vent = (
                occ_vent * self.m_vent_person_design_np[None, None, :]
                + self.m_vent_area_design_np[None, None, :]
            )
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
            "m_vent": m_vent,
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
        m_vent_kg_s: Any,
        m_infil_kg_s: Any,
        q_sens_heat: Any,
        q_sens_cool: Any,
        m_hum: Any,
        m_dehum: Any,
        m_cond_coil: Any,
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

            # Process humidity drop across the cooling coil: 2e-4 kg/kg (0.2 g/kg) floor avoids 0/0
            # singularity when w_a_free approaches w_coil while vanishing as m_dehum -> 0 and
            # changing active-dehumidification coil airflow by < ~15% only near tiny < 1 g/kg drops.
            # Note: ONLY explicit humidistat dehumidification (m_dehum) induces coil subcooling below
            # T_a and potential reheat; coincidental condensation (m_cond_coil) shares sensible cooling
            # already captured in q_sens_cool and adds strictly its latent condensation enthalpy.
            delta_w_coil = _softplus(w_a_free - w_coil, beta=hv.smooth_beta_w) + 2.0e-4
            m_proc = m_dehum / delta_w_coil
            delta_t_coil = _softplus(t_a_free - t_coil, beta=hv.smooth_beta_t)

            t_cond_ref = hv.t_sup_cool_min_c if hv.t_sup_cool_min_c is not None else 13.0
            h_fg_cond = float(latent_heat_vaporization_j_per_kg(t_cond_ref))
            q_dehum_latent = m_dehum * latent_heat_vaporization_j_per_kg(t_coil) + m_cond_coil * h_fg_cond
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
            "m_vent_kg_s": m_vent_kg_s,
            "m_infil_kg_s": m_infil_kg_s,
            "q_sens_heat_w": q_sens_heat,
            "q_sens_cool_w": q_sens_cool,
            "q_hum_w": q_hum,
            "m_hum_kg_s": m_hum,
            "m_dehum_kg_s": m_dehum + m_cond_coil,
            "m_dehum_explicit_kg_s": m_dehum,
            "m_cond_coil_kg_s": m_cond_coil,
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
            "e_dehum_latent_kwh": q_dehum_latent * w_to_kwh,
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
        m_vent_kg_s: ArrayLike | None,
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
            m_vent_kg_s=m_vent_kg_s,
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

        # Time-varying infiltration + mechanical outdoor ventilation & batched inversions (B, T, N, N)
        m_inf = prep["inf_scale"][:, :, None] * self.m_inf_design_np[None, None, :]
        m_vent = prep["m_vent"]
        m_oa = m_inf + m_vent
        h_oa = cp * m_oa

        diag_t = (c_a_dt + self.h_ext_np + h_am_eff)[None, None, :] + h_oa
        diag_w = (m_a_dt + k_ab_eff)[None, None, :] + m_oa

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
            "m_cond_coil_kg_s",
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
        hv = self.config.hvac
        t_sup_min = float(hv.t_sup_cool_min_c) if hv.t_sup_cool_min_c is not None else -999.0

        for t in range(T):
            inv_at = inv_at_all[:, t]
            inv_aw = inv_aw_all[:, t]

            term_m = (t_m * c_m_dt + t_gnd[:, t : t + 1] * self.h_ground_np + q_mass_arr[:, t]) / d_m
            r_t = (
                t_a * c_a_dt
                + t_out[:, t : t + 1] * (self.h_ext_np + h_oa[:, t])
                + self.h_am_np * term_m
                + q_air_arr[:, t]
            )
            t_a_free = np.einsum("bij,bj->bi", inv_at, r_t)

            term_b = (w_b * m_b_dt) / d_b
            r_w = (
                w_a * m_a_dt
                + w_out[:, t : t + 1] * m_oa[:, t]
                + self.k_ab_np * term_b
                + m_vap_arr[:, t]
            )

            if not hvac_active:
                zeros = np.zeros_like(t_a_free)
                w_a_free = np.einsum("bij,bj->bi", inv_aw, r_w)
                t_a_next = t_a_free
                w_a_next = w_a_free
                q_sh = zeros
                q_sc = zeros
                m_hu = zeros
                m_de = zeros
                m_cond = zeros
                w_dehum_sp = humidity_ratio_from_temp_rh(t_a_next, rh_d_sp[:, t], pressure_pa=pressure_pa)
            else:
                t_a_next, q_sh, q_sc = _coupled_deadband_solve_numpy(
                    inv_at,
                    t_a_free,
                    t_h_sp[:, t],
                    t_c_sp[:, t],
                    float(hv.smooth_beta_t),
                    self.q_heat_max_np,
                    self.q_cool_max_np,
                    1.0,
                    1.0e-2,
                )

                if t_sup_min > -100.0:
                    q_oa_cool = m_vent[:, t] * cp * (t_out[:, t : t + 1] - t_a_next)
                    q_zone_cool = _softplus(q_sc - q_oa_cool, beta=0.02)
                    dt_sup_max = np.maximum(t_a_next - t_sup_min, 0.5)
                    m_sup_req = q_zone_cool / (cp * dt_sup_max)
                    active_cool = _sigmoid_np(0.05 * (q_sc - 5.0))
                    m_sup = np.maximum(m_sup_req, m_vent[:, t] * active_cool)
                    m_ret = _softplus(m_sup - m_vent[:, t], beta=500.0)
                    m_oa_coil = m_sup - m_ret
                    t_sup = t_a_next - q_zone_cool / (cp * np.maximum(m_sup, 1.0e-6))
                    w_sup_sat = humidity_ratio_from_temp_rh(t_sup, 100.0, pressure_pa=pressure_pa)
                    w_mix = (m_oa_coil * w_out[:, t : t + 1] + m_ret * w_a) / np.maximum(m_sup, 1.0e-6)
                    m_cond = active_cool * m_sup * _softplus(w_mix - w_sup_sat, beta=float(hv.smooth_beta_w))
                else:
                    m_cond = np.zeros_like(q_sc)

                w_a_free = np.einsum("bij,bj->bi", inv_aw, r_w - m_cond)
                w_hum_sp = humidity_ratio_from_temp_rh(t_a_next, rh_h_sp[:, t], pressure_pa=pressure_pa)
                w_dehum_sp = humidity_ratio_from_temp_rh(t_a_next, rh_d_sp[:, t], pressure_pa=pressure_pa)
                w_a_raw, m_hu, m_de = _coupled_deadband_solve_numpy(
                    inv_aw,
                    w_a_free,
                    w_hum_sp,
                    w_dehum_sp,
                    float(hv.smooth_beta_w),
                    self.m_hum_max_np,
                    self.m_dehum_max_np,
                    1.0e-6,
                    1.0e-14,
                )
                w_a_next = np.maximum(w_a_raw, 1.0e-7)

            t_a = t_a_next
            w_a = w_a_next
            t_m = alpha_m * t_a + term_m
            w_b = alpha_b * w_a + term_b

            buffers["t_air_c"][:, t] = t_a
            buffers["t_mass_c"][:, t] = t_m
            buffers["w_air_kg_kg"][:, t] = w_a
            buffers["w_buffer_kg_kg"][:, t] = w_b
            buffers["t_a_free"][:, t] = t_a_free
            buffers["w_a_free"][:, t] = w_a_free
            buffers["q_sens_heat_w"][:, t] = q_sh
            buffers["q_sens_cool_w"][:, t] = q_sc
            buffers["m_hum_kg_s"][:, t] = m_hu
            buffers["m_dehum_kg_s"][:, t] = m_de
            buffers["m_cond_coil_kg_s"][:, t] = m_cond
            buffers["w_dehum_sp"][:, t] = w_dehum_sp

        return self._package_outputs(
            t_air=buffers["t_air_c"],
            t_mass=buffers["t_mass_c"],
            w_air=buffers["w_air_kg_kg"],
            w_buffer=buffers["w_buffer_kg_kg"],
            t_a_free=buffers["t_a_free"],
            w_a_free=buffers["w_a_free"],
            m_vent_kg_s=m_vent,
            m_infil_kg_s=m_inf,
            q_sens_heat=buffers["q_sens_heat_w"],
            q_sens_cool=buffers["q_sens_cool_w"],
            m_hum=buffers["m_hum_kg_s"],
            m_dehum=buffers["m_dehum_kg_s"],
            m_cond_coil=buffers["m_cond_coil_kg_s"],
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
        m_vent_kg_s: ArrayLike | None,
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
        if m_vent_kg_s is not None:
            m_vent = _btz(m_vent_kg_s, 0.0)
        elif not hvac_active:
            m_vent = torch.zeros((B, T, N), dtype=dtype, device=device)
        else:
            occ_vent = (
                occ
                if occupancy_frac is not None
                else _btz(museum_operating_schedules(T)["occupancy_frac"], 0.0)
            )
            m_vent = (
                occ_vent * _as_t(self.m_vent_person_design_np).view(1, 1, N)
                + _as_t(self.m_vent_area_design_np).view(1, 1, N)
            )
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
        constant_vent = (not hvac_active and m_vent_kg_s is None) or isinstance(m_vent_kg_s, (int, float))
        constant_oa = constant_inf and constant_vent
        eye = torch.eye(N, dtype=dtype, device=device)
        if constant_oa:
            m_vent0 = torch.zeros((1, 1, N), dtype=dtype, device=device) if m_vent_kg_s is None else m_vent[:1, :1, :]
            m_vent_roll = m_vent0.expand(B, 1, N)
            m_oa_0 = m_inf_design.view(1, 1, N) + m_vent0
            m_inf_all = m_inf_design.view(1, 1, N).expand(B, T, N)
            m_oa_all = m_oa_0
            h_oa_all = c.cp_air_j_kg_k * m_oa_all
            mat_t_const = lap_t + torch.diag(c_a_dt + h_ext + h_am_eff + c.cp_air_j_kg_k * m_oa_0.view(N))
            mat_w_const = lap_w + torch.diag(m_a_dt + k_ab_eff + m_oa_0.view(N))
            inv_at_all = torch.linalg.inv(mat_t_const).view(1, 1, N, N).expand(B, 1, N, N)
            inv_aw_all = torch.linalg.inv(mat_w_const).view(1, 1, N, N).expand(B, 1, N, N)
        else:
            m_vent_roll = m_vent
            m_inf_all = inf_scale.unsqueeze(-1) * m_inf_design.view(1, 1, N)
            m_oa_all = m_inf_all + m_vent
            h_oa_all = c.cp_air_j_kg_k * m_oa_all
            diag_t = (c_a_dt + h_ext + h_am_eff).view(1, 1, N) + h_oa_all
            diag_w = (m_a_dt + k_ab_eff).view(1, 1, N) + m_oa_all
            mat_t = lap_t.view(1, 1, N, N) + diag_t.unsqueeze(-1) * eye.view(1, 1, N, N)
            mat_w = lap_w.view(1, 1, N, N) + diag_w.unsqueeze(-1) * eye.view(1, 1, N, N)
            inv_at_all = torch.linalg.inv(mat_t)
            inv_aw_all = torch.linalg.inv(mat_w)

        eff_at_all = 1.0 / torch.diagonal(inv_at_all, dim1=-2, dim2=-1)
        sub_at_all = eff_at_all.unsqueeze(-1) * inv_at_all - eye.view(1, 1, N, N)
        eff_aw_all = 1.0 / torch.diagonal(inv_aw_all, dim1=-2, dim2=-1)
        sub_aw_all = eff_aw_all.unsqueeze(-1) * inv_aw_all - eye.view(1, 1, N, N)

        src_m = (t_gnd.unsqueeze(-1) * h_ground.view(1, 1, N) + q_mass) / d_m.view(1, 1, N)
        src_t = t_out.unsqueeze(-1) * (h_ext.view(1, 1, N) + h_oa_all) + q_air
        src_w = w_out.unsqueeze(-1) * m_oa_all + m_vapor

        t_sup_min = float(hv.t_sup_cool_min_c) if hv.t_sup_cool_min_c is not None else -999.0
        consts = (
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
            float(c.cp_air_j_kg_k),
            t_sup_min,
            bool(hvac_active),
        )
        tensor_args = (
            t_a,
            t_m,
            w_a,
            w_b,
            src_t,
            src_m,
            src_w,
            t_out,
            w_out,
            m_vent_roll,
            inv_at_all,
            eff_at_all,
            sub_at_all,
            inv_aw_all,
            eff_aw_all,
            sub_aw_all,
            t_h_sp,
            t_c_sp,
            rh_h_sp,
            rh_d_sp,
        )
        if hvac_active and torch.is_grad_enabled() and any(x.requires_grad for x in tensor_args):
            rollout_out = _MuseumRolloutFn.apply(*tensor_args, consts)
        else:
            rollout_out = _torch_state_rollout(*tensor_args, *consts)
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
            m_cond_coil,
            w_dehum_sp,
        ) = rollout_out

        return self._package_outputs(
            t_air=t_air,
            t_mass=t_mass,
            w_air=w_air,
            w_buffer=w_buffer,
            t_a_free=t_a_free,
            w_a_free=w_a_free,
            m_vent_kg_s=m_vent,
            m_infil_kg_s=m_inf_all,
            q_sens_heat=q_sens_heat,
            q_sens_cool=q_sens_cool,
            m_hum=m_hum,
            m_dehum=m_dehum,
            m_cond_coil=m_cond_coil,
            w_dehum_sp=w_dehum_sp,
            hvac_active=hvac_active,
            dt_hours=dt_hours,
            pressure_pa=pressure_pa,
            batched=batched,
            use_torch=True,
        )
