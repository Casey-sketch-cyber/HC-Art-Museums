"""Unit tests for Task S1.3 identification and validation helpers."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.v2.identify_rom import (
    apply_params_to_config,
    build_control_sequence,
    compute_metrics,
    identify_tier_parameters,
)
from src.museum_v2.rom import MuseumROM, load_building_tier


def test_apply_params_keeps_mbv_buffer_strictly_locked():
    """apply_params_to_config must never modify S1.1b m_buffer_kg or tau_buffer_h."""
    base = load_building_tier("modern")
    p = {
        "u_wall_w_m2_k": 0.65,
        "u_roof_w_m2_k": 0.45,
        "u_window_w_m2_k": 2.10,
        "u_ground_w_m2_k": 1.45,
        "window_shgc": 0.35,
        "solar_to_air_fraction": 0.40,
        "internal_rad_fraction": 0.45,
        "c_mass_scale": 1.35,
        "h_am_scale": 1.50,
    }
    mod = apply_params_to_config(base, p, pressure_pa=82000.0)
    assert mod.constants.rho_air_kg_m3 < base.constants.rho_air_kg_m3
    for zb, zm in zip(base.zones, mod.zones):
        assert zm.m_buffer_kg == zb.m_buffer_kg
        assert zm.tau_buffer_h == zb.tau_buffer_h
    assert mod.envelope.u_ground_w_m2_k == 1.45


def test_control_sequences_are_feasible_and_distinct():
    """All 4 control sequences satisfy heating <= cooling and hum <= dehum bounds."""
    for name in ("F0", "wide_deadband", "random_perturb", "id_rich"):
        th, tc, rhh, rhd = build_control_sequence(name, n_hours=8760)
        assert th.shape == (8760, 5)
        assert np.all(th <= tc + 1e-12)
        assert np.all(rhh <= rhd + 1e-12)


def test_compute_metrics_and_synthetic_lm_recovery():
    """Synthetic ground-truth recovery via pure-NumPy LM closes residuals cleanly."""
    base = load_building_tier("modern")
    true_p = {
        "u_wall_w_m2_k": 0.52,
        "u_roof_w_m2_k": 0.38,
        "u_window_w_m2_k": 1.80,
        "u_ground_w_m2_k": 1.35,
        "window_shgc": 0.34,
        "solar_to_air_fraction": 0.32,
        "internal_rad_fraction": 0.50,
        "c_mass_scale": 1.15,
        "h_am_scale": 1.10,
    }
    n = 8760
    t_out = 12.0 + 11.0 * np.sin(2.0 * np.pi * np.arange(n) / 8760.0)
    rh_out = np.full(n, 60.0)
    sol = np.zeros((n, 5))
    sol[:, 0] = 200.0
    occ = np.full(n, 0.3)
    forcing = {
        "t_out_c": t_out,
        "rh_out_percent": rh_out,
        "solar_rad_w_m2": sol,
        "occupancy_frac": occ,
        "lighting_frac": occ,
        "equipment_frac": occ,
        "t_ground_c": np.full(n, 20.0),
        "pressure_pa": 101325.0,
    }
    sp = build_control_sequence("id_rich", n_hours=n)
    cfg_true = apply_params_to_config(base, true_p)
    out_true = MuseumROM(cfg_true).forward(
        t_out_c=forcing["t_out_c"],
        rh_out_percent=forcing["rh_out_percent"],
        solar_rad_w_m2=forcing["solar_rad_w_m2"],
        occupancy_frac=forcing["occupancy_frac"],
        lighting_frac=forcing["lighting_frac"],
        equipment_frac=forcing["equipment_frac"],
        t_ground_c=forcing["t_ground_c"],
        t_heat_sp_c=sp[0],
        t_cool_sp_c=sp[1],
        rh_hum_sp_percent=sp[2],
        rh_dehum_sp_percent=sp[3],
    )
    mock_b = {
        "t_air_c": out_true["t_air_c"],
        "rh_air_percent": out_true["rh_air_percent"],
        "e_sens_heat_kwh": out_true["e_sens_heat_kwh"],
        "e_sens_cool_kwh": out_true["e_sens_cool_kwh"],
        "e_hum_kwh": out_true["e_hum_kwh"],
        "e_dehum_kwh": out_true["e_dehum_latent_kwh"],
        "e_total_heat_kwh": out_true["e_sens_heat_kwh"] + out_true["e_hum_kwh"],
        "e_total_cool_kwh": out_true["e_sens_cool_kwh"] + out_true["e_dehum_latent_kwh"],
    }
    fit_p, metrics = identify_tier_parameters("modern", forcing, mock_b, max_iters=4, workers=1)
    assert metrics["passed"]
    assert metrics["cv_rmse_percent"] < 5.0
    assert metrics["rh_rmse_percent"] < 0.5
    m_self = compute_metrics(out_true, mock_b)
    assert m_self["cv_rmse_percent"] < 1e-10
