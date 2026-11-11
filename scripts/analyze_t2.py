"""Aggregate T2 multi-zone results and compare against the single-zone PoC.

Answers the two questions the T2 experiment was designed to test:
  1. Does per-zone thermostat control make the conservation constraints
     feasible (i.e., far fewer violation steps than the single-zone PoC)?
  2. Does the controller localize residual violations to fewer zones, as it
     does on the mock simulator?
"""
import json
from pathlib import Path
import numpy as np

RES = Path("results")
ZONES = ["oil_painting_gallery", "paper_works_gallery", "bronze_storage",
         "mixed_gallery", "public_lobby"]

# Single-zone PoC numbers reported in the manuscript (Table 3, PPO 500k).
SINGLE_ZONE_PPO = {
    "total_energy_kwh": 11440.0,
    "conservation_cost_total": 80010.0,
    "violation_steps": 27928.0,
}


def collect(prefix):
    rows = []
    for d in sorted(RES.glob(f"{prefix}*")):
        s = d / "eval.summary.json"
        if s.exists():
            rows.append(json.loads(s.read_text()))
    return rows


def agg(rows, key):
    vals = [r[key] for r in rows if key in r]
    if not vals:
        return float("nan"), float("nan")
    return float(np.mean(vals)), float(np.std(vals) / np.sqrt(len(vals)))


def main():
    mz = collect("lagr_mz_seed")
    rule = collect("rule_fixed_sinergym_mz")
    print(f"multi-zone Lagrangian-PPO runs: {len(mz)}")
    print(f"multi-zone rule-fixed runs:     {len(rule)}\n")

    print("=== headline (mean +/- SEM) ===")
    print(f"{'metric':28s} {'MZ Lagr-PPO':>22s} {'MZ rule-fixed':>18s} "
          f"{'single-zone PPO':>18s}")
    for m in ["total_energy_kwh", "conservation_cost_total", "violation_steps",
              "mean_pmv"]:
        a, s = agg(mz, m)
        r, _ = agg(rule, m)
        sz = SINGLE_ZONE_PPO.get(m, float("nan"))
        print(f"{m:28s} {a:14.1f}±{s:<6.1f} {r:18.1f} {sz:18.1f}")

    print("\n=== per-zone violation steps (multi-zone Lagr-PPO, mean) ===")
    for z in ZONES:
        a, _ = agg(mz, f"violation_steps_{z}")
        print(f"  {z:26s} {a:10.0f} / 35040")

    print("\n=== final lambda (multi-zone runs) ===")
    for d in sorted(RES.glob("lagr_mz_seed*")):
        lf = d / "lambda_final.txt"
        if lf.exists():
            print(f"  {d.name}: {lf.read_text().strip()}")


if __name__ == "__main__":
    main()
