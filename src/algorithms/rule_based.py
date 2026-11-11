"""Rule-based baselines.

  - RuleBasedFixedSetpoint: classic museum spec — hold T=22, RH=50 always.
  - ScheduleBased:          relax setpoints during closed hours (22:00–08:00, Mondays).
                            Mimics naive "energy-aware" practice.

Both expose .predict(obs) -> action returning an action in [-1, 1]^10
that matches the env's action space (see env.py for the mapping).
"""
from __future__ import annotations
import numpy as np

from ..museum.env import N_ZONES, T_RANGE, RH_RANGE


def _to_action(T_sp: np.ndarray, RH_sp: np.ndarray) -> np.ndarray:
    t_lo, t_hi   = T_RANGE
    rh_lo, rh_hi = RH_RANGE
    a_T  = 2.0 * (T_sp  - t_lo)  / (t_hi  - t_lo)  - 1.0
    a_RH = 2.0 * (RH_sp - rh_lo) / (rh_hi - rh_lo) - 1.0
    return np.concatenate([a_T, a_RH]).astype(np.float32)


class RuleBasedFixedSetpoint:
    name = "rule_fixed"

    def __init__(self, T: float = 22.0, RH: float = 50.0):
        self.T  = np.full(N_ZONES, T)
        self.RH = np.full(N_ZONES, RH)

    def predict(self, obs, deterministic: bool = True):
        return _to_action(self.T, self.RH), None


class SinergymRuleFixed:
    """Constant heating/cooling setpoint for Sinergym's 2-D action space."""
    name = "rule_fixed"

    def __init__(self, heating: float = 21.0, cooling: float = 23.0):
        # Sinergym action_space: Box([12., 23.25], [23.25, 30.], shape=(2,))
        self.action = np.array([heating, cooling], dtype=np.float32)

    def predict(self, obs, deterministic: bool = True):
        return self.action, None


class SinergymMultiZoneRuleFixed:
    """Constant heating/cooling setpoint applied to all five zones (10-D action).

    Mirrors the fixed-setpoint museum baseline (hold a single nominal band in
    every zone) for the multi-zone EnergyPlus env.
    """
    name = "rule_fixed_mz"

    def __init__(self, heating: float = 21.0, cooling: float = 23.0, n_zones: int = 5):
        self.action = np.array([heating, cooling] * n_zones, dtype=np.float32)

    def predict(self, obs, deterministic: bool = True):
        return self.action, None


class SinergymSchedule:
    """Relaxed setpoints during closed hours for Sinergym's 2-D action space.

    Observation layout (Sinergym 5-zone): index 2 = hour, index 1 = day_of_month,
    index 0 = month. We use hour to switch open/closed.
    """
    name = "schedule"

    def __init__(self):
        self.action_open   = np.array([21.0, 23.0], dtype=np.float32)
        self.action_closed = np.array([18.0, 26.0], dtype=np.float32)

    def predict(self, obs, deterministic: bool = True):
        hour = float(obs[2])
        return (self.action_open if 8 <= hour <= 18 else self.action_closed), None


class ScheduleBased:
    """Looser setpoints when the museum is closed.

    Obs layout (see env.py): index 16 is sin(hour/24*2pi), 17 is cos(hour/24*2pi).
    Recover the hour from those.
    """
    name = "schedule"

    def __init__(self):
        # Open hours T/RH per zone — same as fixed.
        self.T_open    = np.full(N_ZONES, 22.0)
        self.RH_open   = np.full(N_ZONES, 50.0)
        # Closed hours — allow a wider deadband to save energy.
        # Public lobby goes furthest; collection zones move only modestly.
        self.T_closed  = np.array([21.0, 20.0, 19.0, 21.0, 18.0])
        self.RH_closed = np.array([48.0, 48.0, 35.0, 50.0, 40.0])

    def predict(self, obs, deterministic: bool = True):
        sin_h, cos_h = float(obs[16]), float(obs[17])
        hour = (np.arctan2(sin_h, cos_h) / (2 * np.pi)) * 24.0
        if hour < 0:
            hour += 24.0
        open_hours = 8.0 <= hour <= 18.0
        if open_hours:
            return _to_action(self.T_open, self.RH_open), None
        return _to_action(self.T_closed, self.RH_closed), None
