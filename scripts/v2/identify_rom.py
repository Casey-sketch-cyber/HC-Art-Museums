#!/usr/bin/env python3
"""Layer A vs Layer B (EnergyPlus 23.2) system identification & cross-climate validation (Task S1.3).

Workflow:
1. Generate rich multi-regime excitation sequence ``id_rich`` plus three unseen
   evaluation sequences (``F0``, ``wide_deadband``, ``random_perturb``), each 8760 h.
2. Run EnergyPlus 23.2 (Layer B) across ``nyc`` (identification only) and three
   unseen evaluation climates (``tampa``, ``chicago``, ``golden``) x 3 building tiers
   (``historic``, ``retrofitted``, ``modern``), caching simulation outputs cleanly.
3. For each building tier independently, identify 9 effective thermal-envelope and
   thermal-mass parameters on ``nyc / id_rich`` via damped Gauss-Newton (Levenberg-
   Marquardt) in pure NumPy. Hygroscopic buffer mass ``m_buffer_kg`` and time constant
   ``tau_buffer_h = 8.0 h`` remain strictly locked to the S1.1b calibrated YAML values.
4. Perform blind cross-climate, cross-tier, cross-sequence validation across all
   27 unseen runs (3 validation climates x 3 tiers x 3 unseen sequences) + NYC holdout,
   comparing Layer A net loads vs Layer B Supply Air loads and zone-averaged/zone-wise
   indoor temperature and relative humidity against S1.3 acceptance gates:
     * Hourly load CV-RMSE <= 30%
     * Hourly load |NMBE|  <= 10%
     * Annual load |rel|   <= 10%
     * Indoor RH RMSE      <= 5% RH
5. Export metrics JSON, identified parameters JSON, pure-Python SVG plots, and a
   concise Markdown summary under ``results_summary/S1.3/``.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.museum_v2.eplus import (  # noqa: E402
    CONTROLLED_ZONES,
    EnergyPlusResult,
    build_museum_epjson,
    find_energyplus_binary,
    run_energyplus_simulation,
)
from src.museum_v2.psychro import STANDARD_ATM_PRESSURE_PA  # noqa: E402
from src.museum_v2.rom import (  # noqa: E402
    MuseumROM,
    MuseumROMConfig,
    load_building_tier,
    museum_operating_schedules,
)
from src.museum_v2.weather import (  # noqa: E402
    EPWData,
    compute_facade_irradiance,
    epjson_ground_temperatures_hourly,
    parse_epw,
)

TIERS: tuple[str, ...] = ("historic", "retrofitted", "modern")
VAL_CLIMATES: tuple[str, ...] = ("tampa", "chicago", "golden")
ALL_CLIMATES: tuple[str, ...] = ("nyc", "tampa", "chicago", "golden")
VAL_SEQUENCES: tuple[str, ...] = ("F0", "wide_deadband", "random_perturb")

DEFAULT_EPW_FILES: dict[str, str] = {
    "nyc": "USA_NY_New.York-J.F.Kennedy.Intl.AP.744860_TMY3.epw",
    "tampa": "USA_FL_Tampa.Intl.AP.722110_TMY3.epw",
    "chicago": "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw",
    "golden": "USA_CO_Golden-NREL.724666_TMY3.epw",
}

THRESHOLDS = {
    "cv_rmse_percent": 30.0,
    "abs_nmbe_percent": 10.0,
    "abs_annual_diff_percent": 10.0,
    "rh_rmse_percent": 5.0,
}

# Physical envelope/thermal parameters identified per tier (m_buffer_kg & tau_buffer_h fixed)
PARAM_NAMES: tuple[str, ...] = (
    "u_wall_w_m2_k",
    "u_roof_w_m2_k",
    "u_window_w_m2_k",
    "u_ground_w_m2_k",
    "window_shgc",
    "solar_to_air_fraction",
    "internal_rad_fraction",
    "c_mass_scale",
    "h_am_scale",
)


def discover_epw_paths(weather_dir: str | Path | None = None) -> dict[str, Path]:
    """Locate official TMY3 EPW files for ``nyc``, ``tampa``, ``chicago``, and ``golden``."""
    search_dirs: list[Path] = []
    if weather_dir is not None:
        search_dirs.append(Path(weather_dir))
    search_dirs.append(REPO_ROOT / "Eplus-env-museum-mz-res1" / "Eplus-env-sub_run1")
    try:
        ep_bin, _ = find_energyplus_binary()
        search_dirs.append(ep_bin.parent / "WeatherData")
    except FileNotFoundError:
        pass
    search_dirs.append(REPO_ROOT / "weather")

    found: dict[str, Path] = {}
    for key, fname in DEFAULT_EPW_FILES.items():
        for d in search_dirs:
            cand = d / fname
            if cand.is_file():
                found[key] = cand
                break
        if key not in found:
            raise FileNotFoundError(
                f"EPW file '{fname}' for climate '{key}' not found in {[str(x) for x in search_dirs]}"
            )
    return found


def build_control_sequence(name: str, n_hours: int = 8760) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build deterministic ``(T, 5)`` setpoint arrays ``(t_h, t_c, rh_h, rh_d)`` for S1.3."""
    shape = (n_hours, 5)
    if name == "F0":
        return (
            np.full(shape, 21.0, dtype=np.float64),
            np.full(shape, 21.0, dtype=np.float64),
            np.full(shape, 50.0, dtype=np.float64),
            np.full(shape, 50.0, dtype=np.float64),
        )
    if name == "wide_deadband":
        return (
            np.full(shape, 18.0, dtype=np.float64),
            np.full(shape, 25.0, dtype=np.float64),
            np.full(shape, 40.0, dtype=np.float64),
            np.full(shape, 65.0, dtype=np.float64),
        )
    if name == "random_perturb":
        rng = np.random.default_rng(2026)
        block_h = 6
        n_blocks = math.ceil(n_hours / block_h)
        t_h = np.repeat(rng.uniform(18.5, 20.8, size=(n_blocks, 5)), block_h, axis=0)[:n_hours]
        dt = np.repeat(rng.uniform(1.5, 4.2, size=(n_blocks, 5)), block_h, axis=0)[:n_hours]
        t_c = t_h + dt
        rh_h = np.repeat(rng.uniform(38.0, 47.0, size=(n_blocks, 5)), block_h, axis=0)[:n_hours]
        drh = np.repeat(rng.uniform(8.0, 18.0, size=(n_blocks, 5)), block_h, axis=0)[:n_hours]
        rh_d = np.minimum(68.0, rh_h + drh)
        return t_h, t_c, rh_h, rh_d
    if name == "id_rich":
        rng = np.random.default_rng(42)
        t_h = np.empty(shape, dtype=np.float64)
        t_c = np.empty(shape, dtype=np.float64)
        rh_h = np.empty(shape, dtype=np.float64)
        rh_d = np.empty(shape, dtype=np.float64)

        # Q1 (hours 0..2159): Tight museum regime with weekly small steps
        for h in range(0, 2160):
            w = h // 168
            t_h[h] = 20.5 + 0.5 * math.sin(w)
            t_c[h] = 21.5 + 0.5 * math.sin(w)
            rh_h[h] = 48.0 + 2.0 * math.cos(w)
            rh_d[h] = 52.0 + 2.0 * math.cos(w)

        # Q2 (hours 2160..4319): Bi-weekly wide/narrow deadband & thermal steps per zone
        for h in range(2160, 4320):
            blk = (h - 2160) // 168
            if blk % 2 == 0:
                t_h[h], t_c[h] = 17.0, 26.5
                rh_h[h], rh_d[h] = 35.0, 68.0
            else:
                t_h[h], t_c[h] = 21.5, 22.0
                rh_h[h], rh_d[h] = 45.0, 50.0

        # Q3 (hours 4320..6479): Summer free-float pulses + dehumidification recovery steps
        for h in range(4320, 6480):
            blk = (h - 4320) // 120
            if blk % 3 == 0:
                t_h[h], t_c[h] = 12.0, 34.0
                rh_h[h], rh_d[h] = 20.0, 85.0
            elif blk % 3 == 1:
                t_h[h], t_c[h] = 19.0, 21.5
                rh_h[h], rh_d[h] = 40.0, 50.0
            else:
                t_h[h], t_c[h] = 22.0, 25.0
                rh_h[h], rh_d[h] = 48.0, 58.0

        # Q4 (hours 6480..8759): Orthogonal zone-independent PRBS over 12h blocks
        n_b = math.ceil((n_hours - 6480) / 12)
        th_q4 = np.repeat(rng.uniform(17.5, 21.0, size=(n_b, 5)), 12, axis=0)[: n_hours - 6480]
        tc_q4 = th_q4 + np.repeat(rng.uniform(1.0, 5.5, size=(n_b, 5)), 12, axis=0)[: n_hours - 6480]
        rh_q4 = np.repeat(rng.uniform(35.0, 48.0, size=(n_b, 5)), 12, axis=0)[: n_hours - 6480]
        rd_q4 = rh_q4 + np.repeat(rng.uniform(6.0, 22.0, size=(n_b, 5)), 12, axis=0)[: n_hours - 6480]
        t_h[6480:], t_c[6480:], rh_h[6480:], rh_d[6480:] = th_q4, tc_q4, rh_q4, rd_q4
        return t_h, t_c, rh_h, rh_d
    raise ValueError(f"Unknown sequence name '{name}'.")


