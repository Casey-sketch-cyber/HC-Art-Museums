"""Unit, conservation, naive-reference, gradient, and speed tests for MuseumROM and psychro."""

from __future__ import annotations

import math
import time

import numpy as np
import pytest

from src.museum_v2 import (
    MuseumROM,
    dew_point_from_w,
    humidity_ratio_from_temp_rh,
    load_building_tier,
    make_adiabatic_config,
    moist_air_enthalpy_j_per_kg,
    rh_from_temp_w,
    saturation_vapor_pressure,
)

try:
    import torch
except ImportError:
    torch = None


def _ashrae_hyland_wexler_pws_pa(temp_c: float) -> float:
    """ASHRAE HOF Ch. 1 Hyland-Wexler saturation vapor pressure over liquid water [Pa]."""
    tk = temp_c + 273.15
    return math.exp(
        -5.8002206e3 / tk
        + 1.3914993
        - 4.8640239e-2 * tk
        + 4.1764768e-5 * tk**2
        - 1.4452093e-8 * tk**3
        + 6.5459673 * math.log(tk)
    )


def _synthetic_year_forcing(n_hours: int = 8760, seed: int = 42):
    rng = np.random.default_rng(seed)
    t_idx = np.arange(n_hours, dtype=np.float64)
    # Seasonal + diurnal outdoor weather spanning [-5, 34] C and [25, 92]% RH
    t_out = 14.5 + 13.0 * np.sin(2.0 * math.pi * (t_idx - 2200.0) / 8760.0) + 4.5 * np.sin(2.0 * math.pi * (t_idx - 9.0) / 24.0)
    rh_out = np.clip(62.0 - 15.0 * np.sin(2.0 * math.pi * (t_idx - 9.0) / 24.0) + 10.0 * rng.normal(0.0, 0.4, n_hours), 20.0, 95.0)
    hour_of_day = np.mod(t_idx, 24.0)
    day_sin = np.maximum(0.0, np.sin(math.pi * (hour_of_day - 6.0) / 12.0)) * ((hour_of_day >= 6.0) & (hour_of_day <= 18.0))
    solar = 650.0 * day_sin * (0.65 + 0.35 * np.cos(2.0 * math.pi * t_idx / 8760.0 - 3.14))
    occ = np.where((hour_of_day >= 9.0) & (hour_of_day <= 17.0), 0.7, 0.05)
    return t_out, rh_out, solar, occ


def test_psychrometrics_vs_ashrae_benchmarks():
    """Magnus-ASHRAE psychrometric routines match ASHRAE Hyland-Wexler across 5-35 C, 10-90% RH (< 1%)."""
    for t_c in (5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0):
        pws_ref = _ashrae_hyland_wexler_pws_pa(t_c)
        pws = float(saturation_vapor_pressure(t_c))
        assert abs(pws - pws_ref) / pws_ref < 0.005

        for rh_pct in (10.0, 30.0, 50.0, 70.0, 90.0):
            pw_ref = (rh_pct / 100.0) * pws_ref
            w_ref = 0.621945 * pw_ref / (101325.0 - pw_ref)
            h_ref = 1006.0 * t_c + w_ref * (2501000.0 + 1860.0 * t_c)

            w = float(humidity_ratio_from_temp_rh(t_c, rh_pct))
            assert abs(w - w_ref) / w_ref < 0.005

            rh_back = float(rh_from_temp_w(t_c, w))
            assert abs(rh_back - rh_pct) < 1e-9

            tdp = float(dew_point_from_w(w))
            assert abs(float(saturation_vapor_pressure(tdp)) - pws * (rh_pct / 100.0)) < 1e-5

            h = float(moist_air_enthalpy_j_per_kg(t_c, w))
            assert abs(h - h_ref) / abs(h_ref) < 0.005


def test_building_tiers_load_and_ordering():
    """All three building YAML tiers load cleanly and follow historic > retrofitted > modern U/ACH order."""
    hist = load_building_tier("historic")
    retro = load_building_tier("retrofitted")
    mod = load_building_tier("modern")

    assert hist.n_zones == 5
    assert hist.zone_names == ("SPACE1-1", "SPACE2-1", "SPACE3-1", "SPACE4-1", "SPACE5-1")
    assert hist.envelope.u_wall_w_m2_k > retro.envelope.u_wall_w_m2_k > mod.envelope.u_wall_w_m2_k
    assert hist.envelope.infiltration_ach_design > retro.envelope.infiltration_ach_design > mod.envelope.infiltration_ach_design
    assert hist.envelope.thermal_mass_multiplier > retro.envelope.thermal_mass_multiplier > mod.envelope.thermal_mass_multiplier


