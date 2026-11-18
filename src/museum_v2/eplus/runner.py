"""Headless EnergyPlus 23.2 simulation runner and CSV/ERR parser (Task S1.2)."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

import numpy as np

from .build_model import CONTROLLED_ZONES

J_TO_KWH = 1.0 / 3_600_000.0


@dataclass(frozen=True)
class EnergyPlusResult:
    tier: str
    n_hours: int
    zone_names: tuple[str, ...]
    t_out_c: np.ndarray            # (T,)
    rh_out_percent: np.ndarray     # (T,)
    t_air_c: np.ndarray            # (T, 5)
    rh_air_percent: np.ndarray     # (T, 5)
    w_air_kg_kg: np.ndarray        # (T, 5)
    e_sens_heat_kwh: np.ndarray    # (T, 5)
    e_sens_cool_kwh: np.ndarray    # (T, 5)
    e_hum_kwh: np.ndarray          # (T, 5) Latent heating energy [kWh_th]
    e_dehum_kwh: np.ndarray        # (T, 5) Latent cooling energy [kWh_th]
    e_total_heat_kwh: np.ndarray   # (T, 5)
    e_total_cool_kwh: np.ndarray   # (T, 5)
    m_oa_kg_s: np.ndarray          # (T, 5)
    m_infil_kg_s: np.ndarray       # (T, 5)
    warnings: tuple[str, ...]
    severe_errors: tuple[str, ...]


def find_energyplus_binary() -> tuple[Path, Path | None]:
    """Locate EnergyPlus 23.2 binary and optional user-space libgomp directory."""
    candidates: list[Path] = []
    env_ep = os.environ.get("EPLUS_PATH")
    if env_ep:
        candidates.append(Path(env_ep) / "energyplus")
    which_ep = shutil.which("energyplus")
    if which_ep:
        candidates.append(Path(which_ep))
    candidates.extend(
        [
            Path("/usr/local/EnergyPlus-23-2-0/energyplus"),
            Path("/mnt/e/lzt/tools/EnergyPlus-23-2-0/energyplus"),
            Path("/mnt/e/lzt/tools/EnergyPlus-23.2.0-7636e6b3e9-Linux-Ubuntu22.04-x86_64/energyplus"),
        ]
    )
    ep_bin: Path | None = None
    for cand in candidates:
        if cand.is_file():
            ep_bin = cand
            break
    if ep_bin is None:
        raise FileNotFoundError(
            "EnergyPlus 23.2 binary not found. Checked EPLUS_PATH, PATH, "
            "/usr/local/EnergyPlus-23-2-0, and /mnt/e/lzt/tools/EnergyPlus-23-2-0."
        )

    lib_dir_cand = Path("/mnt/e/lzt/tools/libs/usr/lib/x86_64-linux-gnu")
    extra_lib = lib_dir_cand if lib_dir_cand.is_dir() else None
    return ep_bin, extra_lib


def parse_eplus_err(err_path: str | Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Extract Warning and Severe/Fatal lines from EnergyPlus ``eplusout.err``."""
    text = Path(err_path).read_text(encoding="utf-8", errors="replace")
    warnings: list[str] = []
    severe: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("** Warning **"):
            warnings.append(s)
        elif s.startswith("** Severe  **") or s.startswith("**  Fatal  **"):
            severe.append(s)
    return tuple(warnings), tuple(severe)


def _extract_zone_matrix(
    headers: list[str],
    cols: dict[str, np.ndarray],
    zones: tuple[str, ...],
    var_substr: str,
    scale: float = 1.0,
) -> np.ndarray:
    n_rows = len(next(iter(cols.values())))
    out = np.zeros((n_rows, len(zones)), dtype=np.float64)
    target = var_substr.lower()
    for j, zone in enumerate(zones):
        z_low = zone.lower()
        matched_col: str | None = None
        for h in headers:
            h_low = h.lower()
            if f":{target}" in h_low and h_low.startswith(z_low):
                matched_col = h
                break
        if matched_col is None:
            raise KeyError(
                f"Expected EnergyPlus CSV column for zone={zone!r}, var={var_substr!r}. "
                f"Available sample headers: {headers[:15]}"
            )
        out[:, j] = cols[matched_col] * scale
    return out


