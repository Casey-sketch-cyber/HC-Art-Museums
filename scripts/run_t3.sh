#!/usr/bin/env bash
# T3 experiment: scalar-lambda vs multi-lambda (constraint-decomposed), matched.
set -e
cd "$(dirname "$0")/.."
STEPS=200000
NENVS=8
SEEDS="0 1 2"
for seed in $SEEDS; do
  for algo in lagrangian multi_lagrangian; do
    name="${algo}_mockT3_seed${seed}"
    echo "=== TRAIN $name ==="
    python3 -m src.train --algo "$algo" --env mock --total-steps $STEPS \
        --n-envs $NENVS --seed "$seed" --cost-limit 0.0 --run-name "$name"
    echo "=== EVAL $name ==="
    python3 -m src.evaluate --env mock --run "results/$name"
  done
done
echo "ALL_T3_DONE"