def test_closed_system_conservation_and_equilibration():
    """Closed adiabatic building strictly conserves total enthalpy and total water mass every step."""
    base = load_building_tier("modern")
    adiab = make_adiabatic_config(base)
    rom = MuseumROM(adiab)

    n_steps = 120
    t_out = np.full(n_steps, 5.0)
    rh_out = np.full(n_steps, 30.0)

    t_a0 = np.array([15.0, 22.0, 18.0, 26.0, 20.0])
    t_m0 = np.array([17.0, 19.0, 23.0, 21.0, 24.0])
    w_a0 = np.array([0.005, 0.010, 0.006, 0.011, 0.008])
    w_b0 = np.array([0.007, 0.008, 0.009, 0.006, 0.010])

    res = rom.forward(
        t_out_c=t_out,
        rh_out_percent=rh_out,
        hvac_active=False,
        t_air_init_c=t_a0,
        t_mass_init_c=t_m0,
        w_air_init_kg_kg=w_a0,
        w_buffer_init_kg_kg=w_b0,
    )

    e0 = float(rom.total_thermal_energy_j(t_a0, t_m0))
    m0 = float(rom.total_water_mass_kg(w_a0, w_b0))

    e_traj = rom.total_thermal_energy_j(res["t_air_c"], res["t_mass_c"])
    m_traj = rom.total_water_mass_kg(res["w_air_kg_kg"], res["w_buffer_kg_kg"])

    rel_e_err = np.max(np.abs(e_traj - e0)) / abs(e0)
    rel_m_err = np.max(np.abs(m_traj - m0)) / abs(m0)
    assert rel_e_err < 1e-12
    assert rel_m_err < 1e-12

    # Inter-zone coupling & air-mass coupling should pull initially distinct zones together
    assert np.ptp(res["t_air_c"][-1]) < 0.2 * np.ptp(t_a0)
    assert np.ptp(res["w_air_kg_kg"][-1]) < 0.2 * np.ptp(w_a0)


def test_unforced_steady_state_convergence():
    """Without HVAC or internal gains, all 5 zones converge to constant exterior (T_out, RH_out)."""
    rom = MuseumROM(load_building_tier("modern"))
    n_steps = 600
    t_ext = 28.0
    rh_ext = 65.0
    res = rom.forward(
        t_out_c=np.full(n_steps, t_ext),
        rh_out_percent=np.full(n_steps, rh_ext),
        t_ground_c=np.full(n_steps, t_ext),
        hvac_active=False,
        t_air_init_c=16.0,
        t_mass_init_c=16.0,
    )
    assert np.allclose(res["t_air_c"][-1], t_ext, atol=0.1)
    assert np.allclose(res["t_mass_c"][-1], t_ext, atol=0.25)
    assert np.allclose(res["rh_air_percent"][-1], rh_ext, atol=0.6)


def test_interzone_physical_coupling_effect():
    """Perturbing core lobby SPACE5-1 noticeably heats and humidifies adjacent perimeter galleries."""
    rom = MuseumROM(load_building_tier("modern"))
    n_steps = 24
    t_out = np.full(n_steps, 18.0)
    rh_out = np.full(n_steps, 45.0)

    q_extra = np.zeros((n_steps, 5))
    m_extra = np.zeros((n_steps, 5))
    q_extra[:, 4] = 8000.0   # 8 kW heat injection in SPACE5-1
    m_extra[:, 4] = 0.005    # 5 g/s moisture injection in SPACE5-1

    base = rom.forward(t_out_c=t_out, rh_out_percent=rh_out, hvac_active=False)
    pert = rom.forward(
        t_out_c=t_out,
        rh_out_percent=rh_out,
        q_extra_air_w=q_extra,
        m_extra_vapor_kg_s=m_extra,
        hvac_active=False,
    )

    delta_t_neighbors = pert["t_air_c"][-1, :4] - base["t_air_c"][-1, :4]
    delta_w_neighbors = pert["w_air_kg_kg"][-1, :4] - base["w_air_kg_kg"][-1, :4]
    assert np.all(delta_t_neighbors > 0.3)
    assert np.all(delta_w_neighbors > 2.0e-4)


