"""Sinergym + EnergyPlus museum environment (single-zone PoC).

Wraps Sinergym's default 5-zone office EnergyPlus model. The default
Sinergym config only exposes one zone (SPACE5-1) in the observation, so
this PoC treats that as a single museum gallery and computes the
conservation cost against the strictest envelope. Multi-zone observation
would require editing the IDF / Sinergym JSON config; that is left to
follow-up work.

The action space (2-D global heating + cooling setpoint) is forwarded
unchanged. The conservation cost is added to `info['cost']`, which
LagrangianCallback consumes via the standard CostRewardWrapper.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any
import numpy as np
import gymnasium as gym

from .constraints import ConservationCost, load_envelopes
from .rewards   import RewardConfig, compute_reward


SINERGYM_AVAILABLE_ZONE = "SPACE5-1"   # only zone Sinergym exposes

# Sinergym writes each env's EnergyPlus output to a directory rooted at the
# current working directory. Without intervention, hundreds of `Eplus-env-*`
# dirs litter the project root. We send them under results/sinergym_episodes/
# instead.
_SINERGYM_EPISODE_ROOT = Path(__file__).resolve().parents[2] / "results" / "sinergym_episodes"


class SinergymMuseumEnv(gym.Env):
    """Thin adapter: pass through Sinergym obs/action, inject cost into info."""

    metadata = {"render_modes": []}

    def __init__(
        self,
        conservation_yaml: str | Path,
        weather: str = "mixed",
    ):
        super().__init__()
        import sinergym   # noqa: F401  -- registers envs

        # Sinergym writes per-episode dirs to cwd; chdir into a managed
        # location so they don't pollute the project root. Each subprocess
        # worker chdir's independently before instantiating the env.
        _SINERGYM_EPISODE_ROOT.mkdir(parents=True, exist_ok=True)
        os.chdir(_SINERGYM_EPISODE_ROOT)

        env_id = f"Eplus-5zone-{weather}-continuous-v1"
        self._inner = gym.make(env_id)
        self.observation_space = self._inner.observation_space
        self.action_space      = self._inner.action_space

        # Cache observation variable indices.
        obs_vars = self._inner.unwrapped.observation_variables
        self._idx_T   = obs_vars.index("air_temperature")
        self._idx_RH  = obs_vars.index("air_humidity")
        self._idx_E   = obs_vars.index("HVAC_electricity_demand_rate")

        # We model ONE zone (the one Sinergym exposes) with the strictest
        # envelope, i.e. oil_painting_gallery. The conservation YAML still
        # carries the 5 zones for documentation; only the first matching
        # envelope is used in the cost computation.
        envs = load_envelopes(conservation_yaml)
        # Pick the entry that maps to SPACE5-1 (public_lobby in our YAML),
        # but switch its envelope to "oil_painting_gallery" so the cost is
        # meaningfully constraining.
        self._target_zone_name = "oil_painting_gallery"
        self.envelopes = {self._target_zone_name: envs[self._target_zone_name]}
        self.cost      = ConservationCost(self.envelopes, dt_hours=0.25)

        import yaml as _yaml
        rcfg = _yaml.safe_load(Path(conservation_yaml).read_text())["reward"]
        self.reward_cfg = RewardConfig(
            w_energy        = rcfg["w_energy"],
            w_comfort       = rcfg["w_comfort"],
            energy_norm_kwh = rcfg["energy_norm_kwh"],
            comfort_band    = rcfg["comfort_band"],
        )

    def reset(self, *, seed=None, options=None):
        obs, info = self._inner.reset(seed=seed, options=options)
        self.cost.reset()
        info["cost"] = 0.0
        return obs, info

    def step(self, action):
        obs, sinergym_reward, terminated, truncated, info = self._inner.step(action)
        T  = float(obs[self._idx_T])
        RH = float(obs[self._idx_RH])
        zone_state = {self._target_zone_name: (T, RH)}
        cost, cost_info = self.cost.step(zone_state)

        demand_w   = float(obs[self._idx_E])
        energy_kwh = demand_w * 0.25 / 1000.0
        pmv = 0.3 * (T - 22.0) + 0.01 * (RH - 50.0)

        # Use Sinergym's native LinearReward as the base (well-tuned for the
        # building/climate); the outer CostRewardWrapper adds -lambda*cost.
        # Sinergym's reward is negative (penalty); pass it through unchanged.
        reward = float(sinergym_reward)

        info.update({
            "cost":           cost,
            "cost_info":      cost_info,
            "raw_reward":     reward,
            "sinergym_reward": float(sinergym_reward),
            "energy_kwh":     energy_kwh,
            "pmv":            pmv,
            "T":              T,
            "RH":             RH,
            "comfort_pen":    max(0.0, abs(pmv) - self.reward_cfg.comfort_band),
        })
        return obs, reward, terminated, truncated, info

    def close(self):
        self._inner.close()

    def render(self, *args, **kwargs):
        return self._inner.render(*args, **kwargs)