def _build_eplus_kwargs(seq_name: str, th: np.ndarray, tc: np.ndarray, rhh: np.ndarray, rhd: np.ndarray) -> dict[str, Any]:
    if seq_name in ("F0", "wide_deadband"):
        return {
            "t_heat_sp_c": float(th[0, 0]),
            "t_cool_sp_c": float(tc[0, 0]),
            "rh_hum_sp_percent": float(rhh[0, 0]),
            "rh_dehum_sp_percent": float(rhd[0, 0]),
        }
    return {
        "hourly_zone_setpoints": {
            z: (th[:, i], tc[:, i], rhh[:, i], rhd[:, i])
            for i, z in enumerate(CONTROLLED_ZONES)
        }
    }


def _eplus_cache_file(cache_dir: Path, climate: str, tier: str, seq_name: str) -> Path:
    return cache_dir / f"{climate}_{tier}_{seq_name}.npz"


def _save_eplus_npz(path: Path, res: EnergyPlusResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        t_air_c=res.t_air_c,
        rh_air_percent=res.rh_air_percent,
        w_air_kg_kg=res.w_air_kg_kg,
        e_sens_heat_kwh=res.e_sens_heat_kwh,
        e_sens_cool_kwh=res.e_sens_cool_kwh,
        e_hum_kwh=res.e_hum_kwh,
        e_dehum_kwh=res.e_dehum_kwh,
        e_total_heat_kwh=res.e_total_heat_kwh,
        e_total_cool_kwh=res.e_total_cool_kwh,
        m_oa_kg_s=res.m_oa_kg_s,
        m_infil_kg_s=res.m_infil_kg_s,
    )