def parse_eplus_csv(
    csv_path: str | Path,
    *,
    zones: tuple[str, ...] = CONTROLLED_ZONES,
    tier: str = "modern",
    warnings: tuple[str, ...] = (),
    severe_errors: tuple[str, ...] = (),
) -> EnergyPlusResult:
    """Parse hourly ``eplusout.csv`` into dense float64 arrays."""
    with Path(csv_path).open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        headers = [h.strip() for h in next(reader)]
        raw_cols: list[list[float]] = [[] for _ in headers]
        for row in reader:
            if not row or not row[0].strip():
                continue
            raw_cols[0].append(0.0)  # Date/Time placeholder
            for idx in range(1, len(headers)):
                raw_cols[idx].append(float(row[idx]))

    cols = {headers[idx]: np.asarray(raw_cols[idx], dtype=np.float64) for idx in range(1, len(headers))}
    n_hours = len(raw_cols[0])

    def _env_col(var_substr: str) -> np.ndarray:
        target = var_substr.lower()
        for h in headers[1:]:
            if f":{target}" in h.lower():
                return cols[h]
        raise KeyError(f"Missing Environment column matching {var_substr!r}")

    return EnergyPlusResult(
        tier=tier,
        n_hours=n_hours,
        zone_names=zones,
        t_out_c=_env_col("Site Outdoor Air Drybulb Temperature"),
        rh_out_percent=_env_col("Site Outdoor Air Relative Humidity"),
        t_air_c=_extract_zone_matrix(headers, cols, zones, "Zone Air Temperature"),
        rh_air_percent=_extract_zone_matrix(headers, cols, zones, "Zone Air Relative Humidity"),
        w_air_kg_kg=_extract_zone_matrix(headers, cols, zones, "Zone Air Humidity Ratio"),
        e_sens_heat_kwh=_extract_zone_matrix(
            headers, cols, zones, "Zone Ideal Loads Supply Air Sensible Heating Energy", scale=J_TO_KWH
        ),
        e_sens_cool_kwh=_extract_zone_matrix(
            headers, cols, zones, "Zone Ideal Loads Supply Air Sensible Cooling Energy", scale=J_TO_KWH
        ),
        e_hum_kwh=_extract_zone_matrix(
            headers, cols, zones, "Zone Ideal Loads Supply Air Latent Heating Energy", scale=J_TO_KWH
        ),
        e_dehum_kwh=_extract_zone_matrix(
            headers, cols, zones, "Zone Ideal Loads Supply Air Latent Cooling Energy", scale=J_TO_KWH
        ),
        e_total_heat_kwh=_extract_zone_matrix(
            headers, cols, zones, "Zone Ideal Loads Supply Air Total Heating Energy", scale=J_TO_KWH
        ),
        e_total_cool_kwh=_extract_zone_matrix(
            headers, cols, zones, "Zone Ideal Loads Supply Air Total Cooling Energy", scale=J_TO_KWH
        ),
        m_oa_kg_s=_extract_zone_matrix(
            headers, cols, zones, "Zone Ideal Loads Outdoor Air Mass Flow Rate"
        ),
        m_infil_kg_s=_extract_zone_matrix(
            headers, cols, zones, "Zone Infiltration Mass Flow Rate"
        ),
        warnings=warnings,
        severe_errors=severe_errors,
    )


def run_energyplus_simulation(
    epjson_data: dict[str, Any],
    weather_epw_path: str | Path,
    *,
    tier: str = "modern",
    work_dir: str | Path | None = None,
    keep_outputs: bool = False,
) -> EnergyPlusResult:
    """Execute EnergyPlus 23.2 headlessly on ``epjson_data`` + ``weather_epw_path``."""
    ep_bin, extra_lib = find_energyplus_binary()
    epw_path = Path(weather_epw_path).resolve()
    if not epw_path.is_file():
        raise FileNotFoundError(f"Weather EPW file not found: {epw_path}")

    env = dict(os.environ)
    if extra_lib is not None:
        prev_ld = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = f"{extra_lib}:{prev_ld}" if prev_ld else str(extra_lib)

    tmp_ctx: tempfile.TemporaryDirectory[str] | None = None
    if work_dir is None:
        tmp_ctx = tempfile.TemporaryDirectory(prefix="eplus_museum_")
        run_dir = Path(tmp_ctx.name)
    else:
        run_dir = Path(work_dir)
        run_dir.mkdir(parents=True, exist_ok=True)

    try:
        in_epjson = run_dir / "in.epJSON"
        in_epjson.write_text(json.dumps(epjson_data, indent=2), encoding="utf-8")

        cmd = [
            str(ep_bin),
            "--readvars",
            "--weather",
            str(epw_path),
            "--output-directory",
            str(run_dir),
            str(in_epjson),
        ]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
        err_path = run_dir / "eplusout.err"
        warnings, severe = parse_eplus_err(err_path) if err_path.is_file() else ((), ())
        if proc.returncode != 0 or any("Fatal" in s for s in severe):
            raise RuntimeError(
                f"EnergyPlus failed (exit={proc.returncode}). Severe: {severe}; "
                f"stderr tail: {proc.stderr[-600:]}"
            )

        csv_path = run_dir / "eplusout.csv"
        if not csv_path.is_file():
            raise RuntimeError(f"EnergyPlus completed but {csv_path} was not created.")

        return parse_eplus_csv(
            csv_path,
            tier=tier,
            warnings=warnings,
            severe_errors=severe,
        )
    finally:
        if tmp_ctx is not None and not keep_outputs:
            tmp_ctx.cleanup()
