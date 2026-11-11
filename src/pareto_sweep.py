"""Pareto-front sweep over the Lagrangian cost_limit.

Trains several Lagrangian PPO runs with different `cost_limit` values, then
evaluates each. The trade-off curve (energy vs. conservation cost) is the
paper's headline figure.

Usage:
    python -m src.pareto_sweep --env mock --steps 100000 --cost-limits 0,0.5,1,2,5
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


RESULTS = Path("results")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--env", default="mock")
    p.add_argument("--steps", type=int, default=100000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--cost-limits", default="0,0.5,1,2,5,10",
                   help="comma-separated cost_limit values")
    p.add_argument("--n-envs", type=int, default=8)
    args = p.parse_args()

    limits = [float(x) for x in args.cost_limits.split(",")]
    points = []
    for cl in limits:
        run_name = f"sweep_cl{cl}_seed{args.seed}"
        print(f"\n[sweep] training cost_limit={cl}  ->  {run_name}")
        subprocess.run([
            sys.executable, "-m", "src.train",
            "--algo", "lagrangian",
            "--env", args.env,
            "--seed", str(args.seed),
            "--total-steps", str(args.steps),
            "--n-envs", str(args.n_envs),
            "--cost-limit", str(cl),
            "--run-name", run_name,
        ], check=True)
        subprocess.run([
            sys.executable, "-m", "src.evaluate",
            "--run", str(RESULTS / run_name),
            "--env", args.env,
        ], check=True)
        summary = json.loads(
            (RESULTS / run_name / "eval.summary.json").read_text()
        )
        summary["cost_limit"] = cl
        points.append(summary)

    df = pd.DataFrame(points)
    out = RESULTS / "pareto_sweep.csv"
    df.to_csv(out, index=False)
    print(f"\n[sweep] saved {out}")
    print(df[["cost_limit", "total_energy_kwh", "conservation_cost_total",
              "violation_steps"]].to_string(index=False))


if __name__ == "__main__":
    main()
