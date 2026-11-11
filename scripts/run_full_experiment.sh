#!/usr/bin/env bash
# Full experiment matrix. Edit MUSEUM_ENV to switch between mock and real EnergyPlus.
set -euo pipefail
cd "$(dirname "$0")/.."

# Reserve GPU 0 only (GPU 1 is taken by another job).
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
# Cap CPU thread oversubscription — SubprocVecEnv already parallelises envs.
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-2}"
# Sinergym + EnergyPlus paths.
export EPLUS_PATH="${EPLUS_PATH:-/usr/local/EnergyPlus-23-2-0}"
export PYTHONPATH="${EPLUS_PATH}:${PYTHONPATH:-}"

MUSEUM_ENV="${MUSEUM_ENV:-mock}"                  # mock | sinergym
TOTAL="${TOTAL:-500000}"
NMUSEUM_ENVS="${NMUSEUM_ENVS:-16}"
SEEDS=(0 1 2)

echo "=== GPU visible: ${CUDA_VISIBLE_DEVICES} | MUSEUM_ENV: ${MUSEUM_ENV} | TOTAL: ${TOTAL} | NMUSEUM_ENVS: ${NMUSEUM_ENVS} ==="

echo "=== 1. Rule baselines ==="
python -m src.evaluate --rule fixed    --env "$MUSEUM_ENV"
python -m src.evaluate --rule schedule --env "$MUSEUM_ENV"

echo "=== 2. Trained baselines (3 seeds each) ==="
for seed in "${SEEDS[@]}"; do
    python -m src.train --algo vanilla       --env "$MUSEUM_ENV" --seed "$seed" \
        --total-steps "$TOTAL" --n-envs "$NMUSEUM_ENVS" \
        --run-name "vanilla_${MUSEUM_ENV}_seed${seed}"
    python -m src.evaluate --run "results/vanilla_${MUSEUM_ENV}_seed${seed}" --env "$MUSEUM_ENV"

    python -m src.train --algo soft_penalty  --env "$MUSEUM_ENV" --seed "$seed" \
        --total-steps "$TOTAL" --n-envs "$NMUSEUM_ENVS" --penalty 5.0 \
        --run-name "soft_${MUSEUM_ENV}_seed${seed}"
    python -m src.evaluate --run "results/soft_${MUSEUM_ENV}_seed${seed}" --env "$MUSEUM_ENV"

    python -m src.train --algo lagrangian    --env "$MUSEUM_ENV" --seed "$seed" \
        --total-steps "$TOTAL" --n-envs "$NMUSEUM_ENVS" \
        --run-name "lagr_${MUSEUM_ENV}_seed${seed}"
    python -m src.evaluate --run "results/lagr_${MUSEUM_ENV}_seed${seed}" --env "$MUSEUM_ENV"
done

echo "=== 3. Pareto sweep (single seed, faster) ==="
python -m src.pareto_sweep --env "$MUSEUM_ENV" --steps 200000 \
    --cost-limits 0,0.5,1,2,5,10 --n-envs "$NMUSEUM_ENVS"

echo "=== 4. Aggregate figures ==="
python -m src.plot

echo "=== done ==="
