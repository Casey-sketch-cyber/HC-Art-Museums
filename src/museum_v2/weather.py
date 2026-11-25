"""EPW weather parser, epJSON ground schedule loader, and facade solar irradiance model (Task S1.3)."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path

import numpy as np

from .eplus.build_model import DEFAULT_BASE_EPJSON

MONTH_DAYS: tuple[int, ...] = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
_MONTH_FIELD_NAMES: tuple[str, ...] = (
    "january_ground_temperature",
    "february_ground_temperature",
    "march_ground_temperature",
    "april_ground_temperature",
    "may_ground_temperature",
    "june_ground_temperature",
    "july_ground_temperature",
    "august_ground_temperature",
    "september_ground_temperature",
    "october_ground_temperature",
    "november_ground_temperature",
    "december_ground_temperature",
)


@dataclass(frozen=True)
class EPWData:
    """Hourly meteorological arrays and station metadata extracted from a TMY3/TMY EPW file."""

    path: str
    city: str
    latitude_deg: float
    longitude_deg: float
    timezone_hours: float
    elevation_m: float
    t_out_c: np.ndarray            # (T,)
    rh_out_percent: np.ndarray     # (T,)
    pressure_pa: np.ndarray        # (T,)
    ghi_w_m2: np.ndarray           # (T,)
    dni_w_m2: np.ndarray           # (T,)
    dhi_w_m2: np.ndarray           # (T,)

    @property
    def mean_pressure_pa(self) -> float:
        return float(np.mean(self.pressure_pa))

    @property
    def n_hours(self) -> int:
        return int(self.t_out_c.shape[0])


def parse_epw(path: str | Path) -> EPWData:
    """Parse an EnergyPlus ``.epw`` weather file into dense float64 hourly arrays."""
    p = Path(path)
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) < 9:
        raise ValueError(f"EPW file '{p}' has fewer than 9 lines.")
    loc = lines[0].split(",")
    city = loc[1].strip() if len(loc) > 1 else p.stem
    lat = float(loc[6])
    lon = float(loc[7])
    tz = float(loc[8])
    elev = float(loc[9])

    t_out, rh_out, patm, ghi, dni, dhi = [], [], [], [], [], []
    for row in lines[8:]:
        if not row.strip():
            continue
        cols = row.split(",")
        t_out.append(float(cols[6]))
        rh_out.append(float(cols[8]))
        patm.append(float(cols[9]))
        ghi.append(float(cols[13]))
        dni.append(float(cols[14]))
        dhi.append(float(cols[15]))

    return EPWData(
        path=str(p),
        city=city,
        latitude_deg=lat,
        longitude_deg=lon,
        timezone_hours=tz,
        elevation_m=elev,
        t_out_c=np.asarray(t_out, dtype=np.float64),
        rh_out_percent=np.asarray(rh_out, dtype=np.float64),
        pressure_pa=np.asarray(patm, dtype=np.float64),
        ghi_w_m2=np.asarray(ghi, dtype=np.float64),
        dni_w_m2=np.asarray(dni, dtype=np.float64),
        dhi_w_m2=np.asarray(dhi, dtype=np.float64),
    )


def epjson_ground_temperatures_hourly(epjson_path: str | Path | None = None) -> np.ndarray:
    """Expand ``Site:GroundTemperature:BuildingSurface`` monthly temperatures to 8760 hourly values."""
    src = Path(epjson_path) if epjson_path is not None else DEFAULT_BASE_EPJSON
    ep = json.loads(src.read_text(encoding="utf-8"))
    ground_objs = ep.get("Site:GroundTemperature:BuildingSurface", {})
    if not ground_objs:
        return np.full(8760, 20.0, dtype=np.float64)
    first_obj = next(iter(ground_objs.values()))
    hourly: list[float] = []
    for n_days, field in zip(MONTH_DAYS, _MONTH_FIELD_NAMES):
        t_val = float(first_obj[field])
        hourly.extend([t_val] * (n_days * 24))
    return np.asarray(hourly, dtype=np.float64)


def compute_facade_irradiance(
    epw: EPWData,
    *,
    albedo: float = 0.20,
    north_axis_deg: float = 30.0,
    south_overhang_depth_m: float = 1.30,
    south_overhang_gap_m: float = 0.10,
    south_window_height_m: float = 1.20,
) -> np.ndarray:
    """Compute hourly vertical-window irradiance ``(T, 5)`` matching EnergyPlus geometry.

    Follows ``5ZoneAutoDXVAV_multizone.epJSON`` (whose ``Building.north_axis`` rotates
    local +Y clockwise by ``30 deg`` from true North):
      * ``SPACE1-1`` (idx 0, ``FRONT-1``, local South): azimuth ``gamma = 0 + north_axis`` (``+30 deg`` SSW),
        including ``Main South Overhang`` shading (1.3 m depth placed 0.1 m above 1.2 m glazing);
      * ``SPACE2-1`` (idx 1, ``RIGHT-1``, local East): azimuth ``gamma = -90 + north_axis`` (``-60 deg`` ESE);
      * ``SPACE3-1`` (idx 2, ``BACK-1``, local North): azimuth ``gamma = -180 + north_axis`` (``-150 deg`` NNE);
      * ``SPACE4-1`` (idx 3, ``LEFT-1``, local West): azimuth ``gamma = +90 + north_axis`` (``+120 deg`` WNW);
      * ``SPACE5-1`` (idx 4, ``Core_Lobby``): interior unglazed core (0 W/m^2).
    """
    lat_rad = math.radians(epw.latitude_deg)
    lon = epw.longitude_deg
    lsm = epw.timezone_hours * 15.0
    ghi, dni, dhi = epw.ghi_w_m2, epw.dni_w_m2, epw.dhi_w_m2
    n_h = epw.n_hours
    out = np.zeros((n_h, 5), dtype=np.float64)
    # Duffie & Beckman gamma: 0 = South, + = West, - = East
    na = math.radians(north_axis_deg)
    surf_azimuths = (0.0 + na, -math.pi / 2.0 + na, -math.pi + na, math.pi / 2.0 + na)

    for h in range(n_h):
        doy = ((h // 24) % 365) + 1
        hod = (h % 24) + 0.5  # midpoint of hourly interval
        b_rad = 2.0 * math.pi * (doy - 1) / 365.0
        eot_min = 229.18 * (
            0.000075
            + 0.001868 * math.cos(b_rad)
            - 0.032077 * math.sin(b_rad)
            - 0.014615 * math.cos(2.0 * b_rad)
            - 0.04089 * math.sin(2.0 * b_rad)
        )
        solar_time = hod + (4.0 * (lon - lsm) + eot_min) / 60.0
        omega = math.radians(15.0 * (solar_time - 12.0))
        decl = math.radians(23.45 * math.sin(math.radians(360.0 * (284 + doy) / 365.0)))
        cos_zen = math.sin(lat_rad) * math.sin(decl) + math.cos(lat_rad) * math.cos(decl) * math.cos(omega)
        diff_vert = 0.5 * dhi[h] + 0.5 * albedo * ghi[h]

        for j, gamma in enumerate(surf_azimuths):
            if cos_zen > 0.01:
                cos_inc = (
                    math.sin(decl) * (-math.cos(lat_rad) * math.cos(gamma))
                    + math.cos(decl) * math.cos(omega) * (math.sin(lat_rad) * math.cos(gamma))
                    + math.cos(decl) * math.sin(gamma) * math.sin(omega)
                )
                beam = dni[h] * max(0.0, cos_inc)
                if j == 0 and south_overhang_depth_m > 0.0 and cos_inc > 1e-4:
                    # Drop of overhang shadow onto vertical window plane
                    h_drop = south_overhang_depth_m * (cos_zen / cos_inc)
                    shaded = max(0.0, h_drop - south_overhang_gap_m)
                    f_sunlit = max(0.0, min(1.0, (south_window_height_m - shaded) / south_window_height_m))
                    beam *= f_sunlit
            else:
                beam = 0.0
            out[h, j] = max(0.0, beam + diff_vert)
    return out
