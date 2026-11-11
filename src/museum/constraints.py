"""Conservation constraints derived from ASHRAE Ch.24 / EN 15757.

Two kinds of constraint per zone:
  1. Static envelope:   T_min <= T <= T_max,   RH_min <= RH <= RH_max
  2. Rate envelope:     |dT/dt|  <= dT_dt_max,  |dRH/dt|  <= dRH_dt_max

The constraint cost for one zone at one step is the sum of normalized
violations across all four conditions. Cost is non-negative; zero means
no violation.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml
import numpy as np


@dataclass
class ZoneEnvelope:
    name: str
    sinergym_zone: str
    T_min: float
    T_max: float
    RH_min: float
    RH_max: float
    dT_dt_max: float
    dRH_dt_max: float
    collection: str

    def violation(
        self,
        T: float,
        RH: float,
        dT_dt: float,
        dRH_dt: float,
    ) -> tuple[float, dict[str, float], np.ndarray]:
        """Return (total normalized violation, per-component dict, clause vector).

        The clause vector groups the violation by the four EN 15757 / ASHRAE
        clause families used in the constraint-decomposed (multi-lambda)
        formulation:
            [0] static temperature, [1] static humidity,
            [2] temperature rate,   [3] humidity rate.
        Its sum equals the scalar total, so the scalar formulation is the
        special case lambda_0 = ... = lambda_3.
        """
        v_T_low  = max(0.0, self.T_min - T)
        v_T_high = max(0.0, T - self.T_max)
        v_RH_low  = max(0.0, self.RH_min - RH)
        v_RH_high = max(0.0, RH - self.RH_max)
        v_dT  = max(0.0, abs(dT_dt)  - self.dT_dt_max)
        v_dRH = max(0.0, abs(dRH_dt) - self.dRH_dt_max)

        # Normalize so each component is roughly O(1) at hard failure.
        n_T  = (v_T_low  + v_T_high)  / 1.0   # 1 K outside band -> 1.0
        n_RH = (v_RH_low + v_RH_high) / 5.0   # 5 % outside band -> 1.0
        n_dT  = v_dT  / 1.0                   # 1 K/h over cap   -> 1.0
        n_dRH = v_dRH / 2.5                   # 2.5%/h over cap  -> 1.0

        components = {
            "T_low":   v_T_low,
            "T_high":  v_T_high,
            "RH_low":  v_RH_low,
            "RH_high": v_RH_high,
            "dT":      v_dT,
            "dRH":     v_dRH,
        }
        clause_vec = np.array([n_T, n_RH, n_dT, n_dRH], dtype=np.float64)
        return float(clause_vec.sum()), components, clause_vec


# Index labels for the four-clause decomposition (multi-lambda formulation).
CLAUSE_NAMES = ("static_T", "static_RH", "rate_T", "rate_RH")
N_CLAUSES = 4


def load_envelopes(yaml_path: str | Path) -> dict[str, ZoneEnvelope]:
    cfg = yaml.safe_load(Path(yaml_path).read_text())
    out: dict[str, ZoneEnvelope] = {}
    for name, z in cfg["zones"].items():
        out[name] = ZoneEnvelope(name=name, **z)
    return out


class ConservationCost:
    """Aggregate cost across all museum zones at one timestep.

    Keeps internal previous-T/RH state so it can compute rates without the
    env having to do it.
    """

    def __init__(self, envelopes: dict[str, ZoneEnvelope], dt_hours: float = 0.25):
        self.envelopes = envelopes
        self.dt = dt_hours
        self._prev: dict[str, tuple[float, float]] = {}

    def reset(self) -> None:
        self._prev.clear()

    def step(self, zone_state: dict[str, tuple[float, float]]) -> tuple[float, dict]:
        """zone_state: {zone_name: (T, RH)}. Returns (total_cost, info).

        The four-clause decomposition vector (summed across zones) is placed
        in ``info['clause_vec']`` for the multi-lambda formulation; its sum
        equals the returned scalar total.
        """
        total = 0.0
        clause_total = np.zeros(N_CLAUSES, dtype=np.float64)
        info: dict[str, dict] = {}
        for name, (T, RH) in zone_state.items():
            env = self.envelopes[name]
            prev = self._prev.get(name, (T, RH))
            dT_dt  = (T  - prev[0]) / self.dt
            dRH_dt = (RH - prev[1]) / self.dt
            v, components, clause_vec = env.violation(T, RH, dT_dt, dRH_dt)
            total += v
            clause_total += clause_vec
            info[name] = {"violation": v, **components, "dT_dt": dT_dt, "dRH_dt": dRH_dt}
            self._prev[name] = (T, RH)
        info["clause_vec"] = clause_total
        return total, info
