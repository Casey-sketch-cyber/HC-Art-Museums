"""Museum HVAC environments.

Two implementations behind a single interface:

  MockMuseumEnv         — lumped-capacity RC model, no external deps.
                          Use for unit tests, pipeline debugging, sanity checks.
  SinergymMuseumWrapper — adapter on top of Sinergym's 5-zone office env, with
                          zones re-interpreted as museum collection spaces and
                          conservation cost injected into the info dict.

Both expose:
  obs (np.ndarray), reward (float), terminated (bool), truncated (bool),
  info (dict containing 'cost' = conservation violation magnitude).

Action layout (continuous, shape (10,), in [-1, 1]):
  [ T_setpoint_zone1..5, RH_setpoint_zone1..5 ]
  mapped to physical ranges via _map_action().

Observation layout:
  [ T_zone1..5, RH_zone1..5,
    T_outside, RH_outside,
    sin(hour), cos(hour), sin(doy), cos(doy),
    visitor_count_norm,
    T_setpoint_prev1..5, RH_setpoint_prev1..5 ]
  -> shape (27,)
"""
from __future__ import annotations
from pathlib import Path
from typing import Any
import numpy as np
import gymnasium as gym
from gymnasium import spaces

from .constraints import ConservationCost, load_envelopes
from .rewards   import RewardConfig, compute_reward
from .visitor   import generate_visitor_series


ACTION_DIM = 10
OBS_DIM    = 27
N_ZONES    = 5
DT_HOURS   = 0.25            # 15-min control timestep
T_RANGE    = (16.0, 28.0)
RH_RANGE   = (30.0, 70.0)


