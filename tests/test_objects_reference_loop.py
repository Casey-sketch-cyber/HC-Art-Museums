"""Cross-check the parallel scan in ``first_order_lowpass`` against a plain loop.

``src/museum_v2/objects.py`` computes the object RH response with a
Hillis-Steele parallel scan. That is fast but easy to get subtly wrong (off-by-one
in the initial value, wrong axis, wrong broadcasting of tau). This test compares
it, on a full year of hourly data, with the simplest possible implementation of
the same recursion:

    y[k] = alpha * y[k-1] + (1 - alpha) * u[k],   alpha = exp(-dt / tau)
    y[-1] = rh_init, or u[0] when rh_init is None

If you change ``first_order_lowpass``, this test must still pass. If you change
the recursion itself on purpose, change ``reference_loop`` below in the same
commit and explain why in docs/DECISIONS.md.

Added during the review of PR #8 (S2.2), 2026-11-17.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.museum_v2.objects import first_order_lowpass, load_object_specs  # noqa: E402

HOURS_PER_YEAR = 8760


def reference_loop(u: np.ndarray, tau: float, dt: float = 1.0, rh_init: float | None = None) -> np.ndarray:
    """Step-by-step first-order low-pass. Slow, but obviously correct."""
    alpha = np.exp(-dt / tau)
    y = np.empty_like(u, dtype=np.float64)
    prev = float(u[0]) if rh_init is None else float(rh_init)
    for k in range(len(u)):
        prev = alpha * prev + (1.0 - alpha) * float(u[k])
        y[k] = prev
    return y


def synthetic_year(seed: int = 0) -> np.ndarray:
    """Hourly RH for one year: seasonal and daily cycles plus noise."""
    rng = np.random.default_rng(seed)
    t = np.arange(HOURS_PER_YEAR)
    return (
        50.0
        + 10.0 * np.sin(2 * np.pi * t / HOURS_PER_YEAR)
        + 6.0 * np.sin(2 * np.pi * t / 24.0)
        + rng.normal(0.0, 2.0, t.size)
    )


@pytest.mark.parametrize("tau", [0.5, 10.0 / 3.0, 34.4, 120.0, 208.0, 320.0, 5000.0])
@pytest.mark.parametrize("rh_init", [None, 30.0])
def test_matches_reference_loop_float64(tau: float, rh_init: float | None) -> None:
    u = synthetic_year()
    got = first_order_lowpass(u, tau, rh_init=rh_init)
    want = reference_loop(u, tau, rh_init=rh_init)
    assert np.max(np.abs(got - want)) < 1e-9


def test_matches_reference_loop_float32() -> None:
    u = synthetic_year()
    got = first_order_lowpass(u.astype(np.float32), 208.0)
    want = reference_loop(u, 208.0)
    assert np.max(np.abs(got.astype(np.float64) - want)) < 1e-3


def test_matches_reference_loop_batch_time_axis_0_per_row_tau() -> None:
    u = synthetic_year()
    batch = np.stack([u, u[::-1]], axis=1)  # shape (T, 2), time on axis 0
    taus = np.array([10.0 / 3.0, 320.0])
    got = first_order_lowpass(batch, taus, time_axis=0)
    assert np.max(np.abs(got[:, 0] - reference_loop(u, taus[0]))) < 1e-9
    assert np.max(np.abs(got[:, 1] - reference_loop(u[::-1], taus[1]))) < 1e-9


def test_daily_cycle_attenuation_matches_first_order_theory() -> None:
    """A pure daily sine is damped by 1 / sqrt(1 + (w tau)^2) at steady state."""
    t = np.arange(60 * 24)  # 60 days, long enough to forget the start
    w = 2 * np.pi / 24.0
    u = 50.0 + 5.0 * np.sin(w * t)
    for name, spec in load_object_specs().items():
        for part in ("surface", "bulk"):
            tau = getattr(spec, part).tau_hours
            if tau > 400:  # would need longer than 60 days to settle
                continue
            y = first_order_lowpass(u, tau)
            last_days = y[-10 * 24 :]
            amplitude = (last_days.max() - last_days.min()) / 2.0
            # ZOH discretisation adds a small error at dt = 1 h; allow 3 %
            expected = 5.0 / np.sqrt(1.0 + (w * tau) ** 2)
            assert amplitude == pytest.approx(expected, rel=0.03), (name, part)
