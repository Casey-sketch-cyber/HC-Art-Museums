"""Reward composition.

We split objective vs. cost:
  reward = -w_energy * energy_norm - w_comfort * comfort_penalty
  cost   = conservation_cost  (handed to the Lagrangian)

Soft-penalty baselines fold cost into reward with a fixed weight.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class RewardConfig:
    w_energy:  float
    w_comfort: float
    energy_norm_kwh: float
    comfort_band:    float


def compute_reward(
    energy_kwh:   float,
    pmv:          float,
    cfg:          RewardConfig,
) -> tuple[float, dict[str, float]]:
    e_norm  = energy_kwh / cfg.energy_norm_kwh
    c_pen   = max(0.0, abs(pmv) - cfg.comfort_band)
    reward  = -cfg.w_energy * e_norm - cfg.w_comfort * c_pen
    return reward, {"energy_norm": e_norm, "comfort_pen": c_pen, "pmv": pmv}
