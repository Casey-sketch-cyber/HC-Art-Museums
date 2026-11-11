"""Synthetic visitor flow generator.

Real museum visitor counts are seasonal, weekly, and daily. We model:
  occupants(t) = base + amplitude * weekly(t) * daily(t) + N(0, sigma)
where weekly() is higher on Sat/Sun, and daily() is a smooth bump 9:00-17:00.

The series is fully deterministic given a seed, so train/eval are reproducible.
"""
from __future__ import annotations
import numpy as np


def generate_visitor_series(
    n_steps: int,
    dt_hours: float = 0.25,
    peak: float = 200.0,
    noise_std: float = 10.0,
    seed: int = 0,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(n_steps) * dt_hours          # hours since start
    hour_of_day = t % 24
    day_of_week = (t // 24).astype(int) % 7

    # Daily profile: opens 09:00, closes 17:00.
    open_mask  = (hour_of_day >= 9) & (hour_of_day <= 17)
    daily_bump = np.where(
        open_mask,
        np.sin((hour_of_day - 9) * np.pi / 8.0) ** 2,
        0.0,
    )

    # Weekly profile.
    weekly = np.where(day_of_week >= 5, 1.3, 1.0)   # Sat/Sun boost
    weekly = np.where(day_of_week == 0, 0.0, weekly)  # Mondays closed

    occ = peak * weekly * daily_bump + rng.normal(0.0, noise_std, size=n_steps)
    return np.clip(occ, 0.0, None)
