"""Lagrangian PPO with PID multiplier update.

Builds on Stable-Baselines3's PPO and modifies the reward stream:

      r_lagrangian(t) = r_env(t) - lambda * c(t)

where c(t) = info['cost'] is the per-step constraint violation magnitude
emitted by the museum env. The Lagrange multiplier `lambda` is updated
outside the PPO inner loop using a PID controller targeting a fixed
cost_limit (typically zero).

This is the standard formulation in safe-RL (see Stooke et al. 2020,
"Responsive Safety in Reinforcement Learning by PID Lagrangian Methods")
but implemented as a thin wrapper rather than a fork.

Cross-process synchronization: lambda lives as `_lambda_scalar` (float)
on each CostRewardWrapper, propagated to SubprocVecEnv workers via
`vec_env.set_attr("_lambda_scalar", new_value)`. This is the only way to
share dynamically updated state with subprocess-based parallel envs;
a plain Python dict ref is **NOT** shared across pickled subprocesses.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import numpy as np
import torch
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from stable_baselines3.common.vec_env import VecEnv
import gymnasium as gym


@dataclass
class LagrangianConfig:
    cost_limit:   float = 0.0
    lambda_init:  float = 1.0
    lambda_lr_p:  float = 0.05
    lambda_lr_i:  float = 0.0005
    lambda_lr_d:  float = 0.0
    lambda_min:   float = 0.0
    lambda_max:   float = 100.0


class CostRewardWrapper(gym.Wrapper):
    """Subtract `_lambda_scalar * cost` from env reward at step time.

    The scalar is updated by the parent process via SubprocVecEnv.set_attr
    after every rollout.
    """

    def __init__(self, env: gym.Env, lambda_init: float = 1.0):
        super().__init__(env)
        self._lambda_scalar = float(lambda_init)
        self._step_costs: list[float] = []

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        cost = float(info.get("cost", 0.0))
        info["raw_reward"] = reward
        info["cost"]       = cost
        self._step_costs.append(cost)
        return obs, reward - self._lambda_scalar * cost, terminated, truncated, info

    def reset(self, *, seed=None, options=None):
        self._step_costs.clear()
        return self.env.reset(seed=seed, options=options)

    def pop_cost_buffer(self) -> list[float]:
        out = self._step_costs[:]
        self._step_costs.clear()
        return out


class LagrangianCallback(BaseCallback):
    """PID controller on lambda + propagates lambda to all parallel envs."""

    def __init__(self, cfg: LagrangianConfig, verbose: int = 0):
        super().__init__(verbose)
        self.cfg = cfg
        self.current_lambda = cfg.lambda_init
        self._integral = 0.0
        self._prev_violation = 0.0
        self.history: list[dict[str, float]] = []

    def _on_step(self) -> bool:
        return True

    def _on_rollout_end(self) -> None:
        # Drain per-env cost buffers via VecEnv.env_method.
        try:
            all_costs_per_env = self.training_env.env_method("pop_cost_buffer")
        except Exception:
            all_costs_per_env = []
        flat = [c for env_costs in all_costs_per_env for c in env_costs]
        mean_cost = float(np.mean(flat)) if flat else 0.0
        violation = mean_cost - self.cfg.cost_limit

        # PID update.
        self._integral += violation
        derivative = violation - self._prev_violation
        delta = (self.cfg.lambda_lr_p * violation
                 + self.cfg.lambda_lr_i * self._integral
                 + self.cfg.lambda_lr_d * derivative)
        new_lambda = self.current_lambda + delta
        new_lambda = float(np.clip(new_lambda,
                                   self.cfg.lambda_min, self.cfg.lambda_max))
        self.current_lambda = new_lambda
        self._prev_violation = violation

        # Push to every parallel env (works for both DummyVecEnv and SubprocVecEnv).
        self.training_env.set_attr("_lambda_scalar", new_lambda)

        self.history.append({
            "lambda": new_lambda,
            "mean_cost": mean_cost,
            "violation": violation,
        })
        self.logger.record("lagrangian/lambda",    new_lambda)
        self.logger.record("lagrangian/mean_cost", mean_cost)
        self.logger.record("lagrangian/violation", violation)