def _load_eplus_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path) as data:
        return {k: data[k].astype(np.float64) for k in data.files}


def _run_one_eplus_job(args: tuple[str, str, str, str, str]) -> tuple[str, str, str, str]:
    climate, tier, seq_name, epw_str, cache_str = args
    cache_path = Path(cache_str)
    if cache_path.is_file():
        return climate, tier, seq_name, "cached"
    th, tc, rhh, rhd = build_control_sequence(seq_name)
    kw = _build_eplus_kwargs(seq_name, th, tc, rhh, rhd)
    ep = build_museum_epjson(tier=tier, **kw)
    res = run_energyplus_simulation(ep, epw_str, tier=tier)
    if res.severe_errors:
        raise RuntimeError(f"Severe EnergyPlus errors on {(climate, tier, seq_name)}: {res.severe_errors}")
    _save_eplus_npz(cache_path, res)
    return climate, tier, seq_name, f"ok (warnings={len(res.warnings)})"


def ensure_eplus_dataset(
    epw_paths: dict[str, Path],
    cache_dir: Path,
    *,
    max_workers: int = 8,
) -> dict[tuple[str, str, str], dict[str, np.ndarray]]:
    """Run all required Layer B reference simulations with disk caching & process parallelism."""
    jobs: list[tuple[str, str, str, str, str]] = []
    # Training set: nyc x all 3 tiers x id_rich
    for tier in TIERS:
        jobs.append(("nyc", tier, "id_rich", str(epw_paths["nyc"]), str(_eplus_cache_file(cache_dir, "nyc", tier, "id_rich"))))
    # Cross-climate unseen evaluation + NYC holdout: all 4 climates x 3 tiers x 3 unseen sequences
    for climate in ALL_CLIMATES:
        for tier in TIERS:
            for seq in VAL_SEQUENCES:
                jobs.append((climate, tier, seq, str(epw_paths[climate]), str(_eplus_cache_file(cache_dir, climate, tier, seq))))

    pending = [j for j in jobs if not Path(j[4]).is_file()]
    if pending:
        print(f"[Layer B] Executing {len(pending)} EnergyPlus 8760h simulations (workers={max_workers})...", flush=True)
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            futs = [pool.submit(_run_one_eplus_job, j) for j in pending]
            for fut in as_completed(futs):
                c, tr, sq, msg = fut.result()
                print(f"  [E+] {c}/{tr}/{sq}: {msg}", flush=True)
    else:
        print(f"[Layer B] Loaded all {len(jobs)} cached EnergyPlus outputs from {cache_dir}.", flush=True)

    dataset: dict[tuple[str, str, str], dict[str, np.ndarray]] = {}
    for c, tr, sq, _, cp in jobs:
        dataset[(c, tr, sq)] = _load_eplus_npz(Path(cp))
    return dataset


def apply_params_to_config(
    base_cfg: MuseumROMConfig,
    params: dict[str, float],
    *,
    pressure_pa: float = STANDARD_ATM_PRESSURE_PA,
) -> MuseumROMConfig:
    """Apply physical parameters to a building config while keeping S1.1b MBV buffer locked."""
    base_rho = float(base_cfg.constants.rho_air_kg_m3)
    rho_site = base_rho * (float(pressure_pa) / STANDARD_ATM_PRESSURE_PA)
    new_const = replace(
        base_cfg.constants,
        rho_air_kg_m3=rho_site,
        solar_to_air_fraction=float(params["solar_to_air_fraction"]),
        internal_rad_fraction=float(params["internal_rad_fraction"]),
    )
    new_env = replace(
        base_cfg.envelope,
        u_wall_w_m2_k=float(params["u_wall_w_m2_k"]),
        u_roof_w_m2_k=float(params["u_roof_w_m2_k"]),
        u_window_w_m2_k=float(params["u_window_w_m2_k"]),
        u_ground_w_m2_k=float(params["u_ground_w_m2_k"]),
        window_shgc=float(params["window_shgc"]),
    )
    c_scale = float(params["c_mass_scale"])
    h_scale = float(params["h_am_scale"])
    # Preserve z.m_buffer_kg and z.tau_buffer_h strictly untouched
    new_zones = tuple(
        replace(z, c_mass_j_k=z.c_mass_j_k * c_scale, h_am_w_k=z.h_am_w_k * h_scale)
        for z in base_cfg.zones
    )
    return replace(base_cfg, constants=new_const, envelope=new_env, zones=new_zones)


def _default_params_from_config(cfg: MuseumROMConfig) -> dict[str, float]:
    return {
        "u_wall_w_m2_k": float(cfg.envelope.u_wall_w_m2_k),
        "u_roof_w_m2_k": float(cfg.envelope.u_roof_w_m2_k),
        "u_window_w_m2_k": float(cfg.envelope.u_window_w_m2_k),
        "u_ground_w_m2_k": float(cfg.envelope.u_ground_w_m2_k),
        "window_shgc": float(cfg.envelope.window_shgc),
        "solar_to_air_fraction": float(cfg.constants.solar_to_air_fraction),
        "internal_rad_fraction": float(cfg.constants.internal_rad_fraction),
        "c_mass_scale": 1.0,
        "h_am_scale": 1.0,
    }


