"""Aggregate and compare scalar-lambda vs multi-lambda (T3) mock runs."""
import json
from pathlib import Path
import numpy as np

RES = Path("results")
METRICS = ["total_energy_kwh", "conservation_cost_total", "violation_steps",
           "mean_pmv"]
ZONES = ["oil_painting_gallery", "paper_works_gallery", "bronze_storage",
         "mixed_gallery", "public_lobby"]


def collect(prefix):
    rows = []
    for d in sorted(RES.glob(f"{prefix}_mockT3_seed*")):
        s = d / "eval.summary.json"
        if s.exists():
            rows.append(json.loads(s.read_text()))
    return rows


def agg(rows, key):
    vals = [r[key] for r in rows if key in r]
    return (np.mean(vals), np.std(vals) / np.sqrt(len(vals))) if vals else (float("nan"), float("nan"))


def main():
    scalar = collect("lagrangian")
    multi = collect("multi_lagrangian")
    print(f"scalar-lambda runs: {len(scalar)}   multi-lambda runs: {len(multi)}\n")
    print(f"{'metric':32s} {'scalar (mean±SEM)':>24s} {'multi (mean±SEM)':>24s}")
    for m in METRICS:
        sm, ss = agg(scalar, m)
        mm, ms = agg(multi, m)
        print(f"{m:32s} {sm:14.1f}±{ss:<8.1f} {mm:14.1f}±{ms:<8.1f}")
    print("\nPer-zone violation steps (mean):")
    print(f"{'zone':28s} {'scalar':>12s} {'multi':>12s}")
    for z in ZONES:
        k = f"violation_steps_{z}"
        sm, _ = agg(scalar, k)
        mm, _ = agg(multi, k)
        print(f"{z:28s} {sm:12.0f} {mm:12.0f}")

    # final per-clause multipliers from the multi runs
    print("\nFinal per-clause lambda (multi runs):")
    for d in sorted(RES.glob("multi_lagrangian_mockT3_seed*")):
        lf = d / "lambda_final.txt"
        if lf.exists():
            print(f"  {d.name}: {lf.read_text().strip()}")


if __name__ == "__main__":
    main()
