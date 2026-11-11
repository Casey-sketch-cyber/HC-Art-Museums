# Museum Safe RL — HVAC Co-Optimization

Code accompanying the paper *"Safe Reinforcement Learning with Conservation-Aware
Hard Constraints for HVAC Control in Art Museums: Formalizing EN 15757 Rate Limits
as a Constrained MDP"*.

## What's inside

A reproducible pipeline that:

1. Wraps an EnergyPlus museum simulation (via Sinergym) into a Gymnasium env.
2. Formalizes EN 15757 / ASHRAE Class A1 conservation rules
   (zone temperature/humidity bounds + dT/dt and dRH/dt rate caps) as a CMDP cost.
3. Trains a **Lagrangian PPO** controller that respects those constraints while
   minimizing HVAC energy and visitor discomfort.
4. Compares against four baselines (rule-based, schedule-based, soft-penalty PPO,
   unconstrained PPO).
5. Sweeps the Lagrange multiplier to draw a 3-D Pareto front
   (energy × comfort × conservation).

## Quickstart (smoke test, no EnergyPlus needed)

```bash
cd /workspace/guangxi
pip install -r requirements.txt
python -m src.train --env mock --algo lagrangian --total-steps 20000
python -m src.evaluate --env mock --run latest
python -m src.plot --run latest
```

The **mock env** is a lumped-capacity RC thermal model — it has the same observation
/ action interface as the real Sinergym env, so you can debug the whole pipeline
in ~2 min on a laptop before you ever touch EnergyPlus.

## Full pipeline (real EnergyPlus)

```bash
bash setup.sh                       # installs EnergyPlus 23.2 + Sinergym
bash scripts/run_full_experiment.sh # ~6–10 h on 32-core Xeon
```

## Directory layout

```
configs/
    conservation.yaml   # per-zone EN 15757 / ASHRAE Class A1 limits
    train.yaml          # PPO hyperparameters
src/
    museum/
        env.py          # MuseumEnv (sinergym wrapper) + MockMuseumEnv
        constraints.py  # ConservationConstraint
        rewards.py      # multi-objective reward composition
        visitor.py      # synthetic visitor flow generator
    algorithms/
        rule_based.py
        lagrangian_ppo.py   # PPO + PID-controlled Lagrange multiplier
    train.py
    evaluate.py
    pareto_sweep.py
    plot.py
scripts/                # top-level shell entrypoints
results/                # generated, gitignored
logs/                   # tensorboard
```

## Hardware sizing

Designed for: Xeon Gold 6226R (32 physical cores) + 256 GB RAM + 2× RTX A6000.

Realistic runtime per stage:

| Stage | Wall time |
|---|---|
| Smoke test (mock env, 20k steps) | 1–2 min |
| Single baseline (real EP, 1-year sim) | ~10 min |
| Lagrangian PPO training (500k steps, 16 parallel envs) | 6–10 h |
| Pareto sweep (10 lambdas × 200k steps) | 1–2 days |
| Full experiment (all baselines × 3 seeds + sweep + eval) | ~4–7 days |

GPU is essentially idle for this workload — bottleneck is EnergyPlus CPU.

## Reproducing the paper

```bash
bash scripts/run_full_experiment.sh
python -m src.plot --run final --paper-figs
```

Generates the 6 figures and 3 tables that go into the manuscript.
