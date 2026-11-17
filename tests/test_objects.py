"""Unit tests for museum object hygroscopic RH response model (Task S2.2).

Verifies:
1. Literature provenance & BibTeX key completeness in ``configs/objects.yaml``.
2. Exact 63% (1 - 1/e) and 95% (1 - e^-3) step-response behavior matching the
   configured time constants and Martens (2012) Eq. (5.2) conversion.
3. Physical invariants (constant preservation, convex bounds, sinusoidal amplitude
   attenuation, associative scan vs sequential loop equivalence, batched and
   non-default ``time_axis`` handling).
4. Exact differentiability via analytical reverse-mode VJP (always tested in
   NumPy) and via ``torch.autograd.gradcheck`` when PyTorch is installed.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.museum_v2.objects import (  # noqa: E402
    DEFAULT_OBJECTS_CONFIG,
    HAS_TORCH,
    ObjectResponseModel,
    compute_all_object_responses,
    compute_object_response,
    first_order_lowpass,
    first_order_lowpass_vjp,
    get_object_spec,
    list_omitted_categories,
    load_object_specs,
    load_objects_config,
    martens_t95_to_tau,
)

BIB_FILE = ROOT / "paper" / "iscience" / "references.bib"
BIB_KEY_RE = re.compile(r"^@\w+\s*\{\s*([^,\s]+)\s*,", re.MULTILINE)


def _sequential_zoh_reference(
    rh_air: np.ndarray,
    tau_hours: float,
    dt_hours: float,
    rh_init: float | None,
) -> np.ndarray:
    """Straightforward sequential reference implementation for 1D arrays."""
    alpha = math.exp(-dt_hours / tau_hours)
    y = np.empty_like(rh_air, dtype=np.float64)
    prev = float(rh_air[0] if rh_init is None else rh_init)
    for k in range(len(rh_air)):
        prev = alpha * prev + (1.0 - alpha) * float(rh_air[k])
        y[k] = prev
    return y


def test_provenance_and_bibtex_keys_complete():
    """Every configured time constant has verified pages/table and BibTeX key."""
    assert DEFAULT_OBJECTS_CONFIG.is_file()
    raw = load_objects_config()
    specs = load_object_specs()
    bib_keys = set(BIB_KEY_RE.findall(BIB_FILE.read_text(encoding="utf-8")))

    assert set(specs.keys()) == {
        "panel_painting",
        "wooden_sculpture",
        "wooden_furniture",
    }

    for name, spec in specs.items():
        assert 0.0 < spec.surface.tau_hours <= spec.bulk.tau_hours, name
        for channel_name, ch in (("surface", spec.surface), ("bulk", spec.bulk)):
            assert ch.bib_key in bib_keys, f"{name}.{channel_name}: missing {ch.bib_key}"
            assert ch.pages.strip(), f"{name}.{channel_name}: empty pages"
            assert ch.table_or_figure.strip(), f"{name}.{channel_name}: empty table/figure"
            assert ch.document.strip(), f"{name}.{channel_name}: empty document"
            expected_tau = martens_t95_to_tau(ch.reported_hours)
            assert math.isclose(ch.tau_hours, expected_tau, rel_tol=1e-12), (
                f"{name}.{channel_name}: expected {expected_tau}, got {ch.tau_hours}"
            )

    # Top-level provenance & omitted categories must cite verified bib keys.
    assert raw["provenance"]["temperature_response"]["bib_key"] in bib_keys
    assert raw["provenance"]["conversion_rule"]["bib_key"] in bib_keys

    omitted = list_omitted_categories()
    assert {"paper", "canvas_painting", "bronze"}.issubset(omitted.keys())
    for cat in ("paper", "canvas_painting", "bronze"):
        assert len(omitted[cat]["reason"].strip()) > 30
        with pytest.raises(KeyError):
            get_object_spec(cat)

    cfg_text = DEFAULT_OBJECTS_CONFIG.read_text(encoding="utf-8")
    for forbidden in ("EN 15757 速率上限", "硬约束"):
        assert forbidden not in cfg_text


@pytest.mark.parametrize(
    "category",
    ["panel_painting", "wooden_sculpture", "wooden_furniture"],
)
def test_step_response_63_percent_equals_tau(category: str):
    """Under a step change, 63.2% (1 - 1/e) response occurs at t = tau."""
    spec = get_object_spec(category)
    rh0 = 40.0
    rh1 = 60.0
    target_63 = 1.0 - math.exp(-1.0)
    target_95 = 1.0 - math.exp(-3.0)

    # 1. Fine timestep dt = tau / 20 so t = tau falls exactly on sample index 19
    #    (when starting from rh_init = rh0) and sample index 20 (equilibrium start).
    for channel_name, ch in (("surface", spec.surface), ("bulk", spec.bulk)):
        tau = ch.tau_hours
        dt = tau / 20.0
        n_steps = 80  # 4 * tau

        # Convention A: rh_init = rh0, step occurs immediately at t = dt (k = 0).
        step_seq = np.full(n_steps, rh1, dtype=np.float64)
        resp_a = first_order_lowpass(step_seq, tau_hours=tau, dt_hours=dt, rh_init=rh0)
        frac_a_tau = (resp_a[19] - rh0) / (rh1 - rh0)
        frac_a_3tau = (resp_a[59] - rh0) / (rh1 - rh0)
        assert math.isclose(frac_a_tau, target_63, abs_tol=1e-12), (
            f"{category}.{channel_name} conv A 63%: {frac_a_tau}"
        )
        assert math.isclose(frac_a_3tau, target_95, abs_tol=1e-12), (
            f"{category}.{channel_name} conv A 95%: {frac_a_3tau}"
        )

        # Convention B: equilibrium at u[0] = rh0, step at u[1:] = rh1.
        step_eq = np.concatenate([[rh0], np.full(n_steps, rh1, dtype=np.float64)])
        resp_b = first_order_lowpass(step_eq, tau_hours=tau, dt_hours=dt, rh_init=None)
        assert math.isclose(resp_b[0], rh0, abs_tol=1e-14)
        frac_b_tau = (resp_b[20] - rh0) / (rh1 - rh0)
        frac_b_3tau = (resp_b[60] - rh0) / (rh1 - rh0)
        assert math.isclose(frac_b_tau, target_63, abs_tol=1e-12)
        assert math.isclose(frac_b_3tau, target_95, abs_tol=1e-12)

    # 2. Hourly grid (dt = 1.0 h) integrated end-to-end via compute_object_response,
    #    testing both rising (40 -> 60) and falling (70 -> 35) steps.
    horizon = max(int(math.ceil(spec.bulk.tau_hours * 4)), 60)
    for start_rh, end_rh in ((40.0, 60.0), (70.0, 35.0)):
        u_hourly = np.full(horizon, end_rh, dtype=np.float64)
        out = compute_object_response(
            u_hourly,
            category=category,
            dt_hours=1.0,
            rh_init_surface=start_rh,
            rh_init_bulk=start_rh,
        )
        times = np.arange(1, horizon + 1, dtype=np.float64)
        for ch_arr, tau in ((out.surface, spec.surface.tau_hours), (out.bulk, spec.bulk.tau_hours)):
            norm = (ch_arr - start_rh) / (end_rh - start_rh)
            # Continuous-time 63% crossing inverted from exact exponential decay:
            idx_above = int(np.argmax(norm >= target_63))
            if float(tau).is_integer():
                k_tau = int(round(tau)) - 1
                assert math.isclose(norm[k_tau], target_63, abs_tol=1e-12)
            else:
                t_est = -times[idx_above] / math.log(1.0 - norm[idx_above])
                assert math.isclose(t_est, tau, rel_tol=1e-10)
            # Also confirm 1 - e^-3 at 3*tau on hourly grid when 3*tau is integer:
            if float(3.0 * tau).is_integer():
                k_3tau = int(round(3.0 * tau)) - 1
                assert math.isclose(norm[k_3tau], target_95, abs_tol=1e-12)


def test_associative_scan_matches_sequential_and_batches():
    """Verify full-year scan matches sequential loop, batches, and time_axis=0."""
    rng = np.random.default_rng(42)
    t_len = 8760
    batch, zones = 2, 3
    u = 50.0 + 15.0 * rng.standard_normal((batch, zones, t_len))
    tau_arr = np.array([3.3333333333333335, 34.4, 208.0], dtype=np.float64)

    y_scan = first_order_lowpass(u, tau_hours=tau_arr, dt_hours=1.0)
    assert y_scan.shape == u.shape

    for b in range(batch):
        for z in range(zones):
            y_ref = _sequential_zoh_reference(u[b, z], float(tau_arr[z]), 1.0, None)
            np.testing.assert_allclose(y_scan[b, z], y_ref, rtol=1e-12, atol=1e-12)

    # Check time_axis=0 gives identical output for moved axes.
    u_tfirst = np.moveaxis(u, -1, 0)
    y_tfirst = first_order_lowpass(u_tfirst, tau_hours=tau_arr, dt_hours=1.0, time_axis=0)
    np.testing.assert_allclose(np.moveaxis(y_tfirst, 0, -1), y_scan, rtol=1e-13, atol=1e-13)

    # Convexity / constant preservation / tau_scale check.
    const = np.full(100, 48.5)
    np.testing.assert_allclose(first_order_lowpass(const, 34.4), const, atol=1e-13)
    assert np.min(y_scan) >= np.min(u) - 1e-12
    assert np.max(y_scan) <= np.max(u) + 1e-12

    all_out = compute_all_object_responses(u[0, 0], tau_scale=0.5)
    assert set(all_out.keys()) == {"panel_painting", "wooden_sculpture", "wooden_furniture"}
    assert np.allclose(
        all_out["wooden_furniture"].surface,
        all_out["wooden_furniture"].bulk,
        atol=1e-14,
    )


def test_sinusoidal_attenuation_matches_frequency_response():
    """Diurnal cycles are strongly damped by high-tau bulk compared to annual cycles."""
    spec = get_object_spec("panel_painting")
    t = np.arange(8760 * 3, dtype=np.float64)
    # Diurnal 24h cycle vs annual 8760h cycle
    u_diurnal = 50.0 + 10.0 * np.sin(2.0 * math.pi * t / 24.0)
    u_annual = 50.0 + 10.0 * np.sin(2.0 * math.pi * t / 8760.0)

    out_d = compute_object_response(u_diurnal, spec)
    out_a = compute_object_response(u_annual, spec)

    # Steady-state sinusoidal amplitude via exact DFT at fundamental frequency
    # (discrete grid peaks can sit up to half a sample off the continuous crest).
    tail_idx = np.arange(8760 * 2, 8760 * 3, dtype=np.float64)
    tail = slice(8760 * 2, None)

    def dft_amplitude(sig: np.ndarray, period_h: float) -> float:
        omega = 2.0 * math.pi / period_h
        centered = sig - np.mean(sig)
        phasor = np.exp(-1j * omega * tail_idx)
        return float((2.0 / len(tail_idx)) * abs(np.sum(centered * phasor)))

    amp_d_bulk = dft_amplitude(out_d.bulk[tail], 24.0)
    amp_d_surf = dft_amplitude(out_d.surface[tail], 24.0)
    amp_a_bulk = dft_amplitude(out_a.bulk[tail], 8760.0)

    # Theoretical gain of discrete ZOH pole alpha at radian frequency omega:
    #   |H(e^{j*omega})| = (1 - alpha) / |1 - alpha * e^{-j*omega}|
    def theoretical_gain(tau_h: float, period_h: float) -> float:
        alpha = math.exp(-1.0 / tau_h)
        omega = 2.0 * math.pi / period_h
        denom = abs(1.0 - alpha * complex(math.cos(omega), -math.sin(omega)))
        return (1.0 - alpha) / denom

    assert math.isclose(amp_d_bulk / 10.0, theoretical_gain(spec.bulk.tau_hours, 24.0), rel_tol=1e-9)
    assert math.isclose(amp_d_surf / 10.0, theoretical_gain(spec.surface.tau_hours, 24.0), rel_tol=1e-9)
    assert math.isclose(amp_a_bulk / 10.0, theoretical_gain(spec.bulk.tau_hours, 8760.0), rel_tol=1e-9)
    assert amp_d_bulk < amp_d_surf < amp_a_bulk


def test_numpy_analytical_gradients_match_finite_differences():
    """Exact reverse-mode VJP w.r.t. rh_air, tau_hours, and rh_init matches FD."""
    rng = np.random.default_rng(7)
    u = 50.0 + 10.0 * rng.standard_normal((2, 3, 25))
    weights = rng.standard_normal(u.shape)
    tau = np.array([3.3333333333333335, 34.4, 120.0], dtype=np.float64)
    rh_init = 45.0 + 3.0 * rng.standard_normal((2, 3))
    dt = 1.0

    def scalar_loss(u_in: np.ndarray, tau_in: np.ndarray, init_in: np.ndarray | None) -> float:
        y = first_order_lowpass(u_in, tau_hours=tau_in, dt_hours=dt, rh_init=init_in)
        return float(np.sum(weights * y))

    # Case 1: explicit rh_init
    grad_u, grad_tau, grad_init = first_order_lowpass_vjp(
        weights, u, tau, dt_hours=dt, rh_init=rh_init
    )
    # The filter is affine in u and rh_init, so eps=1e-3 has zero truncation error
    # while avoiding float64 cancellation on ~1e3 loss sums.
    eps_linear = 1e-3
    eps_tau = 1e-5

    fd_u = np.zeros_like(u)
    for idx in np.ndindex(u.shape):
        up = u.copy()
        um = u.copy()
        up[idx] += eps_linear
        um[idx] -= eps_linear
        fd_u[idx] = (scalar_loss(up, tau, rh_init) - scalar_loss(um, tau, rh_init)) / (
            2.0 * eps_linear
        )
    np.testing.assert_allclose(grad_u, fd_u, rtol=1e-6, atol=1e-9)

    fd_tau = np.zeros_like(tau)
    for idx in range(len(tau)):
        tp = tau.copy()
        tm = tau.copy()
        tp[idx] += eps_tau
        tm[idx] -= eps_tau
        fd_tau[idx] = (scalar_loss(u, tp, rh_init) - scalar_loss(u, tm, rh_init)) / (
            2.0 * eps_tau
        )
    np.testing.assert_allclose(grad_tau, fd_tau, rtol=1e-6, atol=1e-9)

    fd_init = np.zeros_like(rh_init)
    for idx in np.ndindex(rh_init.shape):
        ip = rh_init.copy()
        im = rh_init.copy()
        ip[idx] += eps_linear
        im[idx] -= eps_linear
        fd_init[idx] = (scalar_loss(u, tau, ip) - scalar_loss(u, tau, im)) / (
            2.0 * eps_linear
        )
    np.testing.assert_allclose(grad_init, fd_init, rtol=1e-6, atol=1e-9)

    # Case 2: rh_init=None (equilibrium init at u[..., 0]) and scalar tau
    grad_u2, grad_tau2, grad_init2 = first_order_lowpass_vjp(
        weights, u, 34.4, dt_hours=dt, rh_init=None
    )
    assert grad_init2 is None
    for idx in [(0, 0, 0), (1, 2, 0), (0, 1, 10), (1, 0, 24)]:
        up = u.copy()
        um = u.copy()
        up[idx] += eps_linear
        um[idx] -= eps_linear
        fd = (
            float(np.sum(weights * first_order_lowpass(up, 34.4, dt)))
            - float(np.sum(weights * first_order_lowpass(um, 34.4, dt)))
        ) / (2.0 * eps_linear)
        assert math.isclose(grad_u2[idx], fd, rel_tol=1e-6, abs_tol=1e-9)

    fd_t2 = (
        float(np.sum(weights * first_order_lowpass(u, 34.4 + eps_tau, dt)))
        - float(np.sum(weights * first_order_lowpass(u, 34.4 - eps_tau, dt)))
    ) / (2.0 * eps_tau)
    assert math.isclose(float(grad_tau2), fd_t2, rel_tol=1e-6, abs_tol=1e-9)


def test_object_response_model_wrapper_works():
    """ObjectResponseModel produces identical values to compute_object_response."""
    u = np.linspace(35.0, 65.0, 120)
    model = ObjectResponseModel("wooden_sculpture", dt_hours=1.0)
    res_m = model(u, rh_init_surface=40.0, rh_init_bulk=40.0)
    res_f = compute_object_response(
        u, "wooden_sculpture", dt_hours=1.0, rh_init_surface=40.0, rh_init_bulk=40.0
    )
    np.testing.assert_allclose(res_m.surface, res_f.surface, rtol=1e-13, atol=1e-13)
    np.testing.assert_allclose(res_m.bulk, res_f.bulk, rtol=1e-13, atol=1e-13)


@pytest.mark.skipif(not HAS_TORCH, reason="PyTorch is not installed in this environment")
def test_torch_autograd_gradcheck_and_matches_numpy_vjp():
    """Verify exact torch.autograd differentiability when PyTorch is available."""
    import torch

    torch.manual_seed(0)
    u = torch.randn(2, 3, 18, dtype=torch.float64) * 8.0 + 50.0
    u = u.clone().detach().requires_grad_(True)
    tau = torch.tensor([3.5, 34.4, 120.0], dtype=torch.float64, requires_grad=True)
    rh_init = (torch.randn(2, 3, dtype=torch.float64) + 45.0).requires_grad_(True)

    # 1. torch.autograd.gradcheck w.r.t. (u, tau, rh_init)
    assert torch.autograd.gradcheck(
        lambda x, t, i: first_order_lowpass(x, t, dt_hours=1.0, rh_init=i),
        (u, tau, rh_init),
        eps=1e-6,
        atol=1e-6,
        rtol=1e-5,
    )

    # 2. torch.autograd.gradcheck with rh_init=None
    assert torch.autograd.gradcheck(
        lambda x, t: first_order_lowpass(x, t, dt_hours=1.0, rh_init=None),
        (u, tau),
        eps=1e-6,
        atol=1e-6,
        rtol=1e-5,
    )

    # 3. Torch autograd gradients match NumPy analytical VJP to float64 precision.
    weights = torch.randn_like(u)
    y = first_order_lowpass(u, tau, dt_hours=1.0, rh_init=rh_init)
    loss = torch.sum(weights * y)
    gu_t, gt_t, gi_t = torch.autograd.grad(loss, (u, tau, rh_init))

    gu_np, gt_np, gi_np = first_order_lowpass_vjp(
        weights.detach().numpy(),
        u.detach().numpy(),
        tau.detach().numpy(),
        dt_hours=1.0,
        rh_init=rh_init.detach().numpy(),
    )
    np.testing.assert_allclose(gu_t.detach().numpy(), gu_np, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(gt_t.detach().numpy(), gt_np, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(gi_t.detach().numpy(), gi_np, rtol=1e-12, atol=1e-12)

    # 4. ObjectResponseModel as an nn.Module propagates gradients to air control sequence
    #    and learnable tau parameters.
    model = ObjectResponseModel("panel_painting", dt_hours=1.0, learnable_tau=True)
    resp = model(u)
    grad_loss = torch.mean((resp.surface - resp.bulk) ** 2)
    grad_loss.backward()
    assert model.log_tau_surface.grad is not None
    assert model.log_tau_bulk.grad is not None
    assert torch.isfinite(u.grad).all()