def test_disaggregated_hvac_regimes_and_reheat():
    """Heating, cooling, humidification, dewpoint dehumidification, and reheat are > 0 under realistic regimes."""
    rom_mod = MuseumROM(load_building_tier("modern"))
    rom_hist = MuseumROM(load_building_tier("historic"))

    n_steps = 48
    # 1. Cold dry winter -> sens_heat > 0 & hum > 0
    winter_mod = rom_mod.forward(
        t_out_c=np.full(n_steps, -5.0),
        rh_out_percent=np.full(n_steps, 25.0),
        t_heat_sp_c=20.0,
        t_cool_sp_c=24.0,
        rh_hum_sp_percent=45.0,
        rh_dehum_sp_percent=55.0,
    )
    winter_hist = rom_hist.forward(
        t_out_c=np.full(n_steps, -5.0),
        rh_out_percent=np.full(n_steps, 25.0),
        t_heat_sp_c=20.0,
        t_cool_sp_c=24.0,
        rh_hum_sp_percent=45.0,
        rh_dehum_sp_percent=55.0,
    )
    assert np.sum(winter_mod["total_sens_heat_kwh"]) > 50.0
    assert np.sum(winter_mod["total_hum_kwh"]) > 10.0
    assert np.sum(winter_hist["total_elec_kwh"]) > np.sum(winter_mod["total_elec_kwh"])

    # 2. Hot humid summer -> sens_cool > 0 & dehum_coil > 0
    summer = rom_mod.forward(
        t_out_c=np.full(n_steps, 34.0),
        rh_out_percent=np.full(n_steps, 75.0),
        solar_rad_w_m2=np.full(n_steps, 500.0),
        occupancy_frac=np.full(n_steps, 0.8),
        t_heat_sp_c=20.0,
        t_cool_sp_c=23.0,
        rh_hum_sp_percent=40.0,
        rh_dehum_sp_percent=55.0,
    )
    assert np.sum(summer["total_sens_cool_kwh"]) > 20.0
    assert np.sum(summer["total_dehum_coil_kwh"]) > 20.0

    # 3. Cool humid rainy weather (18 C, 88% RH) -> cooling coil overcools air -> active reheat > 0
    humid_cool = rom_mod.forward(
        t_out_c=np.full(n_steps, 18.0),
        rh_out_percent=np.full(n_steps, 88.0),
        t_heat_sp_c=20.5,
        t_cool_sp_c=23.0,
        rh_hum_sp_percent=40.0,
        rh_dehum_sp_percent=50.0,
    )
    assert np.sum(humid_cool["total_dehum_coil_kwh"]) > 10.0
    assert np.sum(humid_cool["total_reheat_kwh"]) > 2.0

    # Strict non-negativity + primary/CO2 proportionality
    for res in (winter_mod, summer, humid_cool):
        for k in (
            "q_sens_heat_w",
            "q_sens_cool_w",
            "q_hum_w",
            "q_dehum_coil_w",
            "q_reheat_w",
            "e_total_elec_kwh",
            "e_primary_kwh",
            "co2_kg",
        ):
            assert np.all(res[k] >= 0.0)


