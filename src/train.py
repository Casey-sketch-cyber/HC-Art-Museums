"""Training entrypoint.

Usage:
    python -m src.train --algo lagrangian --env mock --seed 0 --total-steps 200000
    python -m src.train --algo soft_penalty --env mock --penalty 5.0
    python -m src.train --algo vanilla --env mock
"""
from __future__ import annotations
import argparse
import json
import os
import time
from pathlib import Path

import gymnasium as gym
import numpy as np
import torch
import yaml
from stable_baselines3 import PPO, SAC
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv
from stable_baselines3.common.callbacks import CheckpointCallback

from .museum.env                  import make_museum_env
from .algorithms.lagrangian_ppo   import (
    CostRewardWrapper, LagrangianCallback, LagrangianConfig,
)
from .algorithms.multi_lagrangian import (
    MultiCostRewardWrapper, MultiLagrangianCallback, MultiLagrangianConfig,
)
from .museum.constraints          import N_CLAUSES

# CPU thread caps — safeguard against oversubscription in subprocess envs.
import os
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")


CONSERVATION = Path(__file__).resolve().parent.parent / "configs" / "conservation.yaml"
TRAIN_CFG    = Path(__file__).resolve().parent.parent / "configs" / "train.yaml"


def make_single_env(env_name: str, seed: int, episode_length: int,
                    wrapper_fn=None):
    def _factory():
        env = make_museum_env(env_name, CONSERVATION,
                              episode_length=episode_length, seed=seed)
        if wrapper_fn is not None:
            env = wrapper_fn(env)
        return env
    return _factory


class SoftPenaltyWrapper(gym.Wrapper):
    """Fold cost into reward with a fixed weight (baseline for ablation)."""
    def __init__(self, env, weight: float):
        super().__init__(env)
        self.weight = weight

    def step(self, action):
        obs, reward, term, trunc, info = self.env.step(action)
        info["raw_reward"] = reward
        info["cost"] = info.get("cost", 0.0)
        return obs, reward - self.weight * info["cost"], term, trunc, info


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--algo",
                   choices=["lagrangian", "multi_lagrangian", "soft_penalty",
                            "vanilla"],
                   default="lagrangian")
    p.add_argument("--env", default="mock",
                   help="mock | sinergym")
    p.add_argument("--learner", choices=["ppo", "sac"], default="ppo",
                   help="RL backbone; sac uses tanh-squashed actions + entropy")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--total-steps", type=int, default=None,
                   help="override the YAML")
    p.add_argument("--n-envs", type=int, default=None)
    p.add_argument("--penalty", type=float, default=5.0,
                   help="fixed weight for soft_penalty algo")
    p.add_argument("--cost-limit", type=float, default=None,
                   help="override Lagrangian cost target")
    p.add_argument("--run-name", default=None)
    p.add_argument("--log-dir", default="logs")
    p.add_argument("--result-dir", default="results")
    args = p.parse_args()

    cfg = yaml.safe_load(TRAIN_CFG.read_text())
    learner_cfg = cfg["sac"] if args.learner == "sac" else cfg["ppo"]
    if args.total_steps is None:
        args.total_steps = learner_cfg["total_timesteps"]
    if args.n_envs is None:
        args.n_envs = learner_cfg["n_envs"]

    episode_length = cfg["env"]["episode_length"]
    run_name = args.run_name or f"{args.algo}_{args.env}_seed{args.seed}_{int(time.time())}"
    run_dir = Path(args.result_dir) / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "args.json").write_text(json.dumps(vars(args), indent=2))

    # ---- Build vec env --------------------------------------------------
    lambda_init = cfg["lagrangian"]["lambda_init"]

    if args.algo == "lagrangian":
        wrapper = lambda e: CostRewardWrapper(e, lambda_init=lambda_init)
    elif args.algo == "multi_lagrangian":
        wrapper = lambda e: MultiCostRewardWrapper(e, lambda_init=lambda_init)
    elif args.algo == "soft_penalty":
        wrapper = lambda e: SoftPenaltyWrapper(e, weight=args.penalty)
    else:
        wrapper = None

    env_fns = [make_single_env(args.env, seed=args.seed + i,
                               episode_length=episode_length,
                               wrapper_fn=wrapper)
               for i in range(args.n_envs)]
    vec_env = SubprocVecEnv(env_fns) if args.n_envs > 1 else DummyVecEnv(env_fns)

    # ---- Set up learner (PPO or SAC) ------------------------------------
    learner_kwargs = dict(learner_cfg)
    learner_kwargs.pop("total_timesteps", None)
    learner_kwargs.pop("n_envs", None)
    policy_kwargs = learner_kwargs.pop("policy_kwargs", {})

    if args.learner == "sac":
        model = SAC(
            "MlpPolicy", vec_env,
            verbose=1,
            tensorboard_log=str(Path(args.log_dir) / run_name),
            policy_kwargs=policy_kwargs,
            seed=args.seed,
            device="cpu",   # small MLP; EnergyPlus is the bottleneck, not the net
            **learner_kwargs,
        )
    else:
        model = PPO(
            "MlpPolicy", vec_env,
            verbose=1,
            tensorboard_log=str(Path(args.log_dir) / run_name),
            policy_kwargs=policy_kwargs,
            seed=args.seed,
            device="cpu",   # SB3 MLP runs faster on CPU than GPU for small nets
            **learner_kwargs,
        )

    # ---- Callbacks ------------------------------------------------------
    callbacks = []
    lagr_cb = None
    if args.algo == "lagrangian":
        lcfg = LagrangianConfig(**cfg["lagrangian"])
        if args.cost_limit is not None:
            lcfg.cost_limit = args.cost_limit
        lagr_cb = LagrangianCallback(lcfg)
        callbacks.append(lagr_cb)
    elif args.algo == "multi_lagrangian":
        lag_yaml = dict(cfg["lagrangian"])
        lag_yaml.pop("cost_limit", None)   # scalar key not used here
        mcfg = MultiLagrangianConfig(**lag_yaml)
        # A scalar --cost-limit is broadcast to every clause budget.
        if args.cost_limit is not None:
            mcfg.cost_limits = [args.cost_limit] * N_CLAUSES
        lagr_cb = MultiLagrangianCallback(mcfg)
        callbacks.append(lagr_cb)
    callbacks.append(CheckpointCallback(
        save_freq=max(50_000 // max(args.n_envs, 1), 1),
        save_path=str(run_dir / "ckpts"),
        name_prefix="ppo",
    ))

    # ---- Train ----------------------------------------------------------
    model.learn(total_timesteps=args.total_steps, callback=callbacks,
                progress_bar=True)
    model.save(str(run_dir / "final_model.zip"))

    # ---- Record final lambda --------------------------------------------
    final_lambda = lagr_cb.current_lambda if lagr_cb is not None else lambda_init
    (run_dir / "lambda_final.txt").write_text(str(final_lambda))
    print(f"[train] done -> {run_dir}")
    print(f"[train] final lambda = {np.round(final_lambda, 3)}")


if __name__ == "__main__":
    main()