def _vector_to_params(vec: np.ndarray) -> dict[str, float]:
    # Physical box constraints via smooth clipped mapping in positive space
    bounds = {
        "u_wall_w_m2_k": (0.05, 6.0),
        "u_roof_w_m2_k": (0.05, 6.0),
        "u_window_w_m2_k": (0.4, 8.0),
        "u_ground_w_m2_k": (0.05, 4.0),
        "window_shgc": (0.05, 0.90),
        "solar_to_air_fraction": (0.02, 0.85),
        "internal_rad_fraction": (0.05, 0.90),
        "c_mass_scale": (0.20, 6.0),
        "h_am_scale": (0.20, 6.0),
    }
    out: dict[str, float] = {}
    for k, val in zip(PARAM_NAMES, vec):
        lo, hi = bounds[k]
        out[k] = float(np.clip(val, lo, hi))
    return out


def prepare_climate_forcing(
    epw: EPWData,
    ground_hourly: np.ndarray,
) -> dict[str, Any]:
    """Assemble stationary Layer A boundary inputs matching EnergyPlus RunPeriod 1 (Tuesday start)."""
    scheds = museum_operating_schedules(epw.n_hours, start_day_of_week="Tuesday")
    solar_5z = compute_facade_irradiance(epw, north_axis_deg=30.0)
    # Undo YAML heuristic solar_weight so per-facade irradiance feeds A_win * SHGC * I_facade cleanly
    ref_zones = load_building_tier("modern").zones
    sw = np.array([z.solar_weight if z.solar_weight > 0.0 else 1.0 for z in ref_zones], dtype=np.float64)
    solar_norm = solar_5z / sw[None, :]
    return {
        "t_out_c": epw.t_out_c,
        "rh_out_percent": epw.rh_out_percent,
        "solar_rad_w_m2": solar_norm,
        "occupancy_frac": scheds["occupancy_frac"],
        "lighting_frac": scheds["lighting_frac"],
        "equipment_frac": scheds["equipment_frac"],
        "t_ground_c": ground_hourly,
        "pressure_pa": epw.mean_pressure_pa,
    }


def run_layer_a(
    base_cfg: MuseumROMConfig,
    params: dict[str, float],
    forcing: dict[str, Any],
    setpoints: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
) -> dict[str, np.ndarray]:
    """Execute Layer A MuseumROM rollout for one climate/tier/sequence."""
    cfg = apply_params_to_config(base_cfg, params, pressure_pa=forcing["pressure_pa"])
    rom = MuseumROM(cfg)
    th, tc, rhh, rhd = setpoints
    return rom.forward(
        t_out_c=forcing["t_out_c"],
        rh_out_percent=forcing["rh_out_percent"],
        solar_rad_w_m2=forcing["solar_rad_w_m2"],
        occupancy_frac=forcing["occupancy_frac"],
        lighting_frac=forcing["lighting_frac"],
        equipment_frac=forcing["equipment_frac"],
        t_ground_c=forcing["t_ground_c"],
        t_heat_sp_c=th,
        t_cool_sp_c=tc,
        rh_hum_sp_percent=rhh,
        rh_dehum_sp_percent=rhd,
        pressure_pa=forcing["pressure_pa"],
    )


