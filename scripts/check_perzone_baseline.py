"""Sanity check: is the mock-env headline result robust to a trivial baseline?

Runs three no-learning controllers on MockMuseumEnv for one year each:

  rule_fixed      -- every zone at 22 degC / 50 %RH (baseline B1 of the old paper)
  perzone_mid     -- every zone at a constant setpoint in the middle of ITS OWN
                     conservation envelope (no learning, no feedback)
  perzone_mid_ff  -- same targets, with a static weather feed-forward that inverts
                     the steady state of the mock dynamics

and prints annual energy, year-total conservation cost, violation steps, the
per-zone violation steps and which clause (static / rate) was violated.

Result recorded on 2026-11-12 (seed 0): rule_fixed reproduces Table 2 of the old
manuscript (364.9 MWh, cost ~78.4k, 35,040 violation steps) while perzone_mid
reaches cost ~5 with 3 violation steps at 358.8 MWh. See docs/REVIEW_2026-11-12.md.

Usage:
    python scripts/check_perzone_baseline.py            # seed 0
    python scripts/check_perzone_baseline.py --seeds 0 1 2
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.museum.env import MockMuseumEnv, N_ZONES, RH_RANGE, T_RANGE  # noqa: E402

CONSERVATION = ROOT / "configs" / "conservation.yaml"
CLAUSES = ("T_low", "T_high", "RH_low", "RH_high", "dT", "dRH")

# Envelope midpoints, in the zone order of configs/conservation.yaml:
# oil painting, paper works, bronze storage, mixed gallery, public lobby.
T_MID = np.array([21.5, 20.0, 20.0, 21.0, 23.0])
RH_MID = np.array([50.0, 50.0, 35.0, 50.0, 50.0])


def to_action(T_sp, RH_sp) -> np.ndarray:
    a_T = 2.0 * (np.asarray(T_sp) - T_RANGE[0]) / (T_RANGE[1] - T_RANGE[0]) - 1.0
    a_RH = 2.0 * (np.asarray(RH_sp) - RH_RANGE[0]) / (RH_RANGE[1] - RH_RANGE[0]) - 1.0
    return np.concatenate([a_T, a_RH]).astype(np.float32)


def rule_fixed(obs):
    return to_action(np.full(N_ZONES, 22.0), np.full(N_ZONES, 50.0))


def perzone_mid(obs):
    return to_action(T_MID, RH_MID)


def perzone_mid_ff(obs):
    """Invert the mock env steady state so the achieved state sits on the target.

    Mock dynamics: dT ~ (T_sp - T)/0.5 + (T_out - T)/8, i.e.
    T_ss = (2 T_sp + 0.125 T_out) / 2.125, and likewise for RH with gain 1.4.
    obs[10], obs[11] are outdoor temperature and relative humidity.
    """
    T_out, RH_out = float(obs[10]), float(obs[11])
    T_sp = np.clip((2.125 * T_MID - 0.125 * T_out) / 2.0, *T_RANGE)
    k = 0.7 / 0.5
    RH_sp = np.clip(((k + 0.125) * RH_MID - 0.125 * RH_out) / k, *RH_RANGE)
    return to_action(T_sp, RH_sp)


def run(name: str, policy, seed: int) -> dict:
    env = MockMuseumEnv(CONSERVATION, seed=seed)
    obs, _ = env.reset(seed=seed)
    energy = cost = 0.0
    viol_steps = 0
    zone_viol = np.zeros(N_ZONES, dtype=int)
    clause = dict.fromkeys(CLAUSES, 0)
    done = False
    while not done:
        obs, _, terminated, truncated, info = env.step(policy(obs))
        done = terminated or truncated
        energy += info["energy_kwh"]
        cost += info["cost"]
        viol_steps += int(info["cost"] > 0)
        for i, zone in enumerate(env.zone_names):
            z = info["cost_info"][zone]
            zone_viol[i] += int(z["violation"] > 0)
            for c in CLAUSES:
                clause[c] += int(z[c] > 0)
    return {
        "controller": name,
        "seed": seed,
        "energy_mwh": energy / 1000.0,
        "cost_total": cost,
        "violation_steps": viol_steps,
        "zone_violation_steps": zone_viol.tolist(),
        "clause_violation_counts": clause,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--seeds", type=int, nargs="+", default=[0])
    args = p.parse_args()

    controllers = {
        "rule_fixed": rule_fixed,
        "perzone_mid": perzone_mid,
        "perzone_mid_ff": perzone_mid_ff,
    }
    for seed in args.seeds:
        for name, policy in controllers.items():
            r = run(name, policy, seed)
            print(
                f"{r['controller']:15s} seed={r['seed']} "
                f"E={r['energy_mwh']:7.1f} MWh  cost={r['cost_total']:10.0f}  "
                f"viol_steps={r['violation_steps']:6d}  "
                f"per_zone={r['zone_violation_steps']}  "
                f"clauses={r['clause_violation_counts']}"
            )


if __name__ == "__main__":
    main()
