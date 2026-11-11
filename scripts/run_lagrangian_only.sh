#!/usr/bin/env bash
# Re-runs ONLY the Lagrangian arms + Pareto sweep after the lambda-propagation fix.
# Rule baselines, vanilla, and soft_penalty results from the previous run are unaffected.
set -euo pipefail
cd "$(dirname "$0")/.."

export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0}"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-2}"

MUSEUM_ENV="${MUSEUM_ENV:-mock}"
TOTAL="${TOTAL:-500000}"
NMUSEUM_ENVS="${NMUSEUM_ENVS:-16}"
SEEDS=(0 1 2)

echo "=== GPU visible: ${CUDA_VISIBLE_DEVICES} | MUSEUM_ENV: ${MUSEUM_ENV} | TOTAL: ${TOTAL} ==="

echo "=== Lagrangian baselines (3 seeds) ==="
for seed in "${SEEDS[@]}"; do
    python -m src.train --algo lagrangian --env "$MUSEUM_ENV" --seed "$seed" \
        --total-steps "$TOTAL" --n-envs "$NMUSEUM_ENVS" \
        --run-name "lagr_${MUSEUM_ENV}_seed${seed}"
    python -m src.evaluate --run "results/lagr_${MUSEUM_ENV}_seed${seed}" --env "$MUSEUM_ENV"
done

echo "=== Pareto sweep ==="
python -m src.pareto_sweep --env "$MUSEUM_ENV" --steps 200000 \
    --cost-limits 0,0.5,1,2,5,10 --n-envs "$NMUSEUM_ENVS"

echo "=== Aggregate figures ==="
python -m src.plot

echo "=== done ==="
