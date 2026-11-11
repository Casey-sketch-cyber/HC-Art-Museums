#!/usr/bin/env bash
# T2 (humidified multi-zone): rule-fixed baseline + Lagrangian-PPO x3 seeds.
set -e
cd "$(dirname "$0")/.."
STEPS=200000
echo "=== BASELINE rule-fixed (multi-zone, humidified) ==="
rm -rf Eplus-env-* 2>/dev/null || true
python3 -m src.evaluate --env sinergym_mz --rule fixed \
    --out /workspace/guangxi/results/rule_fixed_sinergym_mz/eval.csv
for seed in 0 1 2; do
  name="lagr_mz_seed${seed}"
  echo "=== TRAIN $name ==="
  python3 -m src.train --algo lagrangian --env sinergym_mz --total-steps $STEPS \
      --n-envs 1 --seed $seed --cost-limit 0.0 --run-name "$name" \
      --result-dir /workspace/guangxi/results --log-dir /workspace/guangxi/logs
  echo "=== EVAL $name ==="
  rm -rf Eplus-env-* 2>/dev/null || true
  python3 -m src.evaluate --env sinergym_mz --run "/workspace/guangxi/results/$name"
done
echo "ALL_T2_DONE"