def _naive_scalar_reference_rollout(
    rom: MuseumROM,
    *,
    t_out: np.ndarray,
    rh_out: np.ndarray,
    solar: np.ndarray,
    occ: np.ndarray,
    inf_scale: np.ndarray,
    t_heat_sp: float,
    t_cool_sp: float,
    rh_hum_sp: float,
    rh_dehum_sp: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Independent unbatched per-step linear-solve reference loop solving raw Backward Euler."""
    T_len = len(t_out)
    N = rom.n_zones
    cfg = rom.config
    c = cfg.constants
    hv = cfg.hvac
    dt = 3600.0

    t_gnd = float(np.mean(t_out))
    t_a = np.full(N, 20.0)
    t_m = np.full(N, 20.0)
    w_init = float(humidity_ratio_from_temp_rh(20.0, 50.0))
    w_a = np.full(N, w_init)
    w_b = np.full(N, w_init)

    t_a_hist = np.zeros((T_len, N))
    w_a_hist = np.zeros((T_len, N))
    elec_hist = np.zeros(T_len)

    def _sp(x: float, beta: float) -> float:
        bx = x * beta
        return x if bx > 20.0 else math.log1p(math.exp(bx)) / beta

    def _cap(u: float, cap: float, eps: float) -> float:
        return 0.5 * (u + cap - math.sqrt((u - cap) ** 2 + eps**2)) - 0.5 * (cap - math.sqrt(cap**2 + eps**2))

    def _pos_diff(a: float, b: float, eps: float) -> float:
        return 0.5 * ((a - b) + math.sqrt((a - b) ** 2 + eps**2)) - 0.5 * (-b + math.sqrt(b**2 + eps**2))

    for k in range(T_len):
        w_out_k = float(humidity_ratio_from_temp_rh(t_out[k], rh_out[k]))
        q_a_k = np.zeros(N)
        q_m_k = np.zeros(N)
        m_v_k = np.zeros(N)
        for i in range(N):
            q_sol = solar[k] * rom.solar_aperture_np[i]
            q_int = occ[k] * (
                rom.design_lights_w_np[i] + rom.design_equip_w_np[i] + rom.design_people_np[i] * c.person_sensible_w
            )
            q_a_k[i] = c.solar_to_air_fraction * q_sol + (1.0 - c.internal_rad_fraction) * q_int
            q_m_k[i] = (1.0 - c.solar_to_air_fraction) * q_sol + c.internal_rad_fraction * q_int
            m_v_k[i] = occ[k] * rom.design_people_np[i] * c.person_latent_kg_s

        m_inf = inf_scale[k] * rom.m_inf_design_np
        h_inf = c.cp_air_j_kg_k * m_inf

        # Solve explicit full (2N x 2N) thermal system directly without Schur pre-reduction formula
        A_T_full = np.zeros((2 * N, 2 * N))
        b_T_full = np.zeros(2 * N)
        A_W_full = np.zeros((2 * N, 2 * N))
        b_W_full = np.zeros(2 * N)

        for i in range(N):
            # Thermal air row
            A_T_full[i, i] = rom.c_air_np[i] / dt + rom.h_ext_np[i] + h_inf[i] + rom.h_am_np[i]
            A_T_full[i, N + i] = -rom.h_am_np[i]
            for j in range(N):
                if i != j:
                    h_ij = rom.h_inter_total_np[i, j]
                    A_T_full[i, i] += h_ij
                    A_T_full[i, j] -= h_ij
            b_T_full[i] = (rom.c_air_np[i] / dt) * t_a[i] + (rom.h_ext_np[i] + h_inf[i]) * t_out[k] + q_a_k[i]

            # Thermal mass row
            A_T_full[N + i, N + i] = rom.c_mass_np[i] / dt + rom.h_am_np[i] + rom.h_ground_np[i]
            A_T_full[N + i, i] = -rom.h_am_np[i]
            b_T_full[N + i] = (rom.c_mass_np[i] / dt) * t_m[i] + rom.h_ground_np[i] * t_gnd + q_m_k[i]

            # Water air row
            A_W_full[i, i] = rom.m_air_np[i] / dt + m_inf[i] + rom.k_ab_np[i]
            A_W_full[i, N + i] = -rom.k_ab_np[i]
            for j in range(N):
                if i != j:
                    m_ij = rom.m_inter_air_np[i, j]
                    A_W_full[i, i] += m_ij
                    A_W_full[i, j] -= m_ij
            b_W_full[i] = (rom.m_air_np[i] / dt) * w_a[i] + m_inf[i] * w_out_k + m_v_k[i]

            # Water buffer row
            A_W_full[N + i, N + i] = rom.m_buffer_np[i] / dt + rom.k_ab_np[i]
            A_W_full[N + i, i] = -rom.k_ab_np[i]
            b_W_full[N + i] = (rom.m_buffer_np[i] / dt) * w_b[i]

        sol_T_free = np.linalg.solve(A_T_full, b_T_full)
        sol_W_free = np.linalg.solve(A_W_full, b_W_full)
        inv_T_full = np.linalg.inv(A_T_full)
        inv_W_full = np.linalg.inv(A_W_full)

        t_a_free = sol_T_free[:N]
        w_a_free = sol_W_free[:N]

        q_sens_net = np.zeros(N)
        q_sh = np.zeros(N)
        q_sc = np.zeros(N)
        for i in range(N):
            c_eff = 1.0 / inv_T_full[i, i]
            q_sh[i] = _cap(c_eff * _sp(t_heat_sp - t_a_free[i], hv.smooth_beta_t), rom.q_heat_max_np[i], 1.0)
            q_sc[i] = _cap(c_eff * _sp(t_a_free[i] - t_cool_sp, hv.smooth_beta_t), rom.q_cool_max_np[i], 1.0)
            q_sens_net[i] = q_sh[i] - q_sc[i]

        b_T_ctrl = b_T_full.copy()
        b_T_ctrl[:N] += q_sens_net
        sol_T_ctrl = np.linalg.solve(A_T_full, b_T_ctrl)
        t_a_next = sol_T_ctrl[:N]
        t_m_next = sol_T_ctrl[N:]

        m_net = np.zeros(N)
        m_hu = np.zeros(N)
        m_de = np.zeros(N)
        for i in range(N):
            m_eff = 1.0 / inv_W_full[i, i]
            w_h_sp = float(humidity_ratio_from_temp_rh(t_a_next[i], rh_hum_sp))
            w_d_sp = float(humidity_ratio_from_temp_rh(t_a_next[i], rh_dehum_sp))
            m_hu[i] = _cap(m_eff * _sp(w_h_sp - w_a_free[i], hv.smooth_beta_w), rom.m_hum_max_np[i], 1e-6)
            m_de[i] = _cap(m_eff * _sp(w_a_free[i] - w_d_sp, hv.smooth_beta_w), rom.m_dehum_max_np[i], 1e-6)
            m_net[i] = m_hu[i] - m_de[i]

        b_W_ctrl = b_W_full.copy()
        b_W_ctrl[:N] += m_net
        sol_W_ctrl = np.linalg.solve(A_W_full, b_W_ctrl)
        w_a_next = np.maximum(sol_W_ctrl[:N], 1e-7)
        w_b_next = sol_W_ctrl[N:]

        step_elec = 0.0
        for i in range(N):
            h_fg_a = float(2501000.0 - 2381.0 * t_a_next[i])
            q_hu = m_hu[i] * h_fg_a
            w_d_sp = float(humidity_ratio_from_temp_rh(t_a_next[i], rh_dehum_sp))
            t_co = float(dew_point_from_w(w_d_sp)) - hv.coil_approach_dt_c
            w_co = float(humidity_ratio_from_temp_rh(t_co, 100.0))
            dw_c = _sp(w_a_free[i] - w_co, hv.smooth_beta_w) + 2.0e-4
            m_pr = m_de[i] / dw_c
            dt_c = _sp(t_a_free[i] - t_co, hv.smooth_beta_t)
            h_fg_c = float(2501000.0 - 2381.0 * t_co)
            q_dl = m_de[i] * h_fg_c
            q_ds = m_pr * c.cp_air_j_kg_k * dt_c
            q_dc = q_dl + q_ds
            q_re = _pos_diff(q_ds, q_sc[i], 1.0)
            q_ct = q_dc + _pos_diff(q_sc[i], q_ds, 1.0)
            step_elec += (
                q_ct / hv.cop_cooling
                + q_sh[i] / hv.eta_heating
                + q_re / hv.eta_reheat
                + q_hu / hv.eta_humidification
                + hv.fan_w_per_w_sensible * (q_ct + q_sh[i] + q_re + q_hu)
            ) / 1000.0

        t_a, t_m, w_a, w_b = t_a_next, t_m_next, w_a_next, w_b_next
        t_a_hist[k] = t_a
        w_a_hist[k] = w_a
        elec_hist[k] = step_elec

    return t_a_hist, w_a_hist, elec_hist


def test_naive_full_matrix_reference_loop_parity():
    """Schur-reduced MuseumROM matches an unreduced 10x10 step-by-step scalar reference solver."""
    rom = MuseumROM(load_building_tier("retrofitted"))
    t_out, rh_out, solar, occ = _synthetic_year_forcing(n_hours=120, seed=7)
    rng = np.random.default_rng(7)
    inf_scale = 0.7 + 0.6 * rng.random(120)

    res = rom.forward(
        t_out_c=t_out,
        rh_out_percent=rh_out,
        solar_rad_w_m2=solar,
        occupancy_frac=occ,
        infiltration_scale=inf_scale,
        t_heat_sp_c=19.5,
        t_cool_sp_c=23.5,
        rh_hum_sp_percent=42.0,
        rh_dehum_sp_percent=56.0,
    )
    ref_t, ref_w, ref_e = _naive_scalar_reference_rollout(
        rom,
        t_out=t_out,
        rh_out=rh_out,
        solar=solar,
        occ=occ,
        inf_scale=inf_scale,
        t_heat_sp=19.5,
        t_cool_sp=23.5,
        rh_hum_sp=42.0,
        rh_dehum_sp=56.0,
    )

    assert np.allclose(res["t_air_c"], ref_t, atol=1e-10, rtol=1e-10)
    assert np.allclose(res["w_air_kg_kg"], ref_w, atol=1e-12, rtol=1e-10)
    assert np.allclose(res["total_elec_kwh"], ref_e, atol=1e-10, rtol=1e-10)


@pytest.mark.skipif(torch is None, reason="PyTorch not installed in this Python environment")
def test_torch_numpy_parity_autograd_fd_and_annual_speed():
    """Verify PyTorch parity with NumPy, central finite-difference gradient check (< 1e-3), and < 5s annual runtime."""
    rom = MuseumROM(load_building_tier("modern"))

    # 1. Gradient check vs central finite differences over an active 24h rollout covering all 4 HVAC modes
    n_short = 24
    t_out = np.concatenate([np.full(8, 2.0), np.full(8, 19.0), np.full(8, 33.0)])
    rh_out = np.concatenate([np.full(8, 25.0), np.full(8, 90.0), np.full(8, 75.0)])
    solar = np.concatenate([np.zeros(16), np.full(8, 500.0)])
    occ = np.concatenate([np.zeros(8), np.full(16, 0.5)])

    t_out_t = torch.tensor(t_out, dtype=torch.float64)
    rh_out_t = torch.tensor(rh_out, dtype=torch.float64)
    solar_t = torch.tensor(solar, dtype=torch.float64)
    occ_t = torch.tensor(occ, dtype=torch.float64)

    sp_t_heat = torch.full((n_short, 5), 20.0, dtype=torch.float64, requires_grad=True)
    sp_t_cool = torch.full((n_short, 5), 23.5, dtype=torch.float64, requires_grad=True)
    sp_rh_hum = torch.full((n_short, 5), 42.0, dtype=torch.float64, requires_grad=True)
    sp_rh_dehum = torch.full((n_short, 5), 55.0, dtype=torch.float64, requires_grad=True)

    # Check NumPy parity at identical inputs
    np_res = rom.forward(
        t_out_c=t_out,
        rh_out_percent=rh_out,
        solar_rad_w_m2=solar,
        occupancy_frac=occ,
        t_heat_sp_c=20.0,
        t_cool_sp_c=23.5,
        rh_hum_sp_percent=42.0,
        rh_dehum_sp_percent=55.0,
    )
    th_res = rom.forward(
        t_out_c=t_out_t,
        rh_out_percent=rh_out_t,
        solar_rad_w_m2=solar_t,
        occupancy_frac=occ_t,
        t_heat_sp_c=sp_t_heat,
        t_cool_sp_c=sp_t_cool,
        rh_hum_sp_percent=sp_rh_hum,
        rh_dehum_sp_percent=sp_rh_dehum,
    )
    assert np.allclose(th_res["t_air_c"].detach().numpy(), np_res["t_air_c"], atol=1e-11)
    assert np.allclose(th_res["rh_air_percent"].detach().numpy(), np_res["rh_air_percent"], atol=1e-10)
    assert np.allclose(th_res["total_elec_kwh"].detach().numpy(), np_res["total_elec_kwh"], atol=1e-10)

    def _scalar_objective(t_h, t_c, r_h, r_d):
        out = rom.forward(
            t_out_c=t_out_t,
            rh_out_percent=rh_out_t,
            solar_rad_w_m2=solar_t,
            occupancy_frac=occ_t,
            t_heat_sp_c=t_h,
            t_cool_sp_c=t_c,
            rh_hum_sp_percent=r_h,
            rh_dehum_sp_percent=r_d,
        )
        return torch.sum(out["total_elec_kwh"]) + 0.05 * torch.sum((out["rh_air_percent"] - 50.0) ** 2)

    loss = _scalar_objective(sp_t_heat, sp_t_cool, sp_rh_hum, sp_rh_dehum)
    loss.backward()

    # Probe gradients at specific active time steps & zones across all 4 control variables
    eps_map = [
        (sp_t_heat, 1e-4, [(2, 0), (6, 2)]),
        (sp_t_cool, 1e-4, [(20, 0), (22, 4)]),
        (sp_rh_hum, 1e-3, [(3, 0), (5, 1)]),
        (sp_rh_dehum, 1e-3, [(12, 0), (20, 2)]),
    ]
    with torch.no_grad():
        base_vals = [p.clone() for p in (sp_t_heat, sp_t_cool, sp_rh_hum, sp_rh_dehum)]
        for idx_p, (param, h_eps, coords) in enumerate(eps_map):
            assert param.grad is not None
            for t_i, z_i in coords:
                ad_g = float(param.grad[t_i, z_i])
                assert abs(ad_g) > 1e-3, f"Expected active gradient at {(idx_p, t_i, z_i)}, got {ad_g}"
                p_plus = [b.clone() for b in base_vals]
                p_minus = [b.clone() for b in base_vals]
                p_plus[idx_p][t_i, z_i] += h_eps
                p_minus[idx_p][t_i, z_i] -= h_eps
                f_plus = float(_scalar_objective(*p_plus))
                f_minus = float(_scalar_objective(*p_minus))
                fd_g = (f_plus - f_minus) / (2.0 * h_eps)
                rel_err = abs(ad_g - fd_g) / max(abs(fd_g), abs(ad_g), 1e-6)
                assert rel_err < 1e-3, f"Grad mismatch at {(idx_p, t_i, z_i)}: ad={ad_g}, fd={fd_g}, rel={rel_err}"

    # 2. Single-core CPU full-year (8760 h x 5 zones) timing benchmark (< 5.0 s)
    prev_threads = torch.get_num_threads()
    try:
        torch.set_num_threads(1)
        t_y, rh_y, sol_y, occ_y = _synthetic_year_forcing(n_hours=8760, seed=123)
        t_y_t = torch.tensor(t_y, dtype=torch.float64)
        rh_y_t = torch.tensor(rh_y, dtype=torch.float64)
        sol_y_t = torch.tensor(sol_y, dtype=torch.float64)
        occ_y_t = torch.tensor(occ_y, dtype=torch.float64)
        ctrl_t_c = torch.full((8760, 5), 23.0, dtype=torch.float64, requires_grad=True)

        # Warm-up 1 short call to initialize MKL/Torch kernels cleanly
        _ = rom.forward(t_out_c=t_out_t, rh_out_percent=rh_out_t, t_cool_sp_c=sp_t_cool)

        t0 = time.perf_counter()
        yr_out = rom.forward(
            t_out_c=t_y_t,
            rh_out_percent=rh_y_t,
            solar_rad_w_m2=sol_y_t,
            occupancy_frac=occ_y_t,
            t_cool_sp_c=ctrl_t_c,
        )
        t_fwd = time.perf_counter() - t0
        assert yr_out["t_air_c"].shape == (8760, 5)
        assert t_fwd < 5.0, f"Full-year 8760h single-core rollout took {t_fwd:.3f}s (>= 5.0s limit)"

        t1 = time.perf_counter()
        loss_yr = torch.sum(yr_out["total_elec_kwh"])
        loss_yr.backward()
        t_bwd = time.perf_counter() - t1
        print(f"\n[BENCHMARK] 8760h x 5-zone single-core CPU: forward={t_fwd:.3f}s, backward={t_bwd:.3f}s")
        assert ctrl_t_c.grad is not None
        assert torch.all(torch.isfinite(ctrl_t_c.grad))
    finally:
        torch.set_num_threads(prev_threads)
