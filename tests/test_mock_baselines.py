"""锁住分区中点基线优于旧稿固定设定点这一检查，避免再把稻草人基线当结论。

验收（mock 环境，种子 0，全年）：
- 各区包络中点的恒定设定点：保护成本 < 100，违规步数 < 50
- rule_fixed（全区 22°C / 50%RH）全年能耗在 364–366 MWh
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from check_perzone_baseline import perzone_mid, rule_fixed, run  # noqa: E402


def test_perzone_midpoint_conservation_cost_is_small():
    result = run("perzone_mid", perzone_mid, seed=0)
    assert result["cost_total"] < 100
    assert result["violation_steps"] < 50


def test_rule_fixed_energy_matches_recorded_table():
    result = run("rule_fixed", rule_fixed, seed=0)
    assert 364 <= result["energy_mwh"] <= 366
