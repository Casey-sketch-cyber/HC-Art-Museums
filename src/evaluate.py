"""Deterministic evaluation across N episodes.

Usage:
    python -m src.evaluate --run results/lagrangian_mock_seed0_xxx
    python -m src.evaluate --rule fixed     # eval the rule baseline
    python -m src.evaluate --rule schedule
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from stable_baselines3 import PPO, SAC

from .museum.env             import make_museum_env, N_ZONES
from .algorithms.rule_based  import (
    RuleBasedFixedSetpoint, ScheduleBased,
    SinergymRuleFixed, SinergymSchedule, SinergymMultiZoneRuleFixed,
)


CONSERVATION = Path(__file__).resolve().parent.parent / "configs" / "conservation.yaml"
TRAIN_CFG    = Path(__file__).resolve().parent.parent / "configs" / "train.yaml"


def _run_episode(env, controller, env_zones: list[str]):
    obs, _ = env.reset(seed=42)
    done = trunc = False
    rows = []
    while not (done or trunc):
        action, _ = controller.predict(obs, deterministic=True)
        obs, reward, done, trunc, info = env.step(action)
        rows.append({
            "energy_kwh": info.get("energy_kwh", 0.0),
            "pmv": info.get("pmv", 0.0),
            "comfort_pen": info.get("comfort_pen", 0.0),
            "cost": info.get("cost", 0.0),
            "visitors": info.get("visitors", 0.0),
            **{f"viol_{z}": info.get("cost_info", {}).get(z, {}).get("violation", 0.0)
               for z in env_zones},
        })
    return pd.DataFrame(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", default=None,
                   help="path to a run dir produced by train.py")
    p.add_argument("--rule", choices=["fixed", "schedule"], default=None)
    p.add_argument("--env", default="mock")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default=None,
                   help="output CSV path; defaults to <run>/eval.csv")
    p.add_argument("--episode-length", type=int, default=None)
    args = p.parse_args()

    cfg = yaml.safe_load(TRAIN_CFG.read_text())
    ep_len = args.episode_length or cfg["env"]["episode_length"]

    env = make_museum_env(args.env, CONSERVATION,
                          episode_length=ep_len, seed=args.seed)
    zone_names = list(yaml.safe_load(CONSERVATION.read_text())["zones"].keys())

    if args.run:
        model_path = Path(args.run) / "final_model.zip"
        # Pick the loader matching the learner recorded at train time.
        learner = "ppo"
        args_json = Path(args.run) / "args.json"
        if args_json.exists():
            learner = json.loads(args_json.read_text()).get("learner", "ppo")
        model = (SAC if learner == "sac" else PPO).load(str(model_path))
        out_path = Path(args.out or (Path(args.run) / "eval.csv"))
        controller_name = Path(args.run).name
    elif args.rule == "fixed":
        if args.env == "sinergym_mz":
            model = SinergymMultiZoneRuleFixed()
        elif args.env == "sinergym":
            model = SinergymRuleFixed()
        else:
            model = RuleBasedFixedSetpoint()
        out_path = Path(args.out or f"results/rule_fixed_{args.env}/eval.csv")
        controller_name = f"rule_fixed_{args.env}"
    elif args.rule == "schedule":
        model = SinergymSchedule() if args.env == "sinergym" else ScheduleBased()
        out_path = Path(args.out or f"results/schedule_{args.env}/eval.csv")
        controller_name = f"schedule_{args.env}"
    else:
        raise SystemExit("specify --run or --rule")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = _run_episode(env, model, zone_names)
    df.to_csv(out_path, index=False)

    summary = {
        "controller": controller_name,
        "total_energy_kwh":   float(df.energy_kwh.sum()),
        "mean_pmv":           float(df.pmv.mean()),
        "comfort_violations": int((df.comfort_pen > 0).sum()),
        "conservation_cost_mean": float(df.cost.mean()),
        "conservation_cost_total": float(df.cost.sum()),
        "violation_steps": int((df.cost > 0).sum()),
        **{f"violation_steps_{z}": int((df[f"viol_{z}"] > 0).sum())
           for z in zone_names},
    }
    summary_path = out_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