def _map_action(action: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Map action in [-1, 1]^10 to (T_setpoints, RH_setpoints) in physical units."""
    action = np.clip(action, -1.0, 1.0)
    t_lo, t_hi   = T_RANGE
    rh_lo, rh_hi = RH_RANGE
    T_sp  = 0.5 * (action[:N_ZONES]  + 1.0) * (t_hi  - t_lo)  + t_lo
    RH_sp = 0.5 * (action[N_ZONES:]  + 1.0) * (rh_hi - rh_lo) + rh_lo
    return T_sp, RH_sp


class MockMuseumEnv(gym.Env):
    """Lumped RC thermal model of a 5-zone museum.

    Outdoor weather is a synthetic seasonal + diurnal pattern; visitor flow is
    drawn from the generator in visitor.py. The dynamics are deliberately
    simple so the env is fast (~1 ms/step) and the policy actually has to
    *learn something* — there's a real trade-off between energy and constraint
    cost when visitor heat loads spike.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        conservation_yaml: str | Path,
        episode_length: int = 35040,
        seed: int = 0,
    ):
        super().__init__()
        self.cfg_path = Path(conservation_yaml)
        self.envelopes = load_envelopes(self.cfg_path)
        self.zone_names = list(self.envelopes.keys())
        assert len(self.zone_names) == N_ZONES

        import yaml
        cfg = yaml.safe_load(self.cfg_path.read_text())
        rcfg = cfg["reward"]
        self.reward_cfg = RewardConfig(
            w_energy=rcfg["w_energy"],
            w_comfort=rcfg["w_comfort"],
            energy_norm_kwh=rcfg["energy_norm_kwh"],
            comfort_band=rcfg["comfort_band"],
        )

        self.cost = ConservationCost(self.envelopes, dt_hours=DT_HOURS)
        self.episode_length = episode_length
        self.action_space = spaces.Box(
            low=-1.0, high=1.0, shape=(ACTION_DIM,), dtype=np.float32,
        )
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(OBS_DIM,), dtype=np.float32,
        )

        # Thermal model parameters (per-zone). Tweak only if you know what you're doing.
        self.tau_hvac   = np.full(N_ZONES, 0.5)    # hours; HVAC response time constant
        self.tau_env    = np.full(N_ZONES, 8.0)    # hours; envelope leakage
        self.occ_gain   = np.full(N_ZONES, 0.005)  # K per person per step
        self.rh_inertia = np.full(N_ZONES, 0.7)    # how fast RH follows setpoint
        self.energy_coef = 2.0                     # kWh per K-step per zone

        self._seed = seed
        self.rng = np.random.default_rng(seed)
        self.step_idx = 0
        self.T = np.full(N_ZONES, 22.0)
        self.RH = np.full(N_ZONES, 50.0)
        self.T_sp_prev  = np.full(N_ZONES, 22.0)
        self.RH_sp_prev = np.full(N_ZONES, 50.0)
        self.visitors: np.ndarray | None = None

    # ---- gym API -----------------------------------------------------------

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        if seed is not None:
            self._seed = seed
            self.rng = np.random.default_rng(seed)
        self.step_idx = 0
        self.T  = np.full(N_ZONES, 22.0) + self.rng.normal(0.0, 0.3, N_ZONES)
        self.RH = np.full(N_ZONES, 50.0) + self.rng.normal(0.0, 2.0, N_ZONES)
        self.T_sp_prev  = self.T.copy()
        self.RH_sp_prev = self.RH.copy()
        self.cost.reset()
        self.visitors = generate_visitor_series(
            self.episode_length, dt_hours=DT_HOURS, seed=self._seed,
        )
        return self._obs(), {}

    def step(self, action: np.ndarray):
        T_sp, RH_sp = _map_action(np.asarray(action, dtype=np.float32))

        idx = min(self.step_idx, self.episode_length - 1)
        T_out, RH_out = self._weather(idx)
        occ = self.visitors[idx] if self.visitors is not None else 0.0

        # Thermal dynamics: 15-min Euler step.
        dt = DT_HOURS
        # HVAC driver, envelope leakage, occupancy gain proportional to per-zone share.
        occ_share = np.array([0.30, 0.20, 0.05, 0.30, 0.15])
        dT  = dt * ((T_sp  - self.T) / self.tau_hvac
                    + (T_out  - self.T) / self.tau_env
                    + self.occ_gain * occ * occ_share)
        dRH = dt * ((RH_sp - self.RH) / (self.tau_hvac / self.rh_inertia)
                    + (RH_out - self.RH) / self.tau_env)
        self.T  = self.T  + dT
        self.RH = np.clip(self.RH + dRH, 5.0, 100.0)

        # Energy proxy: kWh consumed proportional to abs(setpoint - achieved)
        # plus a base load.
        energy = float(self.energy_coef * np.sum(np.abs(T_sp - self.T)) + 5.0)

        # PMV proxy for public_lobby zone only.
        pmv = self._pmv(self.T[4], self.RH[4])

        reward, rew_info = compute_reward(energy, pmv, self.reward_cfg)

        zone_state = {name: (float(self.T[i]), float(self.RH[i]))
                      for i, name in enumerate(self.zone_names)}
        cost, cost_info = self.cost.step(zone_state)

        self.T_sp_prev  = T_sp
        self.RH_sp_prev = RH_sp
        self.step_idx += 1

        terminated = False
        truncated  = self.step_idx >= self.episode_length

        info = {
            "cost":       cost,
            "cost_vec":   cost_info["clause_vec"],
            "cost_info":  cost_info,
            "energy_kwh": energy,
            "pmv":        pmv,
            "T_out":      T_out,
            "RH_out":     RH_out,
            "visitors":   float(occ),
            **rew_info,
        }
        return self._obs(), float(reward), terminated, truncated, info

    # ---- helpers -----------------------------------------------------------

    def _weather(self, idx: int) -> tuple[float, float]:
        # Seasonal: yearly sine; daily: smaller sine; small noise.
        t = idx * DT_HOURS
        season = 12.0 * np.sin(2 * np.pi * (t / (365 * 24) - 0.25))    # +/-12 K
        daily  =  4.0 * np.sin(2 * np.pi * (t / 24 - 0.25))             # +/- 4 K
        T_out  = 15.0 + season + daily + self.rng.normal(0.0, 0.5)
        RH_out = float(np.clip(60.0 - 0.5 * season + self.rng.normal(0.0, 3.0), 10.0, 95.0))
        return float(T_out), RH_out

    def _pmv(self, T: float, RH: float) -> float:
        # Cheap PMV proxy; OK for the public_lobby penalty.
        return 0.3 * (T - 22.0) + 0.01 * (RH - 50.0)

    def _obs(self) -> np.ndarray:
        idx = min(self.step_idx, self.episode_length - 1)
        T_out, RH_out = self._weather(idx)
        h = (idx * DT_HOURS) % 24
        d = (idx * DT_HOURS) / 24 % 365
        occ = float(self.visitors[idx]) if self.visitors is not None else 0.0
        obs = np.concatenate([
            self.T,
            self.RH,
            np.array([T_out, RH_out,
                      np.sin(2 * np.pi * h / 24), np.cos(2 * np.pi * h / 24),
                      np.sin(2 * np.pi * d / 365), np.cos(2 * np.pi * d / 365),
                      occ / 200.0]),
            self.T_sp_prev,
            self.RH_sp_prev,
        ]).astype(np.float32)
        assert obs.shape == (OBS_DIM,), obs.shape
        return obs


