"""Evaluate S2.2/S2.3 object hygrothermal response & four-mechanism damage risks on D1-D4 real museum traces.

Outputs standardized JSON, Markdown summary, and vector SVG figures under
``results_summary/S2.4/`` for Tasks S2.4 and Results Section 2 of the iScience paper.
Strictly excludes D5 (unknown license, ``usable=False``) and D4 ``LSCR_Oct2019/``
(uncontrolled robotics laboratory) per ``docs/DATASETS.md``.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as xml_escape
from typing import Any

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.data.fetch_D4 import DATASET as D4_SPEC  # noqa: E402
from src.museum_v2.damage import (  # noqa: E402
    ACTIVATION_ENERGY_PAPER_J_MOL,
    ACTIVATION_ENERGY_VARNISH_J_MOL,
    METAL_CRH_PRESETS,
    WOOD_YIELD_STRAIN_DEFAULT,
    biological_mould_risk,
    chemical_degradation_risk,
    estimate_proofed_envelope,
    mechanical_strain_risk,
    metal_corrosion_risk,
)
from src.museum_v2.objects import (  # noqa: E402
    DEFAULT_OBJECTS_CONFIG,
    compute_object_response,
    load_object_specs,
)

ROOT = Path(__file__).resolve().parents[2]
EXCEL_EPOCH_UTC = datetime(1899, 12, 30, tzinfo=timezone.utc)
HOURS_PER_YEAR = 8760.0

# D4 Table 2 sensor mapping (``Museum_Nov2019/description_table.png`` & Botero-Valencia et al., 2022)
D4_CONTINUOUS_SENSORS = frozenset({
    "1608daa8654c",
    "234132342d58",
    "2e08daa8654c",
    "4608daa8654c",
    "4d1736342d58",
    "ac07daa8654c",
    "bb3c32342d58",
    "e61836342d58",
    "ea3c32342d58",
})

# D2 indoor room metadata mapping (from ``docs/DATASETS.md`` & ``00_List-of-data-files.pdf``)
D2_ZONE_FILES: list[tuple[str, str, str, float]] = [
    ("01_ribe-basic-storage-climate.txt", "Ribe Basic Storage", "basic_storage", 0.5),
    ("02_ribe-dry-storage-climate.txt", "Ribe Dry Storage", "dry_storage", 0.5),
    ("03_vejle-basic-storage-climate-A.txt", "Vejle Basic Storage A", "basic_storage", 1.0 / 6.0),
    ("04_vejle-basic-storage-climate-C.txt", "Vejle Basic Storage C", "basic_storage", 1.0 / 6.0),
    ("05_vejle-basic-storage-climate-D.txt", "Vejle Basic Storage D", "basic_storage", 1.0 / 6.0),
    ("06_vejle-dry-storage-climate-B.txt", "Vejle Dry Storage B", "dry_storage", 1.0 / 6.0),
    ("07_randers-basic-storage-climate.txt", "Randers Basic Storage", "basic_storage", 1.0 / 6.0),
    ("08_randers-dry-storage-climate.txt", "Randers Dry Storage", "dry_storage", 1.0 / 6.0),
    ("09_oerholm-basic-storage-climate-P1.txt", "Oerholm Hall P1 Basic Storage", "basic_storage", 0.5),
    ("10_oerholm-basic-storage-climate-P2.txt", "Oerholm Hall P2 Basic Storage", "basic_storage", 1.0),
    ("11_oerholm-basic-storage-climate-P3.txt", "Oerholm Hall P3 Basic Storage", "basic_storage", 1.0),
]


@dataclass(frozen=True)
class ContiguousSegment:
    """Gap-free uniform-grid hygrothermal time series segment."""

    dt_hours: float
    start_epoch_s: float
    end_epoch_s: float
    temp_c: np.ndarray
    rh_percent: np.ndarray


@dataclass(frozen=True)
class PreparedTrace:
    """Cleaned, regularized museum microclimate trace split at large outages."""

    dataset_id: str
    trace_id: str
    zone_group: str
    label: str
    dt_hours: float
    source_files: tuple[str, ...]
    segments: tuple[ContiguousSegment, ...]
    n_raw_samples: int
    n_valid_steps: int
    n_spikes_replaced: int
    duration_hours: float


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _git_head_sha(repo_root: Path = ROOT) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True, stderr=subprocess.DEVNULL
        ).strip()
        return out
    except Exception:
        return "unknown"


def _git_is_dirty(repo_root: Path = ROOT) -> bool:
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=repo_root, text=True, stderr=subprocess.DEVNULL
        )
        return bool(out.strip())
    except Exception:
        return True


def _parse_d1_timestamp(date_s: str, time_s: str) -> float:
    """Fast parser for D1 ``DD.MM.YYYY,HH:MM:SS`` into UTC epoch seconds."""
    d_p = date_s.strip().split(".")
    t_p = time_s.strip().split(":")
    dt = datetime(
        int(d_p[2]), int(d_p[1]), int(d_p[0]),
        int(t_p[0]), int(t_p[1]), int(t_p[2]),
        tzinfo=timezone.utc,
    )
    return dt.timestamp()


def _parse_d2_timestamp(dt_s: str) -> float:
    """Fast parser for D2 ``DD-MM-YYYY HH:MM`` or ``DD/MM/YYYY HH:MM``."""
    s = dt_s.strip().replace("/", "-")
    date_part, time_part = s.split()
    d, m, y = date_part.split("-")
    hh, mm = time_part.split(":")
    return datetime(int(y), int(m), int(d), int(hh), int(mm), tzinfo=timezone.utc).timestamp()


def clean_and_regularize_series(
    epochs_s: np.ndarray,
    temp_c: np.ndarray,
    rh_percent: np.ndarray,
    *,
    dt_hours: float,
    max_gap_fill_hours: float = 6.0,
    min_segment_hours: float = 24.0,
    spike_delta_temp_c: float = 10.0,
    spike_delta_rh: float = 20.0,
) -> tuple[tuple[ContiguousSegment, ...], int]:
    """Bin raw samples onto a uniform grid, remove isolated 1-step glitches, and split outages.

    Parameters
    ----------
    epochs_s, temp_c, rh_percent:
        Raw timestamp [s], temperature [degC], and relative humidity [%] arrays.
    dt_hours:
        Target uniform timestep [h].
    max_gap_fill_hours:
        Maximum missing interval [h] bridged by linear interpolation. Larger gaps
        split the series into separate :class:`ContiguousSegment` instances to avoid
        fabricating multi-day/month ramps.
    min_segment_hours:
        Minimum contiguous duration [h] retained for dynamic analysis.
    """
    if epochs_s.size == 0:
        return (), 0
    dt_s = float(dt_hours) * 3600.0
    valid = (
        np.isfinite(epochs_s)
        & np.isfinite(temp_c)
        & np.isfinite(rh_percent)
        & (rh_percent >= 0.0)
        & (rh_percent <= 100.0)
        & (temp_c >= -50.0)
        & (temp_c <= 80.0)
    )
    if not np.any(valid):
        return (), 0

    ep = epochs_s[valid]
    tc = temp_c[valid]
    rh = rh_percent[valid]

    order = np.argsort(ep, kind="mergesort")
    ep = ep[order]
    tc = tc[order]
    rh = rh[order]

    # Map timestamps onto integer grid indices k = round((ep - t0) / dt_s)
    t0 = math.floor(float(ep[0]) / dt_s) * dt_s
    idx = np.rint((ep - t0) / dt_s).astype(np.int64)
    uniq_idx, inv, counts = np.unique(idx, return_inverse=True, return_counts=True)
    tc_bin = np.bincount(inv, weights=tc) / counts
    rh_bin = np.bincount(inv, weights=rh) / counts

    # Remove isolated single-bin telemetry spikes (jump > threshold & immediately return)
    n_spikes = 0
    if uniq_idx.size >= 3 and dt_hours <= 1.0:
        max_neighbor_steps = max(1, int(round(1.5 / dt_hours)))
        for k in range(1, uniq_idx.size - 1):
            if (
                uniq_idx[k] - uniq_idx[k - 1] <= max_neighbor_steps
                and uniq_idx[k + 1] - uniq_idx[k] <= max_neighbor_steps
            ):
                dt_prev = abs(tc_bin[k] - tc_bin[k - 1])
                dt_next = abs(tc_bin[k] - tc_bin[k + 1])
                dr_prev = abs(rh_bin[k] - rh_bin[k - 1])
                dr_next = abs(rh_bin[k] - rh_bin[k + 1])
                nbr_t = abs(tc_bin[k + 1] - tc_bin[k - 1])
                nbr_r = abs(rh_bin[k + 1] - rh_bin[k - 1])
                if (
                    (dt_prev > spike_delta_temp_c and dt_next > spike_delta_temp_c and nbr_t < 0.35 * spike_delta_temp_c)
                    or (dr_prev > spike_delta_rh and dr_next > spike_delta_rh and nbr_r < 0.35 * spike_delta_rh)
                ):
                    tc_bin[k] = 0.5 * (tc_bin[k - 1] + tc_bin[k + 1])
                    rh_bin[k] = 0.5 * (rh_bin[k - 1] + rh_bin[k + 1])
                    n_spikes += 1

    max_fill_steps = max(1, int(round(max_gap_fill_hours / dt_hours)))
    step_gaps = np.diff(uniq_idx)
    split_points = np.where(step_gaps > max_fill_steps)[0] + 1
    bounds = np.concatenate(([0], split_points, [uniq_idx.size]))

    min_steps = max(2, int(math.ceil(min_segment_hours / dt_hours)))
    segments: list[ContiguousSegment] = []
    for s0, s1 in zip(bounds[:-1], bounds[1:]):
        seg_idx = uniq_idx[s0:s1]
        span_steps = int(seg_idx[-1] - seg_idx[0]) + 1
        if span_steps < min_steps:
            continue
        full_k = np.arange(seg_idx[0], seg_idx[-1] + 1, dtype=np.int64)
        if seg_idx.size == span_steps:
            t_seg = tc_bin[s0:s1].copy()
            r_seg = rh_bin[s0:s1].copy()
        else:
            t_seg = np.interp(full_k, seg_idx, tc_bin[s0:s1])
            r_seg = np.interp(full_k, seg_idx, rh_bin[s0:s1])
        r_seg = np.clip(r_seg, 0.0, 100.0)
        segments.append(
            ContiguousSegment(
                dt_hours=float(dt_hours),
                start_epoch_s=t0 + float(full_k[0]) * dt_s,
                end_epoch_s=t0 + float(full_k[-1]) * dt_s,
                temp_c=np.ascontiguousarray(t_seg, dtype=np.float64),
                rh_percent=np.ascontiguousarray(r_seg, dtype=np.float64),
            )
        )
    return tuple(segments), n_spikes


def _sliding_24h_swing(series: np.ndarray, dt_hours: float) -> np.ndarray:
    """Exact rolling peak-to-peak swing (max - min) over 24 h windows [num_windows]."""
    win = max(2, int(round(24.0 / dt_hours)))
    if series.size < win:
        return np.array([float(np.max(series) - np.min(series))], dtype=np.float64)
    # Non-overlapping daily blocks plus 50%-shifted overlapping blocks avoids slow O(N*W) deque
    # on 6M samples while closely bounding exact sliding swings; wait: stride=1 via numpy view for W<=288 is fast too!
    if win <= 288 and series.size <= 500_000:
        windows = np.lib.stride_tricks.sliding_window_view(series, win)
        return np.max(windows, axis=-1) - np.min(windows, axis=-1)
    n_blocks = series.size // win
    trimmed = series[: n_blocks * win].reshape(n_blocks, win)
    return np.max(trimmed, axis=-1) - np.min(trimmed, axis=-1)


def _centered_moving_average(series: np.ndarray, half_window_steps: int) -> np.ndarray:
    """O(N) centered moving average using cumulative sums with edge truncation."""
    n = series.size
    csum = np.concatenate(([0.0], np.cumsum(series, dtype=np.float64)))
    idx = np.arange(n, dtype=np.int64)
    lo = np.maximum(0, idx - half_window_steps)
    hi = np.minimum(n, idx + half_window_steps + 1)
    return (csum[hi] - csum[lo]) / (hi - lo)


def summarize_fluctuations(
    segments: tuple[ContiguousSegment, ...],
    series_per_seg: list[np.ndarray],
) -> dict[str, Any]:
    """Compute distribution, 24h peak-to-peak swing, and <30d high-pass fluctuation stats."""
    all_vals = np.concatenate(series_per_seg)
    swings_24h = np.concatenate([
        _sliding_24h_swing(arr, seg.dt_hours) for seg, arr in zip(segments, series_per_seg)
    ])

    hp30_devs: list[np.ndarray] = []
    for seg, arr in zip(segments, series_per_seg):
        dur_h = arr.size * seg.dt_hours
        if dur_h >= 30.0 * 24.0:
            half_w = max(1, int(round(15.0 * 24.0 / seg.dt_hours)))
            ma30 = _centered_moving_average(arr, half_w)
            hp30_devs.append(arr - ma30)

    out: dict[str, Any] = {
        "mean": round(float(np.mean(all_vals)), 4),
        "std": round(float(np.std(all_vals)), 4),
        "min": round(float(np.min(all_vals)), 4),
        "p05": round(float(np.percentile(all_vals, 5.0)), 4),
        "p95": round(float(np.percentile(all_vals, 95.0)), 4),
        "max": round(float(np.max(all_vals)), 4),
        "span_total": round(float(np.max(all_vals) - np.min(all_vals)), 4),
        "span_p95_p05": round(float(np.percentile(all_vals, 95.0) - np.percentile(all_vals, 5.0)), 4),
        "swing_24h_mean": round(float(np.mean(swings_24h)), 4),
        "swing_24h_p95": round(float(np.percentile(swings_24h, 95.0)), 4),
        "swing_24h_max": round(float(np.max(swings_24h)), 4),
    }
    if hp30_devs:
        devs = np.concatenate(hp30_devs)
        out["hp30_std"] = round(float(np.std(devs)), 4)
        out["hp30_p93_p07"] = round(
            float(np.percentile(devs, 93.0) - np.percentile(devs, 7.0)), 4
        )
    else:
        out["hp30_std"] = None
        out["hp30_p93_p07"] = None
    return out


def evaluate_prepared_trace(trace: PreparedTrace) -> dict[str, Any]:
    """Run S2.2 object response + S2.3 four-mechanism damage risks on one prepared trace."""
    specs = load_object_specs()
    segs = trace.segments
    if not segs:
        raise ValueError(f"Trace {trace.dataset_id}/{trace.trace_id} has no valid contiguous segments")

    seg_hours = [seg.temp_c.size * seg.dt_hours for seg in segs]
    total_hours = float(sum(seg_hours))
    t_all = np.concatenate([seg.temp_c for seg in segs])
    rh_all = np.concatenate([seg.rh_percent for seg in segs])
    rh_global_mean = float(np.mean(rh_all))

    # Air fluctuation baseline
    air_fluc = summarize_fluctuations(segs, [seg.rh_percent for seg in segs])

    # Precompute S2.2 object responses per contiguous segment under two initializations:
    # 1) "first_sample" (default): object starts equilibrated with seg.rh_percent[0]
    # 2) "segment_mean" (sensitivity): object starts equilibrated with seg mean RH
    seg_means = [float(np.mean(seg.rh_percent)) for seg in segs]
    max_init_offset_rh = max(abs(float(seg.rh_percent[0]) - sm) for seg, sm in zip(segs, seg_means))

    obj_resps: dict[str, list[Any]] = {cat: [] for cat in specs}
    obj_resps_mean: dict[str, list[Any]] = {cat: [] for cat in specs}
    for cat, spec in specs.items():
        for seg, sm in zip(segs, seg_means):
            obj_resps[cat].append(
                compute_object_response(seg.rh_percent, spec, dt_hours=seg.dt_hours)
            )
            obj_resps_mean[cat].append(
                compute_object_response(
                    seg.rh_percent,
                    spec,
                    dt_hours=seg.dt_hours,
                    rh_init_surface=sm,
                    rh_init_bulk=sm,
                )
            )

    def _agg_chem(rh_list: list[np.ndarray], ea: float) -> dict[str, float]:
        dose_sum = 0.0
        lm_mean_sum = 0.0
        lt1_hours = 0.0
        for seg, rh_s, wh in zip(segs, rh_list, seg_hours):
            res = chemical_degradation_risk(seg.temp_c, rh_s, ea_j_per_mol=ea)
            dose_sum += wh * float(res.dose_rate)
            lm_mean_sum += wh * float(res.lm_mean)
            lt1_hours += float(np.sum(np.asarray(res.lm_series) < 1.0)) * seg.dt_hours
        dose_rate = dose_sum / total_hours
        return {
            "lm_equivalent": round(1.0 / dose_rate, 4),
            "lm_mean": round(lm_mean_sum / total_hours, 4),
            "dose_rate": round(dose_rate, 6),
            "frac_lm_lt_1": round(lt1_hours / total_hours, 6),
        }

    def _agg_bio(rh_list: list[np.ndarray]) -> dict[str, float]:
        exc_h = 0.0
        germ = 0.0
        rh_h = 0.0
        for seg, rh_s in zip(segs, rh_list):
            res = biological_mould_risk(seg.temp_c, rh_s, substrate="I", dt_hours=seg.dt_hours)
            exc_h += float(res.exceedance_hours_exact)
            germ += float(res.germination_index)
            rh_h += float(res.exceedance_rh_hours)
        return {
            "exceedance_hours": round(exc_h, 4),
            "exceedance_fraction": round(exc_h / total_hours, 6),
            "germination_index": round(germ, 6),
            "germination_index_per_year": round(germ * (HOURS_PER_YEAR / total_hours), 6),
            "exceedance_rh_hours": round(rh_h, 4),
        }

    def _agg_mech(resps_list: list[Any], mode: str) -> dict[str, Any]:
        max_exact = 0.0
        max_smooth = 0.0
        yield_h = 0.0
        fail_h = 0.0
        for resp, wh in zip(resps_list, seg_hours):
            if mode == "gradient":
                res = mechanical_strain_risk(resp.surface, resp.bulk, mode="gradient")
            else:
                res = mechanical_strain_risk(
                    resp.bulk, rh_reference=rh_global_mean, mode="acclimatized"
                )
            max_exact = max(max_exact, float(res.exact_max_strain_ratio))
            max_smooth = max(max_smooth, float(res.max_strain_ratio))
            yield_h += wh * float(res.yield_exceedance_fraction_exact)
            fail_h += wh * float(res.failure_exceedance_fraction_exact)
        return {
            "mode": mode,
            "exact_max_strain_ratio": round(max_exact, 5),
            "smooth_max_strain_ratio": round(max_smooth, 5),
            "yield_exceedance_fraction": round(yield_h / total_hours, 6),
            "failure_exceedance_fraction": round(fail_h / total_hours, 6),
        }

    #波动衰减 & Damage per collection
    objects_out: dict[str, Any] = {}

    # 1) Paper (direct air T/RH; omit hygric tau per S2.2)
    objects_out["paper"] = {
        "chemical": _agg_chem([s.rh_percent for s in segs], ACTIVATION_ENERGY_PAPER_J_MOL),
        "biological": _agg_bio([s.rh_percent for s in segs]),
    }

    # 2) Hygroscopic wooden objects
    for cat, mode in (
        ("panel_painting", "gradient"),
        ("wooden_sculpture", "gradient"),
        ("wooden_furniture", "acclimatized"),
    ):
        surfs = [r.surface for r in obj_resps[cat]]
        bulks = [r.bulk for r in obj_resps[cat]]
        surf_fluc = summarize_fluctuations(segs, surfs)
        bulk_fluc = surf_fluc if cat == "wooden_furniture" else summarize_fluctuations(segs, bulks)

        def _ratios(obj_f: dict[str, Any]) -> dict[str, Any]:
            air_sw = air_fluc["swing_24h_p95"]
            air_90 = air_fluc["span_p95_p05"]
            air_sd = air_fluc["std"]
            r_out: dict[str, Any] = {
                "swing_24h_p95_ratio": round(obj_f["swing_24h_p95"] / air_sw, 4) if air_sw > 0 else 0.0,
                "span_p95_p05_ratio": round(obj_f["span_p95_p05"] / air_90, 4) if air_90 > 0 else 0.0,
                "std_ratio": round(obj_f["std"] / air_sd, 4) if air_sd > 0 else 0.0,
            }
            if air_fluc["hp30_p93_p07"] and obj_f["hp30_p93_p07"] is not None and air_fluc["hp30_p93_p07"] > 0:
                r_out["hp30_p93_p07_ratio"] = round(obj_f["hp30_p93_p07"] / air_fluc["hp30_p93_p07"], 4)
            else:
                r_out["hp30_p93_p07_ratio"] = None
            return r_out

        proof_env = estimate_proofed_envelope(
            rh_all,
            rh_surface_history=np.concatenate(surfs),
            rh_bulk_history=np.concatenate(bulks),
        )
        objects_out[cat] = {
            "surface_fluctuation": surf_fluc,
            "bulk_fluctuation": bulk_fluc,
            "surface_attenuation_ratio": _ratios(surf_fluc),
            "bulk_attenuation_ratio": _ratios(bulk_fluc),
            "chemical": _agg_chem(surfs, ACTIVATION_ENERGY_VARNISH_J_MOL),
            "biological": _agg_bio(surfs),
            "mechanical": _agg_mech(obj_resps[cat], mode),
            "mechanical_init_segment_mean": _agg_mech(obj_resps_mean[cat], mode),
            "proofed_envelope": {
                "rh_min": round(proof_env.rh_min, 3),
                "rh_max": round(proof_env.rh_max, 3),
                "proofed_strain_ratio": round(proof_env.strain_max / WOOD_YIELD_STRAIN_DEFAULT, 5),
            },
        }

    # 3) Bronze (direct air RH corrosion exceedance)
    bronze_metrics: dict[str, Any] = {}
    for preset_key, crh in METAL_CRH_PRESETS.items():
        hrs = 0.0
        rhh = 0.0
        for seg in segs:
            mres = metal_corrosion_risk(seg.rh_percent, rh_crit=crh, dt_hours=seg.dt_hours)
            hrs += float(mres.exceedance_hours_exact)
            rhh += float(mres.exceedance_rh_hours)
        bronze_metrics[preset_key] = {
            "rh_crit": crh,
            "exceedance_hours": round(hrs, 4),
            "exceedance_fraction": round(hrs / total_hours, 6),
            "exceedance_rh_hours": round(rhh, 4),
        }
    objects_out["bronze"] = bronze_metrics

    return {
        "dataset_id": trace.dataset_id,
        "trace_id": trace.trace_id,
        "zone_group": trace.zone_group,
        "label": trace.label,
        "dt_hours": trace.dt_hours,
        "n_segments": len(segs),
        "start_utc": datetime.fromtimestamp(segs[0].start_epoch_s, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "end_utc": datetime.fromtimestamp(segs[-1].end_epoch_s, tz=timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "duration_hours": round(total_hours, 2),
        "duration_days": round(total_hours / 24.0, 2),
        "n_raw_samples": trace.n_raw_samples,
        "n_valid_steps": trace.n_valid_steps,
        "n_spikes_replaced": trace.n_spikes_replaced,
        "max_init_offset_rh": round(max_init_offset_rh, 4),
        "source_files": list(trace.source_files),
        "temp_stats": {
            "mean": round(float(np.mean(t_all)), 3),
            "std": round(float(np.std(t_all)), 3),
            "min": round(float(np.min(t_all)), 3),
            "p05": round(float(np.percentile(t_all, 5.0)), 3),
            "p95": round(float(np.percentile(t_all, 95.0)), 3),
            "max": round(float(np.max(t_all)), 3),
        },
        "air_rh_fluctuation": air_fluc,
        "objects": objects_out,
    }


def _load_d1_metadata(d1_dir: Path) -> dict[str, dict[str, str]]:
    meta_path = d1_dir / "14233429" / "MetaData.csv"
    dl_path = d1_dir / "14233429" / "DataLoggers.csv"
    info: dict[str, dict[str, str]] = {}
    if dl_path.exists():
        for line in dl_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()[1:]:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4 and parts[0]:
                info[parts[0]] = {"room": parts[1], "floor": parts[2], "room_no": parts[3]}
    if not info and meta_path.exists():
        pass
    return info


def _read_d1_csv(paths: list[Path]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    eps: list[float] = []
    temps: list[float] = []
    rhs: list[float] = []
    for p in paths:
        with p.open("r", encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                parts = line.split(",")
                if len(parts) < 4:
                    continue
                try:
                    ep = _parse_d1_timestamp(parts[0], parts[1])
                    rh = float(parts[2])
                    tc = float(parts[3])
                except (ValueError, IndexError):
                    continue
                eps.append(ep)
                rhs.append(rh)
                temps.append(tc)
    return (
        np.asarray(eps, dtype=np.float64),
        np.asarray(temps, dtype=np.float64),
        np.asarray(rhs, dtype=np.float64),
    )


def load_d1_traces(d1_dir: Path) -> list[PreparedTrace]:
    """Load D1 Vienna NHM (197 deduplicated loggers; 15-min uniform grid)."""
    logger_meta = _load_d1_metadata(d1_dir)
    by_id: dict[str, list[Path]] = {}
    for p in sorted(d1_dir.rglob("NH*.csv")):
        lid = p.stem
        # Deduplicate NH082 (prefer 14233508 over double-written 14233546) per DATASETS.md
        if lid == "NH082" and "14233546" in p.parts:
            continue
        by_id.setdefault(lid, []).append(p)

    traces: list[PreparedTrace] = []
    for lid in sorted(by_id):
        files = by_id[lid]
        ep, tc, rh = _read_d1_csv(files)
        segs, n_spikes = clean_and_regularize_series(ep, tc, rh, dt_hours=0.25)
        if not segs:
            continue
        meta = logger_meta.get(lid, {})
        floor = meta.get("floor", "unknown")
        room = meta.get("room", lid)
        total_steps = sum(s.temp_c.size for s in segs)
        dur_h = sum(s.temp_c.size * s.dt_hours for s in segs)
        traces.append(
            PreparedTrace(
                dataset_id="D1",
                trace_id=lid,
                zone_group=f"floor_{floor}",
                label=f"{lid} ({room})",
                dt_hours=0.25,
                source_files=tuple(f.relative_to(d1_dir.parent).as_posix() for f in files),
                segments=segs,
                n_raw_samples=int(ep.size),
                n_valid_steps=int(total_steps),
                n_spikes_replaced=n_spikes,
                duration_hours=dur_h,
            )
        )
    return traces


def load_d2_traces(d2_dir: Path) -> list[PreparedTrace]:
    """Load D2 Danish low-energy museum storage buildings (11 climate zones 01-11)."""
    traces: list[PreparedTrace] = []
    for fname, label, zgroup, dt_h in D2_ZONE_FILES:
        fpath = d2_dir / fname
        if not fpath.exists():
            continue
        eps: list[float] = []
        temps: list[float] = []
        rhs: list[float] = []
        with fpath.open("r", encoding="utf-8-sig", errors="replace") as f:
            lines = f.read().splitlines()
        for line in lines[2:]:
            parts = [x.strip() for x in line.split(";")]
            if len(parts) < 3:
                continue
            try:
                ep = _parse_d2_timestamp(parts[0])
                tc = float(parts[1])
                rh = float(parts[2])
            except (ValueError, IndexError):
                continue
            eps.append(ep)
            temps.append(tc)
            rhs.append(rh)
        ep_a = np.asarray(eps, dtype=np.float64)
        tc_a = np.asarray(temps, dtype=np.float64)
        rh_a = np.asarray(rhs, dtype=np.float64)

        # Vejle A switches to 3 h sampling after 2010-10-29; restrict or split cleanly
        if fname.startswith("03_vejle-basic-storage-climate-A"):
            cutoff = datetime(2010, 10, 30, tzinfo=timezone.utc).timestamp()
            main_mask = ep_a < cutoff
            segs_main, sp_main = clean_and_regularize_series(
                ep_a[main_mask], tc_a[main_mask], rh_a[main_mask], dt_hours=dt_h
            )
            segs_ext, sp_ext = clean_and_regularize_series(
                ep_a[~main_mask], tc_a[~main_mask], rh_a[~main_mask], dt_hours=3.0
            )
            segs = segs_main + segs_ext
            n_spikes = sp_main + sp_ext
        else:
            segs, n_spikes = clean_and_regularize_series(ep_a, tc_a, rh_a, dt_hours=dt_h)

        if not segs:
            continue
        total_steps = sum(s.temp_c.size for s in segs)
        dur_h = sum(s.temp_c.size * s.dt_hours for s in segs)
        traces.append(
            PreparedTrace(
                dataset_id="D2",
                trace_id=fname.split("_", 1)[0],
                zone_group=zgroup,
                label=label,
                dt_hours=dt_h,
                source_files=(fpath.relative_to(d2_dir.parent).as_posix(),),
                segments=segs,
                n_raw_samples=int(ep_a.size),
                n_valid_steps=int(total_steps),
                n_spikes_replaced=n_spikes,
                duration_hours=dur_h,
            )
        )
    return traces


def _parse_xlsx_sheet_rows(zf: zipfile.ZipFile, ss: list[str], sheet_xml: str) -> list[dict[str, str]]:
    root = ET.fromstring(zf.read(sheet_xml))
    rows: list[dict[str, str]] = []
    for row in root.iter():
        if not (row.tag.endswith("}row") or row.tag == "row"):
            continue
        rv: dict[str, str] = {}
        for cell in row:
            ref = cell.attrib.get("r", "")
            m = re.match(r"([A-Z]+)", ref)
            col = m.group(1) if m else ""
            tp = cell.attrib.get("t", "")
            vel = next((ch for ch in cell if ch.tag.endswith("}v") or ch.tag == "v"), None)
            val = vel.text if vel is not None and vel.text is not None else ""
            if tp == "s" and val != "":
                val = ss[int(val)]
            rv[col] = val
        rows.append(rv)
    return rows


def load_d3_traces(d3_dir: Path) -> list[PreparedTrace]:
    """Load D3 Cabildo Salta winter (INVIERNO) & summer (VERANO) short-term campaigns."""
    xlsx = d3_dir / "MedicionesCabildo.xlsx"
    if not xlsx.exists():
        return []

    traces: list[PreparedTrace] = []
    src_rel = xlsx.relative_to(d3_dir.parent).as_posix()
    with zipfile.ZipFile(xlsx) as zf:
        ss = [
            "".join(t.text or "" for t in si.iter() if t.tag.endswith("t"))
            for si in ET.fromstring(zf.read("xl/sharedStrings.xml"))
        ]

        # 1) INVIERNO (sheet1.xml)
        s1_rows = _parse_xlsx_sheet_rows(zf, ss, "xl/worksheets/sheet1.xml")
        row1_names = s1_rows[0]
        row2_ids = s1_rows[1]
        inv_channels: list[tuple[str, str, str, str, str]] = [
            ("exterior", "Exterior_WeatherStation", "C", "D", "exterior"),
            ("S1", f"S1 ({row1_names.get('H', '').strip()})", "H", "I", "room"),
            ("S2", f"S2 ({row1_names.get('J', '').strip()})", "J", "K", "room"),
            ("S3", f"S3 ({row1_names.get('L', '').strip()})", "L", "M", "room"),
            ("S4", f"S4 ({row1_names.get('N', '').strip()})", "N", "O", "room"),
            ("S5", f"S5 ({row1_names.get('P', '').strip()})", "P", "Q", "room"),
            ("S6", f"S6 ({row1_names.get('R', '').strip()})", "R", "S", "room"),
            ("S7", f"S7 ({row1_names.get('T', '').strip()})", "T", "U", "vitrine"),
            ("S8", f"S8 ({row1_names.get('V', '').strip()})", "V", "W", "gallery"),
            ("S9", f"S9 ({row1_names.get('X', '').strip()})", "X", "Y", "room"),
            ("S10", f"S10 ({row1_names.get('Z', '').strip()})", "Z", "AA", "vitrine"),
            ("S11", f"S11 ({row1_names.get('AB', '').strip()})", "AB", "AC", "room"),
            ("S12", f"S12 ({row1_names.get('AD', '').strip()})", "AD", "AE", "room"),
            ("S13", f"S13 ({row1_names.get('AF', '').strip()})", "AF", "AG", "vitrine"),
            ("C2", f"C2 ({row1_names.get('AP', '').strip()})", "AP", "AQ", "vitrine"),
            ("C3", f"C3 ({row1_names.get('AR', '').strip()})", "AR", "AS", "vitrine"),
        ]
        _ = row2_ids  # checked against column map above

        for cid, cname, t_col, r_col, ztype in inv_channels:
            eps, temps, rhs = [], [], []
            for r in s1_rows[3:]:
                t_raw = r.get("A", "")
                if not t_raw:
                    continue
                try:
                    serial = float(t_raw)
                    tc = float(r.get(t_col, ""))
                    rh = float(r.get(r_col, ""))
                except ValueError:
                    continue
                eps.append((EXCEL_EPOCH_UTC + timedelta(days=serial)).timestamp())
                temps.append(tc)
                rhs.append(rh)
            segs, n_spikes = clean_and_regularize_series(
                np.asarray(eps), np.asarray(temps), np.asarray(rhs), dt_hours=0.25
            )
            if segs:
                traces.append(
                    PreparedTrace(
                        dataset_id="D3",
                        trace_id=f"INVIERNO_{cid}",
                        zone_group=f"winter_{ztype}",
                        label=f"Winter {cname}",
                        dt_hours=0.25,
                        source_files=(src_rel,),
                        segments=segs,
                        n_raw_samples=len(eps),
                        n_valid_steps=sum(s.temp_c.size for s in segs),
                        n_spikes_replaced=n_spikes,
                        duration_hours=sum(s.temp_c.size * s.dt_hours for s in segs),
                    )
                )

        # 2) VERANO (sheet2.xml; note rows 4-6 are MIN/MEAN/MAX summary without timestamps)
        s2_rows = _parse_xlsx_sheet_rows(zf, ss, "xl/worksheets/sheet2.xml")
        ver_channels: list[tuple[str, str, str, str, str]] = [
            ("exterior", "Exterior_UNSa", "AE", "AF", "exterior"),
            ("S5", "S5 (PB-Boleteria y Seguridad)", "E", "F", "room"),
            ("S6", "S6 (PB-Periodo Pre Hispanico I)", "G", "H", "room"),
            ("S7", "S7 (PB-Escribania de Guemes)", "I", "J", "room"),
            ("S8", "S8 (PB-Periodo Pre Hispanico II)", "K", "L", "room"),
            ("S9", "S9 (PB-Habitacion textiles)", "M", "N", "room"),
            ("S10", "S10 (PB-Sala Revolucion de Mayo)", "O", "P", "room"),
            ("S12", "S12 (PB-Galeria)", "Q", "R", "gallery"),
            ("S13", "S13 (PB-Sala arquitectura)", "S", "T", "room"),
            ("S16", "S16 (PB-Periodo Pre Hispanico III)", "U", "V", "room"),
            ("S31", "S31 (PB-Oficina Administrativa)", "W", "X", "room"),
            ("S32", "S32(21) (PA-Sala Arte Sacro Chica)", "Y", "Z", "room"),
            ("S11", "S11 (PA-Reserva tecnica)", "AA", "AB", "room"),
        ]
        for cid, cname, t_col, r_col, ztype in ver_channels:
            eps, temps, rhs = [], [], []
            for r in s2_rows[3:]:
                t_raw = r.get("A", "")
                if not t_raw:
                    continue
                try:
                    serial = float(t_raw)
                    tc = float(r.get(t_col, ""))
                    rh = float(r.get(r_col, ""))
                except ValueError:
                    continue
                eps.append((EXCEL_EPOCH_UTC + timedelta(days=serial)).timestamp())
                temps.append(tc)
                rhs.append(rh)
            segs, n_spikes = clean_and_regularize_series(
                np.asarray(eps), np.asarray(temps), np.asarray(rhs), dt_hours=0.25
            )
            if segs:
                traces.append(
                    PreparedTrace(
                        dataset_id="D3",
                        trace_id=f"VERANO_{cid}",
                        zone_group=f"summer_{ztype}",
                        label=f"Summer {cname}",
                        dt_hours=0.25,
                        source_files=(src_rel,),
                        segments=segs,
                        n_raw_samples=len(eps),
                        n_valid_steps=sum(s.temp_c.size for s in segs),
                        n_spikes_replaced=n_spikes,
                        duration_hours=sum(s.temp_c.size * s.dt_hours for s in segs),
                    )
                )
    return traces


def load_d4_traces(d4_dir: Path) -> list[PreparedTrace]:
    """Load D4 Museum_Nov2019 controlled storage ONLY (exclude LSCR_Oct2019)."""
    museum_dir = d4_dir / "Museum_Nov2019"
    if not museum_dir.exists():
        return []
    # Enforce whitelist from D4 manifest & DATASETS.md (never touch LSCR_Oct2019/)
    allowed_txt = sorted(
        fspec.rel_path.split("/", 1)[1]
        for fspec in D4_SPEC.files
        if fspec.rel_path.startswith("Museum_Nov2019/") and fspec.rel_path.endswith(".txt")
    )
    traces: list[PreparedTrace] = []
    for fname in allowed_txt:
        fpath = museum_dir / fname
        if not fpath.exists():
            continue
        eps, rhs, temps = [], [], []
        for line in fpath.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            parts = line.strip().split(",")
            if len(parts) < 3:
                continue
            try:
                ep = float(parts[0]) / 1000.0
                rh = float(parts[1])
                tc = float(parts[2])
            except ValueError:
                continue
            eps.append(ep)
            rhs.append(rh)
            temps.append(tc)
        segs, n_spikes = clean_and_regularize_series(
            np.asarray(eps), np.asarray(temps), np.asarray(rhs), dt_hours=0.25
        )
        if not segs:
            continue
        sid = fpath.stem
        zgroup = "continuous_storage_sensor" if sid in D4_CONTINUOUS_SENSORS else "intermittent_storage_sensor"
        traces.append(
            PreparedTrace(
                dataset_id="D4",
                trace_id=sid,
                zone_group=zgroup,
                label=f"DeLaSalle {sid} ({'continuous' if sid in D4_CONTINUOUS_SENSORS else 'dropouts'})",
                dt_hours=0.25,
                source_files=(fpath.relative_to(d4_dir.parent).as_posix(),),
                segments=segs,
                n_raw_samples=len(eps),
                n_valid_steps=sum(s.temp_c.size for s in segs),
                n_spikes_replaced=n_spikes,
                duration_hours=sum(s.temp_c.size * s.dt_hours for s in segs),
            )
        )
    return traces


def _aggregate_group(traces: list[dict[str, Any]], group_name: str) -> dict[str, Any]:
    """Compute cross-sensor median / min / max summary for a dataset or sub-group."""
    if not traces:
        return {"group": group_name, "n_traces": 0}

    def _stats(vals: list[float]) -> dict[str, float]:
        arr = np.asarray(vals, dtype=np.float64)
        return {
            "median": round(float(np.median(arr)), 4),
            "min": round(float(np.min(arr)), 4),
            "max": round(float(np.max(arr)), 4),
        }

    out: dict[str, Any] = {
        "group": group_name,
        "n_traces": len(traces),
        "total_duration_hours": round(sum(t["duration_hours"] for t in traces), 2),
        "total_spikes_replaced": sum(t["n_spikes_replaced"] for t in traces),
        "air_rh": {
            "mean": _stats([t["air_rh_fluctuation"]["mean"] for t in traces]),
            "min": _stats([t["air_rh_fluctuation"]["min"] for t in traces]),
            "max": _stats([t["air_rh_fluctuation"]["max"] for t in traces]),
            "span_p95_p05": _stats([t["air_rh_fluctuation"]["span_p95_p05"] for t in traces]),
            "swing_24h_p95": _stats([t["air_rh_fluctuation"]["swing_24h_p95"] for t in traces]),
        },
        "paper": {
            "lm_equivalent": _stats([t["objects"]["paper"]["chemical"]["lm_equivalent"] for t in traces]),
            "germination_index_per_year": _stats(
                [t["objects"]["paper"]["biological"]["germination_index_per_year"] for t in traces]
            ),
        },
        "bronze": {
            "frac_gt_42rh": _stats([t["objects"]["bronze"]["bronze_chloride"]["exceedance_fraction"] for t in traces]),
            "frac_gt_65rh": _stats([t["objects"]["bronze"]["clean_metal"]["exceedance_fraction"] for t in traces]),
        },
    }
    for cat in ("wooden_sculpture", "panel_painting", "wooden_furniture"):
        out[cat] = {
            "surf_swing_24h_p95_ratio": _stats(
                [t["objects"][cat]["surface_attenuation_ratio"]["swing_24h_p95_ratio"] for t in traces]
            ),
            "bulk_swing_24h_p95_ratio": _stats(
                [t["objects"][cat]["bulk_attenuation_ratio"]["swing_24h_p95_ratio"] for t in traces]
            ),
            "surf_span_p95_p05_ratio": _stats(
                [t["objects"][cat]["surface_attenuation_ratio"]["span_p95_p05_ratio"] for t in traces]
            ),
            "bulk_span_p95_p05_ratio": _stats(
                [t["objects"][cat]["bulk_attenuation_ratio"]["span_p95_p05_ratio"] for t in traces]
            ),
            "bulk_std_ratio": _stats(
                [t["objects"][cat]["bulk_attenuation_ratio"]["std_ratio"] for t in traces]
            ),
            "lm_equivalent": _stats([t["objects"][cat]["chemical"]["lm_equivalent"] for t in traces]),
            "germination_index_per_year": _stats(
                [t["objects"][cat]["biological"]["germination_index_per_year"] for t in traces]
            ),
            "exact_max_strain_ratio": _stats(
                [t["objects"][cat]["mechanical"]["exact_max_strain_ratio"] for t in traces]
            ),
            "exact_max_strain_ratio_init_mean": _stats(
                [t["objects"][cat]["mechanical_init_segment_mean"]["exact_max_strain_ratio"] for t in traces]
            ),
            "yield_exceedance_fraction": _stats(
                [t["objects"][cat]["mechanical"]["yield_exceedance_fraction"] for t in traces]
            ),
            "yield_exceedance_fraction_init_mean": _stats(
                [t["objects"][cat]["mechanical_init_segment_mean"]["yield_exceedance_fraction"] for t in traces]
            ),
        }
    return out


def render_attenuation_svg(groups: list[dict[str, Any]], out_path: Path) -> None:
    """Render clean SVG comparing 24h P95 & P95-P05 RH fluctuation amplitude Air vs Objects."""
    width, height = 1040, 460
    left_x0, left_w = 240, 340
    right_x0, right_w = 640, 340
    y0, row_h = 85, 52

    series_defs = [
        ("Air RH", lambda g: g["air_rh"]["swing_24h_p95"]["median"], lambda g: g["air_rh"]["span_p95_p05"]["median"], "#475569"),
        ("Sculpture surf (3.3h)", lambda g: g["wooden_sculpture"]["surf_swing_24h_p95_ratio"]["median"] * g["air_rh"]["swing_24h_p95"]["median"], lambda g: g["wooden_sculpture"]["surf_span_p95_p05_ratio"]["median"] * g["air_rh"]["span_p95_p05"]["median"], "#2563eb"),
        ("Panel surf (34.4h)", lambda g: g["panel_painting"]["surf_swing_24h_p95_ratio"]["median"] * g["air_rh"]["swing_24h_p95"]["median"], lambda g: g["panel_painting"]["surf_span_p95_p05_ratio"]["median"] * g["air_rh"]["span_p95_p05"]["median"], "#0d9488"),
        ("Panel bulk (208h)", lambda g: g["panel_painting"]["bulk_swing_24h_p95_ratio"]["median"] * g["air_rh"]["swing_24h_p95"]["median"], lambda g: g["panel_painting"]["bulk_span_p95_p05_ratio"]["median"] * g["air_rh"]["span_p95_p05"]["median"], "#d97706"),
        ("Furniture (320h)", lambda g: g["wooden_furniture"]["surf_swing_24h_p95_ratio"]["median"] * g["air_rh"]["swing_24h_p95"]["median"], lambda g: g["wooden_furniture"]["surf_span_p95_p05_ratio"]["median"] * g["air_rh"]["span_p95_p05"]["median"], "#7c3aed"),
    ]
    max_sw = max(10.0, max(g["air_rh"]["swing_24h_p95"]["median"] for g in groups) * 1.15)
    max_sp = max(20.0, max(g["air_rh"]["span_p95_p05"]["median"] for g in groups) * 1.15)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="520" y="28" text-anchor="middle" font-family="Arial,sans-serif" font-size="16" font-weight="bold" fill="#0f172a">Hygroscopic Buffering of Real Museum RH Fluctuations (D1-D4)</text>',
        f'<text x="{left_x0 + left_w / 2:.1f}" y="54" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" font-weight="bold" fill="#334155">Short-Term 24h P95 Swing (%RH)</text>',
        f'<text x="{right_x0 + right_w / 2:.1f}" y="54" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" font-weight="bold" fill="#334155">Overall P95-P05 Span (%RH)</text>',
    ]
    lx = 230
    for name, _, _, col in series_defs:
        lines.append(f'<rect x="{lx}" y="62" width="12" height="10" fill="{col}" rx="2"/>')
        lines.append(f'<text x="{lx + 16}" y="71" font-family="Arial,sans-serif" font-size="10" fill="#1e293b">{name}</text>')
        lx += 145

    bar_h = 7
    for gi, g in enumerate(groups):
        yc = y0 + gi * row_h
        lines.append(
            f'<text x="{left_x0 - 12}" y="{yc + 22}" text-anchor="end" font-family="Arial,sans-serif" font-size="11" fill="#0f172a">{xml_escape(str(g["group"]))}</text>'
        )
        lines.append(f'<line x1="{left_x0}" y1="{yc}" x2="{left_x0}" y2="{yc + 40}" stroke="#cbd5e1" stroke-width="1"/>')
        lines.append(f'<line x1="{right_x0}" y1="{yc}" x2="{right_x0}" y2="{yc + 40}" stroke="#cbd5e1" stroke-width="1"/>')
        for si, (_, fn_sw, fn_sp, col) in enumerate(series_defs):
            by = yc + 2 + si * (bar_h + 1)
            val_sw = fn_sw(g)
            val_sp = fn_sp(g)
            w_l = max(1.0, (val_sw / max_sw) * left_w)
            lines.append(f'<rect x="{left_x0}" y="{by}" width="{w_l:.1f}" height="{bar_h}" fill="{col}"/>')
            w_r = max(1.0, (val_sp / max_sp) * right_w)
            lines.append(f'<rect x="{right_x0}" y="{by}" width="{w_r:.1f}" height="{bar_h}" fill="{col}"/>')
    base_y = y0 + len(groups) * row_h + 8
    for frac in (0.0, 0.5, 1.0):
        tx_l = left_x0 + frac * left_w
        lines.append(f'<text x="{tx_l:.1f}" y="{base_y + 12}" text-anchor="middle" font-family="Arial,sans-serif" font-size="10" fill="#475569">{max_sw * frac:.0f}%</text>')
        tx_r = right_x0 + frac * right_w
        lines.append(f'<text x="{tx_r:.1f}" y="{base_y + 12}" text-anchor="middle" font-family="Arial,sans-serif" font-size="10" fill="#475569">{max_sp * frac:.0f}%</text>')
    lines.append("</svg>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def render_damage_svg(groups: list[dict[str, Any]], out_path: Path) -> None:
    """Render SVG comparing conservation metrics across datasets/groups."""
    width, height = 1040, 420
    max_lm = max(4.0, max(g["paper"]["lm_equivalent"]["median"] for g in groups) * 1.1)
    max_sr = max(1.5, max(g["panel_painting"]["exact_max_strain_ratio"]["median"] for g in groups) * 1.15)
    max_sc = max(1.5, max(g["wooden_sculpture"]["exact_max_strain_ratio"]["median"] for g in groups) * 1.15)
    cols = [
        ("Paper LM_eq (ref=1.0)", lambda g: g["paper"]["lm_equivalent"]["median"], max_lm, "#16a34a", 1.0),
        ("Panel Max Strain Ratio", lambda g: g["panel_painting"]["exact_max_strain_ratio"]["median"], max_sr, "#dc2626", 1.0),
        ("Sculpture Max Strain Ratio", lambda g: g["wooden_sculpture"]["exact_max_strain_ratio"]["median"], max_sc, "#ea580c", 1.0),
        ("Bronze >42%RH frac", lambda g: g["bronze"]["frac_gt_42rh"]["median"], 1.0, "#0284c7", None),
    ]
    col_x = [245, 445, 645, 845]
    col_w = 135
    y0, row_h = 85, 48
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="520" y="28" text-anchor="middle" font-family="Arial,sans-serif" font-size="16" font-weight="bold" fill="#0f172a">Conservation Risk Profiles Across Real Museum Datasets D1-D4 (Group Medians)</text>',
    ]
    for ci, (cname, _, _, _, _) in enumerate(cols):
        lines.append(
            f'<text x="{col_x[ci] + col_w / 2:.1f}" y="60" text-anchor="middle" font-family="Arial,sans-serif" font-size="11" font-weight="bold" fill="#334155">{xml_escape(cname)}</text>'
        )
    for gi, g in enumerate(groups):
        yc = y0 + gi * row_h
        lines.append(
            f'<text x="235" y="{yc + 22}" text-anchor="end" font-family="Arial,sans-serif" font-size="11" fill="#0f172a">{xml_escape(str(g["group"]))}</text>'
        )
        for ci, (_, fn, cmax, col, _) in enumerate(cols):
            val = float(fn(g))
            w = max(2.0, min(1.0, val / cmax) * col_w)
            lines.append(f'<rect x="{col_x[ci]}" y="{yc + 8}" width="{w:.1f}" height="18" fill="{col}" rx="2"/>')
            lines.append(
                f'<text x="{col_x[ci] + w + 4:.1f}" y="{yc + 21}" font-family="Arial,sans-serif" font-size="10" fill="#1e293b">{val:.2f}</text>'
            )
    for ci, (_, _, cmax, _, ref_v) in enumerate(cols):
        if ref_v is not None and ref_v <= cmax:
            rx = col_x[ci] + (ref_v / cmax) * col_w
            lines.append(
                f'<line x1="{rx:.1f}" y1="{y0 - 6}" x2="{rx:.1f}" y2="{y0 + len(groups) * row_h}" stroke="#0f172a" stroke-dasharray="3,3" stroke-width="1"/>'
            )
    lines.append("</svg>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate S2.2/S2.3 damage risks on D1-D4 real museum traces.")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "raw", help="Path to data/raw")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "results_summary" / "S2.4", help="Output summary dir")
    args = parser.parse_args(argv)

    data_dir: Path = args.data_dir
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    all_traces: list[PreparedTrace] = []
    all_traces.extend(load_d1_traces(data_dir / "D1"))
    all_traces.extend(load_d2_traces(data_dir / "D2"))
    all_traces.extend(load_d3_traces(data_dir / "D3"))
    all_traces.extend(load_d4_traces(data_dir / "D4"))

    if not all_traces:
        raise FileNotFoundError(f"No usable D1-D4 data traces found under {data_dir}")

    evaluated = [evaluate_prepared_trace(t) for t in all_traces]

    by_ds: dict[str, list[dict[str, Any]]] = {}
    for item in evaluated:
        by_ds.setdefault(item["dataset_id"], []).append(item)

    # Sub-group breakdowns for scientific interpretation & comparison with original papers
    d1_traces = by_ds.get("D1", [])
    d1_exhib = [t for t in d1_traces if t["zone_group"] != "floor_K"]
    d1_cellar = [t for t in d1_traces if t["zone_group"] == "floor_K"]

    d2_traces = by_ds.get("D2", [])
    d2_basic = [t for t in d2_traces if t["zone_group"] == "basic_storage"]
    d2_dry = [t for t in d2_traces if t["zone_group"] == "dry_storage"]

    d3_traces = by_ds.get("D3", [])
    d3_ext = [t for t in d3_traces if t["zone_group"].endswith("_exterior") or t["zone_group"].endswith("_gallery")]
    d3_rooms = [t for t in d3_traces if t["zone_group"].endswith("_room")]
    d3_vitrines = [t for t in d3_traces if t["zone_group"].endswith("_vitrine")]

    d4_traces = by_ds.get("D4", [])
    d4_cont = [t for t in d4_traces if t["zone_group"] == "continuous_storage_sensor"]

    summary_groups = [
        _aggregate_group(d1_traces, "D1 Vienna NHM (All 197 loggers)"),
        _aggregate_group(d2_basic, "D2 Danish Basic Storage (8 zones)"),
        _aggregate_group(d2_dry, "D2 Danish Dry Storage (3 zones)"),
        _aggregate_group(d3_rooms, f"D3 Salta Cabildo Rooms ({len(d3_rooms)} traces)"),
        _aggregate_group(d3_vitrines, "D3 Salta Cabildo Vitrines (5 winter)"),
        _aggregate_group(d4_cont, "D4 Medellin Storage (9 cont. sensors)"),
    ]
    chart_groups = [g for g in summary_groups if g.get("n_traces", 0) > 0]
    if d3_ext:
        chart_groups.insert(3, _aggregate_group(d3_ext, "D3 Salta Exterior & Gallery"))

    render_attenuation_svg(chart_groups, out_dir / "rh_fluctuation_attenuation.svg")
    render_damage_svg([g for g in summary_groups if g.get("n_traces", 0) > 0], out_dir / "damage_risk_summary.svg")

    payload = {
        "metadata": {
            "task_id": "S2.4",
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "git_commit": _git_head_sha(),
            "git_dirty": _git_is_dirty(),
            "config_file": "configs/objects.yaml",
            "config_sha256": _sha256_file(DEFAULT_OBJECTS_CONFIG),
            "random_seed": None,
            "datasets_included": ["D1", "D2", "D3", "D4/Museum_Nov2019"],
            "datasets_excluded": {
                "D4/LSCR_Oct2019": "Uncontrolled robotics laboratory per DATASETS.md",
                "D5": "Unknown/missing research redistribution license (usable=False)",
            },
            "source_trace_count": len(evaluated),
        },
        "group_summaries": summary_groups
        + [
            g
            for g in (
                _aggregate_group(d1_exhib, "D1 Upper/Ground Floors (ex-K)"),
                _aggregate_group(d1_cellar, "D1 Basement/Depot Floor (K)"),
                _aggregate_group(d3_ext, "D3 Salta Exterior & Semi-open Gallery"),
                _aggregate_group(d4_traces, "D4 Medellin All 12 Storage Sensors"),
            )
            if g.get("n_traces", 0) > 0
        ],
        "traces": evaluated,
    }

    json_path = out_dir / "real_traces_summary.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {json_path} ({len(evaluated)} traces) and 2 SVGs in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
