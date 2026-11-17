"""Unit and synthetic end-to-end tests for S2.4 real museum trace evaluation."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.v2.eval_real_traces import (  # noqa: E402
    PreparedTrace,
    _aggregate_group,
    clean_and_regularize_series,
    evaluate_prepared_trace,
    load_d1_traces,
    load_d4_traces,
    render_attenuation_svg,
    render_damage_svg,
)


def test_clean_and_regularize_removes_single_spike_and_splits_large_gaps():
    """Isolated 1-step glitches are replaced; multi-day gaps split segments without bridging."""
    dt_h = 0.5
    n1 = 72  # 36 hours
    n2 = 72  # 36 hours after a 12-hour outage
    t0 = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()

    ep1 = t0 + np.arange(n1) * dt_h * 3600.0
    ep2 = t0 + (n1 + 24 + np.arange(n2)) * dt_h * 3600.0  # 12h gap (> 6h threshold)
    ep = np.concatenate([ep1, ep2])

    tc = np.full(ep.size, 15.0)
    rh = np.full(ep.size, 50.0)
    # Inject isolated 1-step BMS spike inside segment 1 (similar to Vejle A/B/C glitches)
    tc[20] = 49.8
    rh[20] = 83.0

    segs, n_spikes = clean_and_regularize_series(
        ep, tc, rh, dt_hours=dt_h, max_gap_fill_hours=6.0, min_segment_hours=24.0
    )
    assert n_spikes == 1
    assert len(segs) == 2
    assert segs[0].temp_c.size == n1
    assert segs[1].temp_c.size == n2
    assert math.isclose(float(segs[0].temp_c[20]), 15.0, abs_tol=1e-9)
    assert math.isclose(float(segs[0].rh_percent[20]), 50.0, abs_tol=1e-9)


def test_evaluate_prepared_trace_attenuation_ordering_and_damage_outputs():
    """Verify monotonic buffering ordering across tau scales and complete 4-mechanism outputs."""
    dt_h = 0.25
    n_days = 45
    n_steps = int(n_days * 24 / dt_h)
    t0 = datetime(2021, 6, 1, tzinfo=timezone.utc).timestamp()
    t_hrs = np.arange(n_steps, dtype=np.float64) * dt_h

    # Synthetic diurnal (10%RH p2p) + multi-week (16%RH p2p) climate with T=22 degC
    temp_c = 22.0 + 2.0 * np.sin(2.0 * math.pi * t_hrs / 24.0)
    rh_air = (
        55.0
        + 5.0 * np.sin(2.0 * math.pi * t_hrs / 24.0)
        + 8.0 * np.sin(2.0 * math.pi * t_hrs / (30.0 * 24.0))
    )
    segs, n_sp = clean_and_regularize_series(
        t0 + t_hrs * 3600.0, temp_c, rh_air, dt_hours=dt_h
    )
    assert n_sp == 0
    trace = PreparedTrace(
        dataset_id="SYNTH",
        trace_id="zone_01",
        zone_group="test",
        label="Synthetic 45-day museum",
        dt_hours=dt_h,
        source_files=("synthetic",),
        segments=segs,
        n_raw_samples=n_steps,
        n_valid_steps=n_steps,
        n_spikes_replaced=0,
        duration_hours=float(n_steps * dt_h),
    )

    out = evaluate_prepared_trace(trace)
    air_sw = out["air_rh_fluctuation"]["swing_24h_p95"]
    assert 9.0 <= air_sw <= 11.5
    assert out["air_rh_fluctuation"]["hp30_p93_p07"] is not None

    objs = out["objects"]
    r_sculpt = objs["wooden_sculpture"]["surface_attenuation_ratio"]["swing_24h_p95_ratio"]
    r_panel_s = objs["panel_painting"]["surface_attenuation_ratio"]["swing_24h_p95_ratio"]
    r_panel_b = objs["panel_painting"]["bulk_attenuation_ratio"]["swing_24h_p95_ratio"]
    r_furn = objs["wooden_furniture"]["surface_attenuation_ratio"]["swing_24h_p95_ratio"]

    # Shorter tau transmits more of the 24h cycle than longer tau
    assert 1.0 > r_sculpt > r_panel_s > r_panel_b > r_furn > 0.0
    assert objs["panel_painting"]["mechanical"]["exact_max_strain_ratio"] >= 0.0
    assert (
        objs["panel_painting"]["mechanical"]["exact_max_strain_ratio"]
        <= objs["panel_painting"]["mechanical"]["smooth_max_strain_ratio"]
        <= objs["panel_painting"]["mechanical"]["exact_max_strain_ratio"] + 0.02
    )
    assert objs["paper"]["chemical"]["lm_equivalent"] > 0.0
    assert objs["bronze"]["bronze_chloride"]["exceedance_fraction"] > 0.5

    grp = _aggregate_group([out], "SYNTH Exterior & Gallery (<test>)")
    svg_a = ROOT / "results_summary" / "_test_tmp_att.svg"
    svg_d = ROOT / "results_summary" / "_test_tmp_dmg.svg"
    try:
        svg_a.parent.mkdir(parents=True, exist_ok=True)
        render_attenuation_svg([grp], svg_a)
        render_damage_svg([grp], svg_d)
        assert ET.fromstring(svg_a.read_text(encoding="utf-8")).tag.endswith("svg")
        assert ET.fromstring(svg_d.read_text(encoding="utf-8")).tag.endswith("svg")
    finally:
        svg_a.unlink(missing_ok=True)
        svg_d.unlink(missing_ok=True)
        if svg_a.parent.exists() and not any(svg_a.parent.iterdir()):
            svg_a.parent.rmdir()


def test_loaders_enforce_d1_dedup_and_d4_lscr_exclusion(tmp_path: Path):
    """Verify D1 NH082 deduplication & NH083 stitch, and D4 excludes LSCR_Oct2019/."""
    d1_dir = tmp_path / "D1"
    (d1_dir / "14233429").mkdir(parents=True)
    (d1_dir / "14233508").mkdir(parents=True)
    (d1_dir / "14233546").mkdir(parents=True)
    (d1_dir / "14233429" / "DataLoggers.csv").write_text(
        "Logger Nr.,Room,Floor,Roon No.\nNH082,E 10,E,10\nNH083,HP 1,HP,1\n",
        encoding="utf-8",
    )

    # 30 hours of 15-min data for NH082 (duplicated badly in 14233546) and split NH083
    t_start = datetime(2022, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
    lines_82 = []
    lines_83_a = []
    lines_83_b = []
    for k in range(120):
        dt = t_start + timedelta(minutes=15 * k)
        row = f"{dt:%d.%m.%Y},{dt:%H:%M:%S},50.0,20.0"
        lines_82.append(row)
        if k < 60:
            lines_83_a.append(row)
        else:
            lines_83_b.append(row)

    (d1_dir / "14233508" / "NH082.csv").write_text("\n".join(lines_82) + "\n", encoding="utf-8")
    # Simulate duplicated corrupted lines in 14233546/NH082.csv that loader must skip
    (d1_dir / "14233546" / "NH082.csv").write_text("\n".join(lines_82 * 2) + "\n", encoding="utf-8")
    (d1_dir / "14233546" / "NH083.csv").write_text("\n".join(lines_83_a) + "\n", encoding="utf-8")
    (d1_dir / "14233508" / "NH083.csv").write_text("\n".join(lines_83_b) + "\n", encoding="utf-8")

    d1_traces = load_d1_traces(d1_dir)
    by_id = {t.trace_id: t for t in d1_traces}
    assert set(by_id) == {"NH082", "NH083"}
    assert by_id["NH082"].n_raw_samples == 120
    assert by_id["NH083"].n_valid_steps == 120

    # D4: place files in both LSCR_Oct2019 (must be ignored) and Museum_Nov2019
    d4_dir = tmp_path / "D4"
    (d4_dir / "LSCR_Oct2019").mkdir(parents=True)
    (d4_dir / "Museum_Nov2019").mkdir(parents=True)
    t_nov = datetime(2019, 11, 1, 0, 0, tzinfo=timezone.utc)
    d4_rows = [
        f"{int((t_nov + timedelta(minutes=15 * k)).timestamp() * 1000)},55.0,21.0"
        for k in range(120)
    ]
    (d4_dir / "LSCR_Oct2019" / "1608daa8654c.txt").write_text("\n".join(d4_rows) + "\n", encoding="utf-8")
    (d4_dir / "Museum_Nov2019" / "1608daa8654c.txt").write_text("\n".join(d4_rows) + "\n", encoding="utf-8")

    d4_traces = load_d4_traces(d4_dir)
    assert len(d4_traces) == 1
    assert d4_traces[0].source_files == ("D4/Museum_Nov2019/1608daa8654c.txt",)