# ---------------------------------------------------------------------------
# Sinergym wrapper — lazy-imported.
# ---------------------------------------------------------------------------

class SinergymMuseumWrapper(gym.Env):
    """Thin wrapper: wraps a Sinergym 5-zone env and adds conservation cost.

    Sinergym's default rewards/observations are mostly compatible. We:
      * Re-map zone names to museum collections (oil_painting_gallery, etc.).
      * Compute cost via the same ConservationCost as the mock env.
      * Pass cost in info['cost'] so the Lagrangian PPO can consume it.

    Note: this is a *wrapper around an existing IDF*. For a paper we still
    treat zones as 'representative' museum spaces; the methodology
    contribution is the constraint formulation, not the geometry.
    """

    def __init__(self, conservation_yaml: str | Path, weather: str = "hot"):
        super().__init__()
        import sinergym  # noqa: F401  -- registers the envs
        env_id = f"Eplus-5zone-{weather}-continuous-v1"
        self._inner = gym.make(env_id)
        self.observation_space = self._inner.observation_space
        self.action_space      = self._inner.action_space
        self.envelopes = load_envelopes(conservation_yaml)
        self.cost      = ConservationCost(self.envelopes, dt_hours=DT_HOURS)

    def reset(self, *, seed=None, options=None):
        obs, info = self._inner.reset(seed=seed, options=options)
        self.cost.reset()
        info["cost"] = 0.0
        return obs, info

    def step(self, action):
        obs, reward, terminated, truncated, info = self._inner.step(action)
        zone_state = self._extract_zone_state(info)
        cost, cost_info = self.cost.step(zone_state)
        info["cost"]      = cost
        info["cost_info"] = cost_info
        return obs, reward, terminated, truncated, info

    def _extract_zone_state(self, info: dict[str, Any]) -> dict[str, tuple[float, float]]:
        # Sinergym info dict contains zone variables under their EnergyPlus names.
        # Map them back to our museum zone names via the YAML's sinergym_zone field.
        out: dict[str, tuple[float, float]] = {}
        for museum_name, env in self.envelopes.items():
            sz = env.sinergym_zone
            T_key  = f"{sz}_air_temperature"
            RH_key = f"{sz}_relative_humidity"
            T  = float(info.get(T_key, 22.0))
            RH = float(info.get(RH_key, 50.0))
            out[museum_name] = (T, RH)
        return out


def make_museum_env(
    env_name: str,
    conservation_yaml: str | Path,
    episode_length: int = 35040,
    seed: int = 0,
    weather: str = "mixed",
) -> gym.Env:
    if env_name in ("museum-mock-v0", "mock"):
        return MockMuseumEnv(conservation_yaml, episode_length=episode_length, seed=seed)
    if env_name in ("museum-sinergym-v0", "sinergym"):
        # Single-zone proof-of-concept (one global thermostat).
        from .sinergym_env import SinergymMuseumEnv
        return SinergymMuseumEnv(conservation_yaml, weather=weather)
    if env_name in ("museum-sinergym-mz-v0", "sinergym_mz"):
        # Multi-zone: five independent per-zone thermostats (T2).
        from .sinergym_multizone_env import MultiZoneSinergymMuseumEnv
        return MultiZoneSinergymMuseumEnv(conservation_yaml, weather=weather)
    raise ValueError(f"unknown env: {env_name}")
