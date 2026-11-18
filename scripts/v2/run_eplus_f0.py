"""Run full-year F0 (21 C / 50% RH) EnergyPlus 23.2 verification across all 3 tiers (Task S1.2)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.museum_v2.eplus import (  # noqa: E402
    build_museum_epjson,
    compute_humidity_capacity_multipliers,
    find_energyplus_binary,
    run_energyplus_simulation,
)
from src.museum_v2.rom import load_building_tier  # noqa: E402

DEFAULT_EPW = (
    REPO_ROOT
    / "Eplus-env-museum-mz-res1"
    / "Eplus-env-sub_run1"
    / "USA_NY_New.York-J.F.Kennedy.Intl.AP.744860_TMY3.epw"
)


def _git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify S1.2 EnergyPlus museum F0 baseline.")
    parser.add_argument("--weather", type=Path, default=DEFAULT_EPW, help="Path to EPW file.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "results_summary" / "S1.2",
        help="Directory for summary JSON and Markdown.",
    )
    parser.add_argument("--tiers", nargs="+", default=["modern", "retrofitted", "historic"])
    args = parser.parse_args()

    ep_bin, _ = find_energyplus_binary()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    summary_tiers: dict[str, dict] = {}
    md_lines = [
        "# S1.2 EnergyPlus B 层 F0（21 °C / 50% RH）全年验证汇总",
        "",
        f"- **Git 提交号**: `{_git_head()}`",
        f"- **生成时间 (UTC)**: `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}`",
        f"- **EnergyPlus 二进制**: `{ep_bin}`",
        f"- **气象文件**: `{args.weather.name}`",
        "- **验收标准**: 各区全年 `>= 95%` 小时位于 `21±1 °C` 与 `50±5 %RH`，且逐时显热、加湿、除湿负荷无严重报错。",
        "",
    ]

    all_passed = True
    for tier in args.tiers:
        cfg = load_building_tier(tier)
        mults = compute_humidity_capacity_multipliers(cfg)
        epjson = build_museum_epjson(
            tier=tier,
            t_heat_sp_c=21.0,
            t_cool_sp_c=21.0,
            rh_hum_sp_percent=50.0,
            rh_dehum_sp_percent=50.0,
        )
        res = run_energyplus_simulation(epjson, args.weather, tier=tier)

        zones_info: dict[str, dict] = {}
        md_lines.extend(
            [
                f"## 档位 `{tier}`（湿度容倍数范围 `1+M_b/M_a`: `{min(mults.values()):.2f}–{max(mults.values()):.2f}`，Severe={len(res.severe_errors)}）",
                "",
                "| 分区 | `21±1°C` 达标 (%) | `50±5%RH` 达标 (%) | 温度极值 [°C] | RH 极值 [%] | 显热供热 [kWh] | 显热供冷 [kWh] | 加湿潜热 [kWh] | 除湿潜热 [kWh] |",
                "|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for j, zname in enumerate(res.zone_names):
            t_col = res.t_air_c[:, j]
            rh_col = res.rh_air_percent[:, j]
            t_ok = float(np.mean(np.abs(t_col - 21.0) <= 1.0) * 100.0)
            rh_ok = float(np.mean(np.abs(rh_col - 50.0) <= 5.0) * 100.0)
            if t_ok < 95.0 or rh_ok < 95.0 or res.severe_errors:
                all_passed = False

            sh = float(np.sum(res.e_sens_heat_kwh[:, j]))
            sc = float(np.sum(res.e_sens_cool_kwh[:, j]))
            hu = float(np.sum(res.e_hum_kwh[:, j]))
            de = float(np.sum(res.e_dehum_kwh[:, j]))
            zones_info[zname] = {
                "humidity_capacity_multiplier": mults[zname],
                "temp_within_21pm1_pct": round(t_ok, 4),
                "rh_within_50pm5_pct": round(rh_ok, 4),
                "t_min_c": round(float(np.min(t_col)), 3),
                "t_max_c": round(float(np.max(t_col)), 3),
                "rh_min_pct": round(float(np.min(rh_col)), 3),
                "rh_max_pct": round(float(np.max(rh_col)), 3),
                "sens_heat_kwh": round(sh, 2),
                "sens_cool_kwh": round(sc, 2),
                "hum_latent_kwh": round(hu, 2),
                "dehum_latent_kwh": round(de, 2),
            }
            md_lines.append(
                f"| `{zname}` | {t_ok:.2f} | {rh_ok:.2f} | {np.min(t_col):.2f}–{np.max(t_col):.2f} | "
                f"{np.min(rh_col):.2f}–{np.max(rh_col):.2f} | {sh:,.1f} | {sc:,.1f} | {hu:,.1f} | {de:,.1f} |"
            )

        md_lines.append("")
        summary_tiers[tier] = {
            "n_hours": res.n_hours,
            "warnings_count": len(res.warnings),
            "severe_errors": list(res.severe_errors),
            "totals_kwh": {
                "sens_heat": round(float(np.sum(res.e_sens_heat_kwh)), 2),
                "sens_cool": round(float(np.sum(res.e_sens_cool_kwh)), 2),
                "hum_latent": round(float(np.sum(res.e_hum_kwh)), 2),
                "dehum_latent": round(float(np.sum(res.e_dehum_kwh)), 2),
            },
            "zones": zones_info,
        }

    payload = {
        "task": "S1.2",
        "commit": _git_head(),
        "weather_epw": args.weather.name,
        "setpoint": {"t_heat_sp_c": 21.0, "t_cool_sp_c": 21.0, "rh_hum_sp_percent": 50.0, "rh_dehum_sp_percent": 50.0},
        "all_zones_pass_95pct": all_passed,
        "tiers": summary_tiers,
    }
    (args.out_dir / "f0_verification.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (args.out_dir / "summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"S1.2 verification finished: all_passed={all_passed} -> {args.out_dir}")
    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
