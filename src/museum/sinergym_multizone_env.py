"""Multi-zone Sinergym + EnergyPlus museum environment.

Unlike the single-zone proof-of-concept in ``sinergym_env.py``, this env drives
all five EnergyPlus zones with independent dual-setpoint thermostats (built by
``make_multizone_building``) and observes each zone's temperature and humidity.
The five zones are mapped onto the five museum conservation envelopes, so the
constrained-RL controller can differentiate setpoints per collection, exactly
as it does on the mock simulator.

Observation : outdoor T/RH + per-zone (T, RH) for the 5 zones + whole-building
              HVAC electricity demand.
Action      : 10-D, [htg_i, clg_i] for i = 1..5, each affinely the schedule value.
Cost        : conservation cost summed over all 5 zones (scalar in info['cost'],
              four-clause vector in info['cost_vec']).
"""
from __future__ import annotations
import os
from pathlib import Path

import numpy as np
import gymnasium as gym

from .constraints import ConservationCost, load_envelopes
from .rewards import RewardConfig, compute_reward
from .make_multizone_building import build as build_multizone, actuators as mz_actuators, ZONES

try:
    from sinergym.utils.rewards import BaseReward as _BaseReward
except Exception:                       # pragma: no cover
    _BaseReward = object


class _ZeroReward(_BaseReward):
    """Stub reward so EplusEnv constructs; the museum reward is computed in step."""
    def __init__(self, **kwargs):
        pass

    def __call__(self, obs_dict):
        return 0.0, {}

_EPISODE_ROOT = Path(__file__).resolve().parents[2] / "results" / "sinergym_episodes_mz"
_WEATHER = {
    "hot":   "USA_AZ_Davis-Monthan.AFB.722745_TMY3.epw",
    "mixed": "USA_NY_New.York-J.F.Kennedy.Intl.AP.744860_TMY3.epw",
    "cool":  "USA_WA_Port.Angeles-William.R.Fairchild.Intl.AP.727885_TMY3.epw",
}


class MultiZoneSinergymMuseumEnv(gym.Env):
    """Per-zone-thermostat 5-zone EnergyPlus museum env."""

    metadata = {"render_modes": []}

    def __init__(self, conservation_yaml: str | Path, weather: str = "mixed"):
        super().__init__()
        from sinergym.envs.eplus_env import EplusEnv

        _EPISODE_ROOT.mkdir(parents=True, exist_ok=True)
        os.chdir(_EPISODE_ROOT)

        building = build_multizone()

        # EplusEnv expects already-expanded variables: {custom_name: (E+ var, key)}.
        # Per-zone observation: outdoor + (T, RH) for each of the five zones +
        # whole-building HVAC electricity demand.
        variables = {
            "outdoor_temperature":
                ("Site Outdoor Air DryBulb Temperature", "Environment"),
            "outdoor_humidity":
                ("Site Outdoor Air Relative Humidity", "Environment"),
        }
        for z in ZONES:
            variables[f"{z.lower()}_air_temperature"] = ("Zone Air Temperature", z)
        for z in ZONES:
            variables[f"{z.lower()}_air_humidity"] = ("Zone Air Relative Humidity", z)
        variables["HVAC_electricity_demand_rate"] = (
            "Facility Total HVAC Electricity Demand Rate", "Whole Building")
        actuators = mz_actuators()  # ordered htg1,clg1,...,htg5,clg5

        # Action bounds per the stock 5-zone env: htg in [12, 23.25], clg in
        # [23.25, 30], repeated for the five zones.
        low  = np.array([12.0, 23.25] * len(ZONES), dtype=np.float32)
        high = np.array([23.25, 30.0] * len(ZONES), dtype=np.float32)
        action_space = gym.spaces.Box(low=low, high=high,
                                      shape=(2 * len(ZONES),), dtype=np.float32)

        self._inner = EplusEnv(
            building_file=str(building),
            weather_files=_WEATHER[weather],
            action_space=action_space,
            time_variables=["month", "day_of_month", "hour"],
            variables=variables,
            meters={},   # energy read from the HVAC demand obs variable instead
            actuators=actuators,
            reward=_ZeroReward,
            env_name="museum-mz",
        )
        self.observation_space = self._inner.observation_space
        self.action_space = self._inner.action_space

        # Map observation indices by the custom variable names we defined.
        obs_vars = list(self._inner.observation_variables)
        self._idx_T  = {z: obs_vars.index(f"{z.lower()}_air_temperature") for z in ZONES}
        self._idx_RH = {z: obs_vars.index(f"{z.lower()}_air_humidity") for z in ZONES}
        self._idx_E  = obs_vars.index("HVAC_electricity_demand_rate")

        # Zone -> envelope mapping comes from the conservation YAML.
        all_env = load_envelopes(conservation_yaml)
        self._zone_to_env = {}   # sinergym zone key -> envelope-name
        for ename, env in all_env.items():
            self._zone_to_env[env.sinergym_zone] = ename
        self.envelopes = all_env
        self.cost = ConservationCost(all_env, dt_hours=0.25)

        # Museum reward config (energy + public-lobby comfort), reused from the
        # mock/single-zone envs for a consistent objective across backends.
        import yaml as _yaml
        rcfg = _yaml.safe_load(Path(conservation_yaml).read_text())["reward"]
        self.reward_cfg = RewardConfig(
            w_energy=rcfg["w_energy"], w_comfort=rcfg["w_comfort"],
            energy_norm_kwh=rcfg["energy_norm_kwh"], comfort_band=rcfg["comfort_band"],
        )
        self._lobby_zone = "public_lobby"   # comfort evaluated in the lobby

    def reset(self, *, seed=None, options=None):
        obs, info = self._inner.reset(seed=seed, options=options)
        self.cost.reset()
        info["cost"] = 0.0
        info["cost_vec"] = np.zeros(4)
        return obs, info

    def step(self, action):
        obs, sinergym_reward, terminated, truncated, info = self._inner.step(action)
        # Build zone_state keyed by envelope name (what ConservationCost expects).
        zone_state = {}
        for z in ZONES:
            T  = float(obs[self._idx_T[z]])
            RH = float(obs[self._idx_RH[z]])
            zone_state[self._zone_to_env[z]] = (T, RH)
        cost, cost_info = self.cost.step(zone_state)

        demand_w = float(obs[self._idx_E])
        energy_kwh = demand_w * 0.25 / 1000.0

        # Museum reward (energy + public-lobby comfort), computed here rather
        # than relying on Sinergym's reward (we pass a zero stub at construction).
        T_lobby, RH_lobby = zone_state[self._lobby_zone]
        pmv = 0.3 * (T_lobby - 22.0) + 0.01 * (RH_lobby - 50.0)
        reward, rew_info = compute_reward(energy_kwh, pmv, self.reward_cfg)

        info.update({
            "cost":       cost,
            "cost_vec":   cost_info["clause_vec"],
            "cost_info":  cost_info,
            "raw_reward": reward,
            "energy_kwh": energy_kwh,
            "pmv":        pmv,
            **rew_info,
        })
        return obs, float(reward), terminated, truncated, info

    def close(self):
        self._inner.close()

    def render(self, *args, **kwargs):
        return self._inner.render(*args, **kwargs)
