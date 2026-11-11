"""Constraint-decomposed (multi-lambda) Lagrangian PPO.

Generalizes the scalar Lagrangian formulation in ``lagrangian_ppo.py`` to one
Lagrange multiplier per constraint family. The per-step conservation cost is
split into the four EN 15757 / ASHRAE clause groups

    c(t) = [ c_staticT(t), c_staticRH(t), c_rateT(t), c_rateRH(t) ],

each with its own budget d_k and its own PID-controlled multiplier lambda_k.
The surrogate reward becomes

    r_tilde(t) = r(t) - sum_k lambda_k * c_k(t).

The scalar formulation is the special case lambda_0 = ... = lambda_3, so this
module is a strict generalization. Decoupling the multipliers lets the agent
spend its violation budget where it is cheap (typically the static envelope)
while keeping the rate clauses tight, which the scalar formulation cannot do.

Cross-process synchronization mirrors the scalar version: the multiplier
vector lives as ``_lambda_vec`` (a list of floats) on each wrapper instance and
is pushed to SubprocVecEnv workers via ``vec_env.set_attr("_lambda_vec", ...)``.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import gymnasium as gym
from stable_baselines3.common.callbacks import BaseCallback

from ..museum.constraints import N_CLAUSES, CLAUSE_NAMES


@dataclass
class MultiLagrangianConfig:
    cost_limits: list[float] = field(default_factory=lambda: [0.0] * N_CLAUSES)
    lambda_init: float = 1.0
    lambda_lr_p: float = 0.05
    lambda_lr_i: float = 0.0005
    lambda_lr_d: float = 0.0
    lambda_min:  float = 0.0
    lambda_max:  float = 100.0


class MultiCostRewardWrapper(gym.Wrapper):
    """Subtract ``sum_k _lambda_vec[k] * cost_vec[k]`` from the env reward.

    The multiplier vector is updated by the parent process via
    ``SubprocVecEnv.set_attr`` after every rollout.
    """

    def __init__(self, env: gym.Env, lambda_init: float = 1.0):
        super().__init__(env)
        self._lambda_vec = [float(lambda_init)] * N_CLAUSES
        self._step_cost_vecs: list[np.ndarray] = []

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        cost_vec = np.asarray(
            info.get("cost_vec", np.zeros(N_CLAUSES)), dtype=np.float64
        )
        lam = np.asarray(self._lambda_vec, dtype=np.float64)
        info["raw_reward"] = reward
        info["cost"]       = float(cost_vec.sum())
        info["cost_vec"]   = cost_vec
        self._step_cost_vecs.append(cost_vec)
        penalty = float(np.dot(lam, cost_vec))
        return obs, reward - penalty, terminated, truncated, info

    def reset(self, *, seed=None, options=None):
        self._step_cost_vecs.clear()
        return self.env.reset(seed=seed, options=options)

    def pop_cost_buffer(self) -> list[list[float]]:
        # Return as plain lists so the values survive pickling cleanly.
        out = [v.tolist() for v in self._step_cost_vecs]
        self._step_cost_vecs.clear()
        return out


class MultiLagrangianCallback(BaseCallback):
    """One PID controller per constraint clause; pushes the multiplier vector."""

    def __init__(self, cfg: MultiLagrangianConfig, verbose: int = 0):
        super().__init__(verbose)
        self.cfg = cfg
        self.current_lambda = np.full(N_CLAUSES, cfg.lambda_init, dtype=np.float64)
        self._integral = np.zeros(N_CLAUSES, dtype=np.float64)
        self._prev_violation = np.zeros(N_CLAUSES, dtype=np.float64)
        self.history: list[dict] = []

    def _on_step(self) -> bool:
        return True

    def _on_rollout_end(self) -> None:
        try:
            per_env = self.training_env.env_method("pop_cost_buffer")
        except Exception:
            per_env = []
        # Flatten to (n_steps, N_CLAUSES) and take the per-clause mean.
        rows = [np.asarray(v, dtype=np.float64)
                for env_buf in per_env for v in env_buf]
        if rows:
            mean_cost = np.mean(np.stack(rows, axis=0), axis=0)
        else:
            mean_cost = np.zeros(N_CLAUSES, dtype=np.float64)

        limits = np.asarray(self.cfg.cost_limits, dtype=np.float64)
        violation = mean_cost - limits

        # Per-clause PID update.
        self._integral += violation
        derivative = violation - self._prev_violation
        delta = (self.cfg.lambda_lr_p * violation
                 + self.cfg.lambda_lr_i * self._integral
                 + self.cfg.lambda_lr_d * derivative)
        new_lambda = np.clip(self.current_lambda + delta,
                             self.cfg.lambda_min, self.cfg.lambda_max)
        self.current_lambda = new_lambda
        self._prev_violation = violation

        self.training_env.set_attr("_lambda_vec", new_lambda.tolist())

        rec = {"mean_cost": mean_cost.tolist(), "lambda": new_lambda.tolist()}
        self.history.append(rec)
        for k, name in enumerate(CLAUSE_NAMES):
            self.logger.record(f"multi_lagrangian/lambda_{name}", float(new_lambda[k]))
            self.logger.record(f"multi_lagrangian/cost_{name}",   float(mean_cost[k]))
        self.logger.record("multi_lagrangian/lambda_sum", float(new_lambda.sum()))
        self.logger.record("multi_lagrangian/cost_sum",   float(mean_cost.sum()))