def extract_net_loads(res_a: dict[str, np.ndarray], res_b: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Compute zone-summed hourly net thermal loads [kWh] on matching Supply-Air basis."""
    a_sens_h = np.sum(res_a["e_sens_heat_kwh"], axis=1)
    a_sens_c = np.sum(res_a["e_sens_cool_kwh"], axis=1)
    a_hum = np.sum(res_a["e_hum_kwh"], axis=1)
    a_dehum = np.sum(res_a["e_dehum_latent_kwh"], axis=1)
    a_sens = a_sens_h + a_sens_c
    a_lat = a_hum + a_dehum
    a_tot = a_sens + a_lat

    b_sens_h = np.sum(res_b["e_sens_heat_kwh"], axis=1)
    b_sens_c = np.sum(res_b["e_sens_cool_kwh"], axis=1)
    b_hum = np.sum(res_b["e_hum_kwh"], axis=1)
    b_dehum = np.sum(res_b["e_dehum_kwh"], axis=1)
    b_tot_h = np.sum(res_b["e_total_heat_kwh"], axis=1)
    b_tot_c = np.sum(res_b["e_total_cool_kwh"], axis=1)
    b_sens = b_sens_h + b_sens_c
    b_lat = b_hum + b_dehum
    b_tot = b_tot_h + b_tot_c

    return {
        "a_tot": a_tot,
        "b_tot": b_tot,
        "a_sens": a_sens,
        "b_sens": b_sens,
        "a_lat": a_lat,
        "b_lat": b_lat,
        "a_heat": a_sens_h + a_hum,
        "b_heat": b_tot_h,
        "a_cool": a_sens_c + a_dehum,
        "b_cool": b_tot_c,
    }


def compute_metrics(res_a: dict[str, np.ndarray], res_b: dict[str, np.ndarray]) -> dict[str, Any]:
    """Compute ASHRAE Guideline 14 load metrics and indoor T/RH errors."""
    loads = extract_net_loads(res_a, res_b)
    a_tot, b_tot = loads["a_tot"], loads["b_tot"]
    mean_b = max(float(np.mean(b_tot)), 1e-6)
    diff = a_tot - b_tot

    cv_rmse = 100.0 * float(np.sqrt(np.mean(diff ** 2))) / mean_b
    nmbe = 100.0 * float(np.mean(diff)) / mean_b
    sum_b = max(float(np.sum(b_tot)), 1e-6)
    ann_diff = 100.0 * (float(np.sum(a_tot)) - sum_b) / sum_b

    mean_bs = max(float(np.mean(loads["b_sens"])), 1e-6)
    sens_cv = 100.0 * float(np.sqrt(np.mean((loads["a_sens"] - loads["b_sens"]) ** 2))) / mean_bs
    sens_nmbe = 100.0 * float(np.mean(loads["a_sens"] - loads["b_sens"])) / mean_bs

    mean_bl = max(float(np.mean(loads["b_lat"])), 1e-6)
    lat_cv = 100.0 * float(np.sqrt(np.mean((loads["a_lat"] - loads["b_lat"]) ** 2))) / mean_bl
    lat_nmbe = 100.0 * float(np.mean(loads["a_lat"] - loads["b_lat"])) / mean_bl

    t_err = res_a["t_air_c"] - res_b["t_air_c"]
    rh_err = res_a["rh_air_percent"] - res_b["rh_air_percent"]
    t_rmse = float(np.sqrt(np.mean(t_err ** 2)))
    rh_rmse = float(np.sqrt(np.mean(rh_err ** 2)))
    rh_rmse_per_zone = [float(np.sqrt(np.mean(rh_err[:, j] ** 2))) for j in range(5)]

    passed = (
        cv_rmse <= THRESHOLDS["cv_rmse_percent"]
        and abs(nmbe) <= THRESHOLDS["abs_nmbe_percent"]
        and abs(ann_diff) <= THRESHOLDS["abs_annual_diff_percent"]
        and rh_rmse <= THRESHOLDS["rh_rmse_percent"]
    )
    return {
        "cv_rmse_percent": cv_rmse,
        "nmbe_percent": nmbe,
        "annual_diff_percent": ann_diff,
        "annual_a_kwh": float(np.sum(a_tot)),
        "annual_b_kwh": float(np.sum(b_tot)),
        "sens_cv_rmse_percent": sens_cv,
        "sens_nmbe_percent": sens_nmbe,
        "lat_cv_rmse_percent": lat_cv,
        "lat_nmbe_percent": lat_nmbe,
        "t_rmse_c": t_rmse,
        "rh_rmse_percent": rh_rmse,
        "rh_rmse_per_zone": rh_rmse_per_zone,
        "passed": bool(passed),
    }


def _residual_vector(
    vec: np.ndarray,
    base_cfg: MuseumROMConfig,
    forcing: dict[str, Any],
    sp_train: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    res_b_train: dict[str, np.ndarray],
) -> np.ndarray:
    params = _vector_to_params(vec)
    res_a = run_layer_a(base_cfg, params, forcing, sp_train)
    loads = extract_net_loads(res_a, res_b_train)
    mean_b = max(float(np.mean(loads["b_tot"])), 1e-3)
    mean_bs = max(float(np.mean(loads["b_sens"])), 1e-3)
    mean_bl = max(float(np.mean(loads["b_lat"])), 1e-3)

    # Normalized multi-channel residuals across hourly total load, sensible/latent, T, RH
    r_tot = (loads["a_tot"] - loads["b_tot"]) / mean_b
    r_sens = 0.5 * (loads["a_sens"] - loads["b_sens"]) / mean_bs
    r_lat = 0.35 * (loads["a_lat"] - loads["b_lat"]) / mean_bl
    r_t = 0.25 * (res_a["t_air_c"] - res_b_train["t_air_c"]).reshape(-1) / 2.0
    r_rh = 0.25 * (res_a["rh_air_percent"] - res_b_train["rh_air_percent"]).reshape(-1) / 5.0

    # Gentle physical regularization breaking collinear (u_wall, u_window, f_int_rad) ridges
    nom = _default_params_from_config(base_cfg)
    prior_keys = ("u_wall_w_m2_k", "u_roof_w_m2_k", "u_window_w_m2_k", "window_shgc", "internal_rad_fraction")
    r_prior = np.array([1.5 * (params[k] - nom[k]) / max(nom[k], 0.1) for k in prior_keys], dtype=np.float64)
    return np.concatenate([r_tot, r_sens, r_lat, r_t, r_rh, r_prior])


def _eval_fd_column(
    args: tuple[int, np.ndarray, np.ndarray, str, dict[str, Any], tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray], dict[str, np.ndarray]],
) -> tuple[int, np.ndarray]:
    j, x_p, r_base_h, tier, forcing_nyc, sp_id, res_b_nyc_id = args
    base_cfg = load_building_tier(tier)
    r_p = _residual_vector(x_p, base_cfg, forcing_nyc, sp_id, res_b_nyc_id)
    return j, (r_p - r_base_h)


def identify_tier_parameters(
    tier: str,
    forcing_nyc: dict[str, Any],
    res_b_nyc_id: dict[str, np.ndarray],
    *,
    max_iters: int = 12,
    workers: int = 1,
) -> tuple[dict[str, float], dict[str, Any]]:
    """Pure-NumPy Levenberg-Marquardt system identification strictly on ``nyc / id_rich``."""
    base_cfg = load_building_tier(tier)
    sp_id = build_control_sequence("id_rich")
    p0 = _default_params_from_config(base_cfg)
    # Warm start ground U from Layer B slab physical conductance ratio (~1.6 W/m2K)
    p0["u_ground_w_m2_k"] = max(p0["u_ground_w_m2_k"], 1.2)
    x = np.array([p0[k] for k in PARAM_NAMES], dtype=np.float64)

    r = _residual_vector(x, base_cfg, forcing_nyc, sp_id, res_b_nyc_id)
    cost = 0.5 * float(np.dot(r, r))
    lam = 1.0e-2
    n_p = len(PARAM_NAMES)

    pool = ProcessPoolExecutor(max_workers=min(workers, n_p)) if workers > 1 else None
    try:
        for it in range(max_iters):
            jac = np.empty((r.size, n_p), dtype=np.float64)
            hs = [max(1e-3 * abs(x[j]), 1e-4) for j in range(n_p)]
            if pool is not None:
                tasks = []
                for j in range(n_p):
                    x_p = x.copy()
                    x_p[j] += hs[j]
                    tasks.append((j, x_p, r, tier, forcing_nyc, sp_id, res_b_nyc_id))
                for j, diff_r in pool.map(_eval_fd_column, tasks):
                    jac[:, j] = diff_r / hs[j]
            else:
                for j in range(n_p):
                    x_p = x.copy()
                    x_p[j] += hs[j]
                    r_p = _residual_vector(x_p, base_cfg, forcing_nyc, sp_id, res_b_nyc_id)
                    jac[:, j] = (r_p - r) / hs[j]

            jtj = jac.T @ jac
            jtr = jac.T @ r
            diag_scale = np.maximum(np.diag(jtj), 1e-6)

            accepted = False
            rel_imp = 0.0
            for _ in range(6):
                step = -np.linalg.solve(jtj + lam * np.diag(diag_scale), jtr)
                x_cand = np.array([_vector_to_params(x + step)[k] for k in PARAM_NAMES], dtype=np.float64)
                r_cand = _residual_vector(x_cand, base_cfg, forcing_nyc, sp_id, res_b_nyc_id)
                cost_cand = 0.5 * float(np.dot(r_cand, r_cand))
                if cost_cand < cost:
                    rel_imp = (cost - cost_cand) / max(cost, 1e-12)
                    x, r, cost = x_cand, r_cand, cost_cand
                    lam = max(lam * 0.4, 1e-5)
                    accepted = True
                    print(
                        f"  [LM {tier}] it={it + 1:02d} cost={cost:.2f} rel_imp={rel_imp:.3e}",
                        flush=True,
                    )
                    break
                lam *= 4.0
            if not accepted or rel_imp < 1e-4:
                break
    finally:
        if pool is not None:
            pool.shutdown()

    final_params = _vector_to_params(x)
    train_a = run_layer_a(base_cfg, final_params, forcing_nyc, sp_id)
    train_metrics = compute_metrics(train_a, res_b_nyc_id)
    return final_params, train_metrics


def _render_cross_climate_svg(rows: list[dict[str, Any]], out_path: Path) -> None:
    """Render an inline SVG bar matrix for CV-RMSE, |NMBE|, and RH RMSE across all validation runs."""
    val_rows = [r for r in rows if r["climate"] in VAL_CLIMATES]
    w, h = 1120, 760
    pad_l, pad_r, pad_t, pad_b = 70, 30, 65, 110
    pw = w - pad_l - pad_r
    panel_h = 180
    gap = 45

    metrics = [
        ("cv_rmse_percent", "Hourly Net Load CV-RMSE [%]", THRESHOLDS["cv_rmse_percent"], 50.0, "#1f77b4"),
        ("abs_nmbe_percent", "Hourly Net Load |NMBE| [%]", THRESHOLDS["abs_nmbe_percent"], 25.0, "#ff7f0e"),
        ("rh_rmse_percent", "Indoor RH Hourly RMSE [% RH]", THRESHOLDS["rh_rmse_percent"], 8.0, "#2ca02c"),
    ]

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        '<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#222;} .title{font-size:15px;font-weight:bold;} .lbl{font-size:11px;} .tick{font-size:9px;fill:#555;}</style>',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        f'<text x="{pad_l}" y="28" class="title">Task S1.3 Cross-Climate Blind Validation (27 Unseen Runs: 3 Climates x 3 Tiers x 3 Sequences)</text>',
        f'<text x="{pad_l}" y="46" class="lbl">Locked S1.1b moisture buffer (tau_buffer_h = 8.0 h); dashed red lines mark S1.3 acceptance gates</text>',
    ]

    n_bars = len(val_rows)
    step = pw / max(n_bars, 1)
    bw = max(6.0, step * 0.72)

    for p_idx, (key, title, gate, y_max, color) in enumerate(metrics):
        y0 = pad_t + p_idx * (panel_h + gap)
        parts.append(f'<rect x="{pad_l}" y="{y0}" width="{pw}" height="{panel_h}" fill="#fafafa" stroke="#ddd"/>')
        parts.append(f'<text x="{pad_l + 6}" y="{y0 + 16}" class="lbl" font-weight="bold">{title}</text>')

        gate_y = y0 + panel_h - (gate / y_max) * (panel_h - 24)
        parts.append(
            f'<line x1="{pad_l}" y1="{gate_y:.1f}" x2="{pad_l + pw}" y2="{gate_y:.1f}" '
            f'stroke="#d62728" stroke-width="1.5" stroke-dasharray="5,4"/>'
        )
        parts.append(f'<text x="{pad_l + pw - 5}" y="{gate_y - 4:.1f}" text-anchor="end" class="tick" fill="#d62728">Gate {gate:.0f}</text>')

        for i, row in enumerate(val_rows):
            val = abs(row["nmbe_percent"]) if key == "abs_nmbe_percent" else row[key]
            val_c = min(val, y_max)
            bh = (val_c / y_max) * (panel_h - 24)
            bx = pad_l + i * step + (step - bw) * 0.5
            by = y0 + panel_h - bh
            fill = color if val <= gate else "#d62728"
            parts.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{fill}" opacity="0.88"/>')
            parts.append(f'<text x="{bx + bw/2:.1f}" y="{by - 3:.1f}" text-anchor="middle" class="tick">{val:.1f}</text>')
            if p_idx == len(metrics) - 1:
                tag = f'{row["climate"][:3].upper()}-{row["tier"][:3]}-{row["sequence"][:4]}'
                lx = bx + bw * 0.5
                ly = y0 + panel_h + 10
                parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" transform="rotate(45 {lx:.1f},{ly:.1f})" class="tick">{tag}</text>')

    parts.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")


def _render_timeseries_svg(
    examples: list[tuple[str, dict[str, np.ndarray], dict[str, np.ndarray]]],
    out_path: Path,
) -> None:
    """Render 14-day hourly Layer A vs Layer B traces (Temp, RH, Net Load) as pure SVG."""
    w, h = 1120, 680
    pad_l, pad_r, pad_t = 65, 25, 55
    col_w = (w - pad_l - pad_r - 35) / max(len(examples), 1)
    row_h = 165
    row_gap = 38

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
        '<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#222;} .title{font-size:14px;font-weight:bold;} .lbl{font-size:11px;} .tick{font-size:9px;fill:#555;}</style>',
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
        f'<text x="{pad_l}" y="26" class="title">Representative 14-Day Hourly Alignment: Layer B (Solid) vs Layer A (Dashed)</text>',
    ]

    h_slice = slice(4320, 4320 + 336)  # July 1-14 summer window
    xs = np.arange(336, dtype=np.float64)

    for c_idx, (label, ra, rb) in enumerate(examples):
        x0 = pad_l + c_idx * (col_w + 35)
        la_tot = extract_net_loads(ra, rb)
        panels = [
            ("Mean Zone Temp [C]", np.mean(rb["t_air_c"][h_slice], axis=1), np.mean(ra["t_air_c"][h_slice], axis=1), 16.0, 27.0),
            ("Mean Zone RH [%]", np.mean(rb["rh_air_percent"][h_slice], axis=1), np.mean(ra["rh_air_percent"][h_slice], axis=1), 32.0, 72.0),
            ("Total Net Load [kWh/h]", la_tot["b_tot"][h_slice], la_tot["a_tot"][h_slice], 0.0, max(float(np.max(la_tot["b_tot"][h_slice])) * 1.15, 5.0)),
        ]
        parts.append(f'<text x="{x0}" y="{pad_t - 8}" class="lbl" font-weight="bold">{label}</text>')

        for r_idx, (ylabel, yb, ya, ymin, ymax) in enumerate(panels):
            y0 = pad_t + r_idx * (row_h + row_gap)
            parts.append(f'<rect x="{x0:.1f}" y="{y0}" width="{col_w:.1f}" height="{row_h}" fill="#fafafa" stroke="#ddd"/>')
            parts.append(f'<text x="{x0 + 6:.1f}" y="{y0 + 14}" class="tick" font-weight="bold">{ylabel}</text>')

            def _pts(arr: np.ndarray) -> str:
                px = x0 + (xs / 335.0) * col_w
                py = y0 + row_h - np.clip((arr - ymin) / max(ymax - ymin, 1e-6), 0.0, 1.0) * (row_h - 20)
                return " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(px, py))

            parts.append(f'<polyline fill="none" stroke="#1f77b4" stroke-width="1.6" points="{_pts(yb)}"/>')
            parts.append(f'<polyline fill="none" stroke="#d62728" stroke-width="1.5" stroke-dasharray="4,3" points="{_pts(ya)}"/>')
            parts.append(f'<text x="{x0 - 4:.1f}" y="{y0 + 12}" text-anchor="end" class="tick">{ymax:.0f}</text>')
            parts.append(f'<text x="{x0 - 4:.1f}" y="{y0 + row_h}" text-anchor="end" class="tick">{ymin:.0f}</text>')

    parts.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(parts), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Task S1.3: Layer A identification and cross-climate validation.")
    parser.add_argument("--weather-dir", type=str, default=None, help="Directory holding EPW files.")
    parser.add_argument("--out-dir", type=str, default="results_summary/S1.3", help="Summary output directory.")
    parser.add_argument("--max-iters", type=int, default=12, help="Max Levenberg-Marquardt iterations per tier.")
    parser.add_argument("--workers", type=int, default=8, help="Parallel EnergyPlus worker processes.")
    args = parser.parse_args(argv)

    out_dir = (REPO_ROOT / args.out_dir) if not Path(args.out_dir).is_absolute() else Path(args.out_dir)
    cache_dir = out_dir / "eplus_cache"
    out_dir.mkdir(parents=True, exist_ok=True)

    epw_paths = discover_epw_paths(args.weather_dir)
    epws = {k: parse_epw(p) for k, p in epw_paths.items()}
    ground_hourly = epjson_ground_temperatures_hourly()
    forcings = {k: prepare_climate_forcing(epws[k], ground_hourly) for k in ALL_CLIMATES}

    dataset = ensure_eplus_dataset(epw_paths, cache_dir, max_workers=args.workers)

    identified: dict[str, dict[str, float]] = {}
    train_summary: dict[str, dict[str, Any]] = {}
    for tier in TIERS:
        print(f"\n[Identify] Fitting '{tier}' strictly on nyc / id_rich (buffer locked)...", flush=True)
        params, tr_m = identify_tier_parameters(
            tier,
            forcings["nyc"],
            dataset[("nyc", tier, "id_rich")],
            max_iters=args.max_iters,
            workers=args.workers,
        )
        identified[tier] = params
        train_summary[tier] = tr_m
        print(
            f"  [Train NYC/id_rich {tier}] CV={tr_m['cv_rmse_percent']:.2f}% "
            f"NMBE={tr_m['nmbe_percent']:+.2f}% Ann={tr_m['annual_diff_percent']:+.2f}% "
            f"RH_RMSE={tr_m['rh_rmse_percent']:.2f}%RH",
            flush=True,
        )

    rows: list[dict[str, Any]] = []
    ts_examples: list[tuple[str, dict[str, np.ndarray], dict[str, np.ndarray]]] = []
    tau0_diag: list[dict[str, Any]] = []

    for climate in ALL_CLIMATES:
        for tier in TIERS:
            base_cfg = load_building_tier(tier)
            for seq in VAL_SEQUENCES:
                sp = build_control_sequence(seq)
                ra = run_layer_a(base_cfg, identified[tier], forcings[climate], sp)
                rb = dataset[(climate, tier, seq)]
                m = compute_metrics(ra, rb)
                row = {"climate": climate, "tier": tier, "sequence": seq, **m}
                rows.append(row)
                if (climate, tier, seq) in (("tampa", "modern", "wide_deadband"), ("chicago", "historic", "wide_deadband")):
                    ts_examples.append((f"{climate.upper()} / {tier} / {seq}", ra, rb))
                if not m["passed"] and climate in VAL_CLIMATES:
                    # Run locked diagnostic comparison with instantaneous buffer (tau_buffer_h = 0.05h) for structural attribution
                    cfg_fast_buf = replace(
                        base_cfg,
                        zones=tuple(replace(z, tau_buffer_h=0.05) for z in base_cfg.zones),
                    )
                    ra_fast = run_layer_a(cfg_fast_buf, identified[tier], forcings[climate], sp)
                    m_fast = compute_metrics(ra_fast, rb)
                    tau0_diag.append({"climate": climate, "tier": tier, "sequence": seq, "tau_8h": m, "tau_0p05h": m_fast})

    val_rows = [r for r in rows if r["climate"] in VAL_CLIMATES]
    n_pass = sum(1 for r in val_rows if r["passed"])
    all_passed = n_pass == len(val_rows)

    (out_dir / "identified_params.json").write_text(
        json.dumps({"identified_params": identified, "nyc_train_metrics": train_summary}, indent=2),
        encoding="utf-8",
    )
    (out_dir / "validation_metrics.json").write_text(
        json.dumps(
            {
                "thresholds": THRESHOLDS,
                "n_val_total": len(val_rows),
                "n_val_passed": n_pass,
                "all_val_passed": all_passed,
                "runs": rows,
                "tau_buffer_attribution": tau0_diag,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    _render_cross_climate_svg(rows, out_dir / "cross_climate_metrics.svg")
    if ts_examples:
        _render_timeseries_svg(ts_examples, out_dir / "timeseries_wide_deadband.svg")

    md_lines = [
        "# Task S1.3: Layer A / Layer B Cross-Climate Validation Summary",
        "",
        f"- Identification dataset: `nyc / id_rich` per tier (`m_buffer_kg` and `tau_buffer_h = 8.0 h` strictly locked at S1.1b YAML values).",
        f"- Validation matrix: {len(val_rows)} unseen runs (`{len(VAL_CLIMATES)}` climates x `{len(TIERS)}` tiers x `{len(VAL_SEQUENCES)}` sequences) + NYC holdout ({len(rows) - len(val_rows)} runs).",
        f"- **Unseen validation pass rate: {n_pass} / {len(val_rows)}** ({'ALL PASSED' if all_passed else 'FAILURES DETECTED'}).",
        "",
        "| Climate | Tier | Sequence | CV-RMSE (%) | NMBE (%) | Ann Diff (%) | Sens CV (%) | Lat CV (%) | T RMSE (C) | RH RMSE (%RH) | Pass |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for r in rows:
        md_lines.append(
            f"| {r['climate']} | {r['tier']} | {r['sequence']} | {r['cv_rmse_percent']:.2f} | "
            f"{r['nmbe_percent']:+.2f} | {r['annual_diff_percent']:+.2f} | "
            f"{r['sens_cv_rmse_percent']:.2f} | {r['lat_cv_rmse_percent']:.2f} | "
            f"{r['t_rmse_c']:.2f} | {r['rh_rmse_percent']:.2f} | {'PASS' if r['passed'] else 'FAIL'} |"
        )
    (out_dir / "summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"\n[S1.3 Summary] Unseen Validation Passed: {n_pass} / {len(val_rows)}", flush=True)
    return 0 if all_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
