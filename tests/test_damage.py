"""Unit tests and literature arithmetic checks for heritage damage functions (Task S2.3).

Covers all four degradation mechanisms in ``src/museum_v2/damage.py``:
1. Literature test-case validation (chemical LM reference points & Martens 2012
   examples, Sedlbauer LIM_0 / LIM_I / LIM_II & 8-day germination onset + VTT
   reference curve, Mecklenburg/Martens tangential yield & fracture points +
   acclimatized furniture + Michalski proofed fluctuation, and CCI/ASHRAE/Scott
   metal critical-RH exceedance).
2. End-to-end integration with ``src/museum_v2/objects.py`` (including ``paper``
   direct air LM and ``wooden_furniture`` acclimatized bulk risk).
3. Full-year (8760 h) naive scalar-loop cross-check per ``docs/TASKS.md`` guidelines.
4. Exact differentiability via pure-NumPy analytical gradients/VJPs vs central finite
   differences across all four mechanisms, plus ``torch.autograd.gradcheck`` when
   PyTorch is available.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.museum_v2.damage import (  # noqa: E402
    ACTIVATION_ENERGY_PAPER_J_MOL,
    ACTIVATION_ENERGY_VARNISH_J_MOL,
    HAS_TORCH,
    METAL_CRH_PRESETS,
    biological_mould_risk,
    biological_mould_vjp_numpy,
    chemical_degradation_risk,
    chemical_lifetime_multiplier,
    chemical_lifetime_multiplier_grad_numpy,
    estimate_proofed_envelope,
    mechanical_strain_risk,
    mechanical_strain_vjp_numpy,
    metal_corrosion_risk,
    metal_corrosion_vjp_numpy,
    mould_germination_rate,
    proofed_fluctuation_risk,
    sedlbauer_lim_rh,
    vtt_critical_rh,
    wood_equilibrium_strain,
)
from src.museum_v2.objects import compute_object_response  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Chemical Degradation (Michalski-Martens LM)
# ---------------------------------------------------------------------------

def test_chemical_lifetime_multiplier_literature_cases():
    """Verify exact reference condition (20 C, 50% RH) = 1 and Martens p.61 examples."""
    # Reference condition: 20 degC, 50% RH -> LM == 1.0 regardless of Ea
    for ea in (ACTIVATION_ENERGY_PAPER_J_MOL, ACTIVATION_ENERGY_VARNISH_J_MOL):
        lm_ref = float(chemical_lifetime_multiplier(20.0, 50.0, ea_j_per_mol=ea))
        assert math.isclose(lm_ref, 1.0, rel_tol=1e-12, abs_tol=1e-12)

    # Martens (2012, Ch. 3, p. 61) worked examples for 5 K drop (20 C -> 15 C, 50% RH):
    #   Ea = 70 kJ/mol -> LM = 1.65; Ea = 100 kJ/mol -> LM = 2.04
    lm_15_70 = float(
        chemical_lifetime_multiplier(15.0, 50.0, ea_j_per_mol=ACTIVATION_ENERGY_VARNISH_J_MOL)
    )
    lm_15_100 = float(
        chemical_lifetime_multiplier(15.0, 50.0, ea_j_per_mol=ACTIVATION_ENERGY_PAPER_J_MOL)
    )
    assert math.isclose(lm_15_70, 1.65, abs_tol=0.005)
    assert math.isclose(lm_15_100, 2.04, abs_tol=0.005)

    # Michalski (2002): halving RH (50% -> 25% at 20 C) multiplies life by 2^1.3 > 2
    lm_25rh = float(
        chemical_lifetime_multiplier(20.0, 25.0, ea_j_per_mol=ACTIVATION_ENERGY_PAPER_J_MOL)
    )
    assert math.isclose(lm_25rh, 2.0 ** 1.3, rel_tol=1e-9)

    # Time aggregation: harmonic mean lm_equivalent <= arithmetic lm_mean (Jensen)
    temps = np.array([15.0, 25.0, 20.0, 30.0])
    rhs = np.array([40.0, 65.0, 50.0, 75.0])
    res = chemical_degradation_risk(temps, rhs, ea_j_per_mol=ACTIVATION_ENERGY_PAPER_J_MOL)
    assert float(res.lm_equivalent) < float(res.lm_mean)
    assert math.isclose(float(res.lm_equivalent * res.dose_rate), 1.0, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# 2. Biological Degradation (Sedlbauer LIM & VTT)
# ---------------------------------------------------------------------------

def test_sedlbauer_lim_and_vtt_literature_cases():
    """Verify Sedlbauer LIM_0/I/II fits, 8-day germination factor, and VTT points."""
    # Digitized anchor points from Sedlbauer et al. (2001, Fig. 5) & Krus et al. (2007, Fig. 1):
    anchors_lim0 = [(0.0, 92.42), (4.0, 83.02), (12.5, 73.85), (22.5, 70.46), (30.0, 69.87)]
    for t_c, expected_lim0 in anchors_lim0:
        lim0 = float(sedlbauer_lim_rh(t_c, substrate="0"))
        lim1 = float(sedlbauer_lim_rh(t_c, substrate="I"))
        lim2 = float(sedlbauer_lim_rh(t_c, substrate="II"))
        assert math.isclose(lim0, expected_lim0, abs_tol=0.35), (t_c, lim0, expected_lim0)
        assert lim0 < lim1 < lim2

    # Martens (2012, Sec. 5.2.2, p. 102):
    # "after exceedance of the 8-day curve for 8 successive days the [germination] value is 1"
    # On Krus et al. (2007) Fig. 1, the 8-day Substrate I curve sits ~4.5 %RH above LIM_I.
    t_20 = np.full(192, 20.0)
    rh_8d = np.full(192, float(sedlbauer_lim_rh(20.0, substrate="I")) + 4.5)
    bio_8d = biological_mould_risk(t_20, rh_8d, substrate="I", dt_hours=1.0)
    assert 0.8 <= float(bio_8d.germination_index) <= 1.7
    assert math.isclose(float(bio_8d.exceedance_hours_exact), 192.0, abs_tol=1e-9)

    # Safe museum conditions (20 C, 50% RH for 1 full year): negligible mould risk
    bio_safe = biological_mould_risk(np.full(8760, 20.0), np.full(8760, 50.0), substrate="I")
    assert float(bio_safe.exceedance_hours_exact) == 0.0
    assert float(bio_safe.germination_index) < 1e-8

    # Hukka & Viitanen (1999) VTT equation checkpoints
    assert math.isclose(float(vtt_critical_rh(0.0)), 100.0, abs_tol=1e-9)
    assert math.isclose(
        float(vtt_critical_rh(10.0)),
        -0.00267 * 1000.0 + 0.160 * 100.0 - 3.13 * 10.0 + 100.0,
        abs_tol=1e-9,
    )
    assert math.isclose(float(vtt_critical_rh(20.0)), 80.0, abs_tol=0.05)
    assert math.isclose(float(vtt_critical_rh(25.0)), 80.0, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# 3. Mechanical Degradation & Proofed Fluctuation
# ---------------------------------------------------------------------------

def test_mechanical_strain_and_proofed_fluctuation_cases():
    """Verify Mecklenburg/Martens yield/failure bounds, furniture bulk, & proofed logic."""
    # Equilibrium (rh_surface == rh_bulk) produces exact zero strain
    rh_eq = np.full(100, 50.0)
    res_eq = mechanical_strain_risk(rh_eq, rh_eq)
    assert np.allclose(res_eq.strain, 0.0, atol=1e-15)
    assert float(res_eq.exact_max_strain_ratio) == 0.0

    # Mecklenburg et al. (1998, p. 468) & Martens (2012, Fig. 3.5, p. 56):
    # From 50% RH, drop to ~28-31% causes yield (~0.004) in tension;
    # rise to ~67% causes yield (~0.004) in compression; drop to ~14% approaches failure (~0.012).
    s_comp67 = float(mechanical_strain_risk(67.0, 50.0).strain)
    s_tens28 = float(mechanical_strain_risk(28.0, 50.0).strain)
    s_fail14 = float(mechanical_strain_risk(14.0, 50.0).strain)
    assert 0.0035 < s_comp67 < 0.0045
    assert -0.0045 < s_tens28 < -0.0035
    assert s_fail14 < -0.010

    # Compressive excursion (surface wetter than bulk) does not trigger tensile fracture!
    res_wet = mechanical_strain_risk(np.array([92.0]), np.array([50.0]))
    assert float(res_wet.yield_exceedance_fraction_exact) == 1.0
    assert float(res_wet.failure_exceedance_fraction_exact) == 0.0

    # Dry shock triggers tensile fracture
    res_dry = mechanical_strain_risk(np.array([10.0]), np.array([50.0]))
    assert float(res_dry.failure_exceedance_fraction_exact) == 1.0

    # Integration with S2.2 objects.py: wooden_furniture has tau_surface == tau_bulk (320 h),
    # so Martens (2012, Sec. 5.2.4, p. 105) requires mode="acclimatized" (bulk vs long-term mean).
    t = np.arange(8760, dtype=np.float64)
    rh_air = 50.0 + 28.0 * np.sin(2.0 * math.pi * t / 8760.0)  # Large seasonal swing 22..78%
    furn = compute_object_response(rh_air, "wooden_furniture")
    assert np.allclose(furn.surface, furn.bulk, atol=1e-14)
    res_furn = mechanical_strain_risk(furn.bulk, mode="acclimatized")
    assert float(res_furn.exact_max_strain_ratio) > 0.5  # Notices slow seasonal drift

    # Michalski (2007) proofed fluctuation: safe inside historic [35, 65], penalized outside
    env = estimate_proofed_envelope(np.array([35.0, 50.0, 65.0]))
    assert (env.rh_min, env.rh_max) == (35.0, 65.0)
    inside = np.linspace(37.0, 63.0, 200)
    outside = np.concatenate([np.full(50, 20.0), np.full(50, 80.0)])
    p_in = proofed_fluctuation_risk(inside, rh_hist_min=env.rh_min, rh_hist_max=env.rh_max)
    p_out = proofed_fluctuation_risk(outside, rh_hist_min=env.rh_min, rh_hist_max=env.rh_max)
    assert float(p_in.unproofed_fraction_exact) == 0.0
    assert float(p_in.unproofed_rh_exceedance_hours) < 1e-1
    assert float(p_out.unproofed_fraction_exact) == 1.0
    assert float(p_out.unproofed_rh_exceedance_hours) > 1000.0


# ---------------------------------------------------------------------------
# 4. Metal / Bronze Corrosion Risk
# ---------------------------------------------------------------------------

def test_metal_corrosion_critical_rh_literature_cases():
    """Verify CCI (42%), Scott/Thickett (35%), ASHRAE Dry room (30%), and clean (65%)."""
    assert METAL_CRH_PRESETS["ashrae_dry_room"] == 30.0
    assert METAL_CRH_PRESETS["bronze_chloride"] == 42.0
    assert METAL_CRH_PRESETS["clean_metal"] == 65.0

    # 100 h at 35% RH, 50 h at 50% RH -> exact 50 h above 42%, 150 h above 30%, 0 h above 65%
    rh = np.concatenate([np.full(100, 35.0), np.full(50, 50.0)])
    res_42 = metal_corrosion_risk(rh, rh_crit=42.0)
    res_30 = metal_corrosion_risk(rh, rh_crit=30.0)
    res_65 = metal_corrosion_risk(rh, rh_crit=65.0)
    assert math.isclose(float(res_42.exceedance_hours_exact), 50.0, abs_tol=1e-9)
    assert math.isclose(float(res_42.exceedance_hours_smooth), 50.0, abs_tol=0.1)
    assert math.isclose(float(res_30.exceedance_hours_exact), 150.0, abs_tol=1e-9)
    assert math.isclose(float(res_65.exceedance_hours_exact), 0.0, abs_tol=1e-9)
    assert float(res_65.exceedance_rh_hours) < 1e-3


# ---------------------------------------------------------------------------
# 5. Naive Scalar Loop Reference Cross-Check on Real-Length Year (8760 h)
# ---------------------------------------------------------------------------

def test_full_year_damage_matches_naive_scalar_loops():
    """Verify vectorized formulas match plain scalar element-by-element Python loops."""
    rng = np.random.default_rng(123)
    t = np.arange(8760, dtype=np.float64)
    temp_c = 20.0 + 5.0 * np.sin(2.0 * math.pi * t / 8760.0) + rng.normal(0.0, 1.0, t.size)
    rh_air = np.clip(
        55.0 + 18.0 * np.sin(2.0 * math.pi * t / 8760.0) + rng.normal(0.0, 5.0, t.size),
        10.0,
        96.0,
    )
    panel = compute_object_response(rh_air, "panel_painting")

    # Vectorized implementations
    chem = chemical_degradation_risk(temp_c, rh_air, ea_j_per_mol=ACTIVATION_ENERGY_PAPER_J_MOL)
    bio = biological_mould_risk(temp_c, rh_air, substrate="I")
    mech = mechanical_strain_risk(panel.surface, panel.bulk, mode="gradient")
    met = metal_corrosion_risk(rh_air, rh_crit=42.0)

    # Naive readable scalar loop reference (exact elementwise equations)
    inv_lm_sum = 0.0
    lm_sum = 0.0
    bio_exact_hrs = 0.0
    bio_excess_sum = 0.0
    max_abs_strain = 0.0
    met_exact_hrs = 0.0
    met_smooth_hrs = 0.0
    for k in range(len(t)):
        tc = float(temp_c[k])
        rh = float(rh_air[k])
        # Chemical
        lm_k = ((50.0 / rh) ** 1.3) * math.exp(
            (100_000.0 / 8.314) * (1.0 / (tc + 273.15) - 1.0 / 293.15)
        )
        inv_lm_sum += 1.0 / lm_k
        lm_sum += lm_k
        # Biological (LIM_I for tc in [0, 30] far from smooth caps)
        lim_k = 74.19 + 23.32 * math.exp(-tc / 7.86)
        if rh > lim_k:
            bio_exact_hrs += 1.0
        diff_b = rh - lim_k
        bio_excess_sum += max(diff_b, 0.0) + math.log1p(math.exp(-abs(diff_b)))
        # Mechanical
        x_s = (float(panel.surface[k]) - 45.0) / 50.0
        x_b = (float(panel.bulk[k]) - 45.0) / 50.0
        eps_s = 0.006577 * x_s - 0.000887 * x_s * x_s + 0.024119 * x_s * x_s * x_s
        eps_b = 0.006577 * x_b - 0.000887 * x_b * x_b + 0.024119 * x_b * x_b * x_b
        max_abs_strain = max(max_abs_strain, abs(eps_s - eps_b))
        # Metal
        if rh > 42.0:
            met_exact_hrs += 1.0
        met_smooth_hrs += 1.0 / (1.0 + math.exp(-(rh - 42.0)))

    assert math.isclose(float(chem.lm_mean), lm_sum / len(t), rel_tol=1e-9)
    assert math.isclose(float(chem.lm_equivalent), len(t) / inv_lm_sum, rel_tol=1e-9)
    assert math.isclose(float(bio.exceedance_hours_exact), bio_exact_hrs, abs_tol=1.0)
    assert math.isclose(float(bio.exceedance_rh_hours), bio_excess_sum, rel_tol=1e-5)
    assert math.isclose(float(mech.exact_max_strain_ratio), max_abs_strain / 0.004, rel_tol=1e-12)
    assert (
        float(mech.exact_max_strain_ratio)
        <= float(mech.max_strain_ratio)
        <= float(mech.exact_max_strain_ratio) + 0.02
    )
    assert math.isclose(float(met.exceedance_hours_exact), met_exact_hrs, abs_tol=1e-12)
    assert math.isclose(float(met.exceedance_hours_smooth), met_smooth_hrs, rel_tol=1e-12)


def test_smooth_max_strain_is_tight_upper_bound_on_full_year_and_spike():
    """Smooth max strain ratio is a conservative upper bound within +0.02 over 8760 h."""
    rng = np.random.default_rng(2026)
    t = np.arange(8760, dtype=np.float64)
    rh_full = np.clip(
        50.0 + 18.0 * np.sin(2.0 * math.pi * t / 8760.0) + rng.normal(0.0, 5.0, t.size),
        10.0,
        95.0,
    )

    for obj_type, mode in (
        ("panel_painting", "gradient"),
        ("wooden_sculpture", "gradient"),
        ("wooden_furniture", "acclimatized"),
    ):
        resp = compute_object_response(rh_full, obj_type)
        mech = mechanical_strain_risk(resp.surface, resp.bulk, mode=mode)
        exact = float(mech.exact_max_strain_ratio)
        smooth = float(mech.max_strain_ratio)
        assert exact <= smooth <= exact + 0.02, f"{obj_type}: exact={exact}, smooth={smooth}"

    # Single-hour 30% RH spike out of 8760 h (regression test for LogMeanExp underestimation)
    rh_spike = np.full(8760, 50.0, dtype=np.float64)
    rh_spike[4000] = 30.0
    rh_bulk_const = np.full(8760, 50.0, dtype=np.float64)

    for mode in ("gradient", "acclimatized"):
        mech_direct = mechanical_strain_risk(rh_spike, rh_bulk_const, mode=mode)
        exact_d = float(mech_direct.exact_max_strain_ratio)
        smooth_d = float(mech_direct.max_strain_ratio)
        assert exact_d > 0.5
        assert exact_d <= smooth_d <= exact_d + 0.02

    for obj_type, mode in (
        ("panel_painting", "gradient"),
        ("wooden_sculpture", "gradient"),
        ("wooden_furniture", "acclimatized"),
    ):
        resp_s = compute_object_response(rh_spike, obj_type)
        mech_s = mechanical_strain_risk(resp_s.surface, resp_s.bulk, mode=mode)
        exact_s = float(mech_s.exact_max_strain_ratio)
        smooth_s = float(mech_s.max_strain_ratio)
        assert exact_s <= smooth_s <= exact_s + 0.02, f"spike {obj_type}: {exact_s} vs {smooth_s}"

    # Zero-strain full-year trace must remain bounded above exact (=0) and within +0.02
    rh_const = np.full(8760, 50.0, dtype=np.float64)
    mech_zero = mechanical_strain_risk(rh_const, rh_const, mode="gradient")
    assert float(mech_zero.exact_max_strain_ratio) == 0.0
    assert 0.0 <= float(mech_zero.max_strain_ratio) <= 0.02


# ---------------------------------------------------------------------------
# 6. Differentiability Tests (NumPy Analytical VJP + Torch gradcheck)
# ---------------------------------------------------------------------------

def test_numpy_analytical_gradients_match_finite_differences_all_mechanisms():
    """All four damage mechanisms match central finite differences to < 1e-6."""
    rng = np.random.default_rng(19)
    temp_c = 18.0 + 6.0 * rng.standard_normal((2, 12))
    rh = np.clip(65.0 + 18.0 * rng.standard_normal((2, 12)), 15.0, 95.0)
    rh_surf = np.clip(rh + 5.0 * rng.standard_normal((2, 12)), 10.0, 95.0)
    rh_bulk = np.clip(rh, 10.0, 95.0)

    eps_t = 1e-5
    eps_rh = 1e-4

    # 1) Chemical LM gradients
    dlm_dt, dlm_drh = chemical_lifetime_multiplier_grad_numpy(temp_c, rh)
    fd_t = (
        chemical_lifetime_multiplier(temp_c + eps_t, rh)
        - chemical_lifetime_multiplier(temp_c - eps_t, rh)
    ) / (2.0 * eps_t)
    fd_rh = (
        chemical_lifetime_multiplier(temp_c, rh + eps_rh)
        - chemical_lifetime_multiplier(temp_c, rh - eps_rh)
    ) / (2.0 * eps_rh)
    np.testing.assert_allclose(dlm_dt, fd_t, rtol=1e-6, atol=1e-9)
    np.testing.assert_allclose(dlm_drh, fd_rh, rtol=1e-6, atol=1e-9)

    # 2) Biological mould VJP
    g_exc = np.array([1.2, 0.7])
    g_germ = np.array([2.5, 1.8])
    gt_b, grh_b = biological_mould_vjp_numpy(g_exc, g_germ, temp_c, rh)

    def bio_loss(tc_in: np.ndarray, rh_in: np.ndarray) -> float:
        r = biological_mould_risk(tc_in, rh_in)
        return float(np.sum(g_exc * r.exceedance_rh_hours + g_germ * r.germination_index))

    for idx in [(0, 0), (0, 7), (1, 5), (1, 11)]:
        tp, tm = temp_c.copy(), temp_c.copy()
        tp[idx] += eps_t
        tm[idx] -= eps_t
        assert math.isclose(
            gt_b[idx], (bio_loss(tp, rh) - bio_loss(tm, rh)) / (2.0 * eps_t), rel_tol=1e-5, abs_tol=1e-8
        )
        rp, rm = rh.copy(), rh.copy()
        rp[idx] += eps_rh
        rm[idx] -= eps_rh
        assert math.isclose(
            grh_b[idx], (bio_loss(temp_c, rp) - bio_loss(temp_c, rm)) / (2.0 * eps_rh), rel_tol=1e-5, abs_tol=1e-8
        )

    # 3) Mechanical strain VJP (both gradient and broadcast acclimatized shape)
    g_max = np.array([1.0, 2.0])
    g_y = np.array([0.8, 1.5])
    g_f = np.array([0.5, 1.1])
    gp, gr = mechanical_strain_vjp_numpy(g_max, g_y, g_f, rh_surf, rh_bulk)

    def mech_loss(sp_in: np.ndarray, bk_in: np.ndarray) -> float:
        r = mechanical_strain_risk(sp_in, bk_in)
        return float(
            np.sum(
                g_max * r.max_strain_ratio
                + g_y * r.yield_exceedance_fraction_smooth
                + g_f * r.failure_exceedance_fraction_smooth
            )
        )

    for idx in [(0, 2), (0, 9), (1, 4), (1, 10)]:
        sp, sm = rh_surf.copy(), rh_surf.copy()
        sp[idx] += eps_rh
        sm[idx] -= eps_rh
        assert math.isclose(
            gp[idx], (mech_loss(sp, rh_bulk) - mech_loss(sm, rh_bulk)) / (2.0 * eps_rh), rel_tol=1e-5, abs_tol=1e-7
        )
        bp, bm = rh_bulk.copy(), rh_bulk.copy()
        bp[idx] += eps_rh
        bm[idx] -= eps_rh
        assert math.isclose(
            gr[idx], (mech_loss(rh_surf, bp) - mech_loss(rh_surf, bm)) / (2.0 * eps_rh), rel_tol=1e-5, abs_tol=1e-7
        )

    # 4) Metal corrosion VJP
    g_mh = np.array([0.6, 1.3])
    g_mrh = np.array([0.4, 0.9])
    grad_m = metal_corrosion_vjp_numpy(g_mh, g_mrh, rh, rh_crit=42.0)

    def metal_loss(rh_in: np.ndarray) -> float:
        r = metal_corrosion_risk(rh_in, rh_crit=42.0)
        return float(np.sum(g_mh * r.exceedance_hours_smooth + g_mrh * r.exceedance_rh_hours))

    for idx in [(0, 1), (0, 8), (1, 3), (1, 11)]:
        rp, rm = rh.copy(), rh.copy()
        rp[idx] += eps_rh
        rm[idx] -= eps_rh
        assert math.isclose(
            grad_m[idx], (metal_loss(rp) - metal_loss(rm)) / (2.0 * eps_rh), rel_tol=1e-6, abs_tol=1e-8
        )


@pytest.mark.skipif(not HAS_TORCH, reason="PyTorch is not installed in this environment")
def test_torch_autograd_gradcheck_all_mechanisms_and_object_chain():
    """Verify exact torch.autograd.gradcheck across all 4 mechanisms + S2.2 chain."""
    import torch

    torch.manual_seed(11)
    t_c = (torch.randn(2, 10, dtype=torch.float64) * 5.0 + 18.0).requires_grad_(True)
    rh = (torch.rand(2, 10, dtype=torch.float64) * 70.0 + 20.0).requires_grad_(True)
    rh_ref = (torch.rand(2, 10, dtype=torch.float64) * 40.0 + 35.0).requires_grad_(True)

    # 1. Chemical LM
    assert torch.autograd.gradcheck(
        lambda tc, r: chemical_degradation_risk(tc, r).dose_rate,
        (t_c, rh),
        eps=1e-6,
        atol=1e-6,
        rtol=1e-5,
    )

    # 2. Biological mould (LIM + germination index)
    assert torch.autograd.gradcheck(
        lambda tc, r: (
            biological_mould_risk(tc, r).exceedance_rh_hours,
            biological_mould_risk(tc, r).germination_index,
        ),
        (t_c, rh),
        eps=1e-6,
        atol=1e-6,
        rtol=1e-5,
    )

    # 3. Mechanical + proofed chain composed with S2.2 object response!
    assert torch.autograd.gradcheck(
        lambda r_s, r_b: (
            mechanical_strain_risk(r_s, r_b).max_strain_ratio,
            mechanical_strain_risk(r_s, r_b).yield_exceedance_fraction_smooth,
            mechanical_strain_risk(r_s, r_b).failure_exceedance_fraction_smooth,
        ),
        (rh, rh_ref),
        eps=1e-6,
        atol=1e-6,
        rtol=1e-5,
    )

    assert torch.autograd.gradcheck(
        lambda r: proofed_fluctuation_risk(r, rh_hist_min=35.0, rh_hist_max=65.0).unproofed_rh_exceedance_hours,
        (rh,),
        eps=1e-6,
        atol=1e-6,
        rtol=1e-5,
    )

    # 4. Metal corrosion
    assert torch.autograd.gradcheck(
        lambda r: (
            metal_corrosion_risk(r, rh_crit=42.0).exceedance_hours_smooth,
            metal_corrosion_risk(r, rh_crit=42.0).exceedance_rh_hours,
        ),
        (rh,),
        eps=1e-6,
        atol=1e-6,
        rtol=1e-5,
    )

    # End-to-end differentiable composition: room rh_air -> S2.2 panel_painting -> S2.3 mechanical
    resp = compute_object_response(rh, "panel_painting")
    mech = mechanical_strain_risk(resp.surface, resp.bulk)
    loss = torch.sum(mech.max_strain_ratio + mech.yield_exceedance_fraction_smooth)
    (grad_air,) = torch.autograd.grad(loss, (rh,))
    assert grad_air.shape == rh.shape
    assert torch.isfinite(grad_air).all()
