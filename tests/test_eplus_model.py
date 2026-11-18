"""Unit and live simulation tests for EnergyPlus Layer B museum models (Task S1.2)."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.museum_v2.eplus import (
    CONTROLLED_ZONES,
    build_museum_epjson,
    compute_humidity_capacity_multipliers,
    find_energyplus_binary,
    run_energyplus_simulation,
)
from src.museum_v2.rom import load_building_tier

DEFAULT_EPW = (
    REPO_ROOT
    / "Eplus-env-museum-mz-res1"
    / "Eplus-env-sub_run1"
    / "USA_NY_New.York-J.F.Kennedy.Intl.AP.744860_TMY3.epw"
)


def _eplus_ready() -> bool:
    if not DEFAULT_EPW.is_file():
        return False
    try:
        find_energyplus_binary()
        return True
    except FileNotFoundError:
        return False


def test_build_museum_epjson_schema_and_s11b_moisture_multipliers():
    """Generated epJSON has 5 independent IdealLoads, Humidistats, ZoneMixing, and S1.1b MBV multipliers."""
    for tier in ("modern", "retrofitted", "historic"):
        cfg = load_building_tier(tier)
        expected_mults = compute_humidity_capacity_multipliers(cfg)
        ep = build_museum_epjson(
            tier=tier,
            t_heat_sp_c=20.0,
            t_cool_sp_c=23.0,
            rh_hum_sp_percent=42.0,
            rh_dehum_sp_percent=58.0,
        )

        # Central VAV AirLoop components must be completely removed
        assert "AirLoopHVAC" not in ep
        assert "Humidifier:Steam:Electric" not in ep
        assert "AirTerminal:SingleDuct:VAV:Reheat" not in ep

        assert len(ep["ZoneHVAC:IdealLoadsAirSystem"]) == 5
        assert len(ep["ZoneControl:Thermostat"]) == 5
        assert len(ep["ZoneControl:Humidistat"]) == 5
        assert len(ep["ZoneCapacitanceMultiplier:ResearchSpecial"]) == 5
        assert len(ep["ZoneMixing"]) == 16  # 8 bidirectional partition doorway pairs

        for z in CONTROLLED_ZONES:
            sys_obj = ep["ZoneHVAC:IdealLoadsAirSystem"][f"{z} Ideal Loads"]
            assert sys_obj["humidification_control_type"] == "Humidistat"
            assert sys_obj["dehumidification_control_type"] == "Humidistat"
            assert sys_obj["demand_controlled_ventilation_type"] == "OccupancySchedule"

            hum_obj = ep["ZoneControl:Humidistat"][f"{z} Humidistat"]
            assert "humidifying_relative_humidity_setpoint_schedule_name" in hum_obj
            assert "dehumidifying_relative_humidity_setpoint_schedule_name" in hum_obj

            mult_obj = ep["ZoneCapacitanceMultiplier:ResearchSpecial"][f"{z} Moisture Buffer Multiplier"]
            assert mult_obj["humidity_capacity_multiplier"] == expected_mults[z]
            assert mult_obj["humidity_capacity_multiplier"] > 4.0

        assert ep["Schedule:Compact"]["INFIL-SCH"]["data"][-1] == {"field": 1.0}
        assert ep["ZoneInfiltration:DesignFlowRate"]["SPACE1-1 Infil 1"]["air_changes_per_hour"] == pytest.approx(
            cfg.envelope.infiltration_ach_design
        )


def test_per_zone_independent_setpoints_in_epjson():
    """zone_setpoints assigns distinct dual temperature and humidity schedules per zone."""
    custom = {
        "SPACE1-1": (19.0, 24.0, 38.0, 62.0),
        "SPACE5-1": (21.0, 21.5, 48.0, 52.0),
    }
    ep = build_museum_epjson(tier="modern", zone_setpoints=custom)
    assert ep["Schedule:Compact"]["Htg-SetP-Sch-1"]["data"][-1] == {"field": 19.0}
    assert ep["Schedule:Compact"]["Clg-SetP-Sch-1"]["data"][-1] == {"field": 24.0}
    assert ep["Schedule:Compact"]["Hum-SetP-Sch-1"]["data"][-1] == {"field": 38.0}
    assert ep["Schedule:Compact"]["Dehum-SetP-Sch-1"]["data"][-1] == {"field": 62.0}
    assert ep["Schedule:Compact"]["Htg-SetP-Sch-5"]["data"][-1] == {"field": 21.0}
    assert ep["Schedule:Compact"]["Dehum-SetP-Sch-5"]["data"][-1] == {"field": 52.0}


@pytest.mark.skipif(not _eplus_ready(), reason="EnergyPlus 23.2 binary or EPW file not present")
def test_energyplus_live_f0_and_per_zone_differentiation():
    """Live EnergyPlus 23.2 simulation: F0 holds >=95% hours within 21+-1 C / 50+-5 %RH and zones decouple."""
    # 1. Full-year F0 check on modern tier
    ep_f0 = build_museum_epjson(tier="modern", t_heat_sp_c=21.0, t_cool_sp_c=21.0, rh_hum_sp_percent=50.0, rh_dehum_sp_percent=50.0)
    res_f0 = run_energyplus_simulation(ep_f0, DEFAULT_EPW, tier="modern")
    assert res_f0.n_hours == 8760
    assert not res_f0.severe_errors
    for j in range(5):
        assert np.mean(np.abs(res_f0.t_air_c[:, j] - 21.0) <= 1.0) >= 0.95
        assert np.mean(np.abs(res_f0.rh_air_percent[:, j] - 50.0) <= 5.0) >= 0.95
    assert np.sum(res_f0.e_sens_heat_kwh) > 1000.0
    assert np.sum(res_f0.e_sens_cool_kwh) > 1000.0
    assert np.sum(res_f0.e_hum_kwh) > 1000.0
    assert np.sum(res_f0.e_dehum_kwh) > 1000.0

    # 2. Verify zones can independently enforce distinct T & RH bands
    ep_diff = build_museum_epjson(
        tier="modern",
        zone_setpoints={
            "SPACE1-1": (18.0, 25.0, 35.0, 65.0),
            "SPACE2-1": (21.5, 22.0, 48.0, 52.0),
            "SPACE3-1": (18.0, 25.0, 35.0, 65.0),
            "SPACE4-1": (18.0, 25.0, 35.0, 65.0),
            "SPACE5-1": (21.5, 22.0, 48.0, 52.0),
        },
    )
    res_diff = run_energyplus_simulation(ep_diff, DEFAULT_EPW, tier="modern")
    assert not res_diff.severe_errors
    # SPACE2-1 tightly controlled near 21.5-22 C & 48-52% RH while SPACE1-1 floats wider across year
    assert np.std(res_diff.rh_air_percent[:, 0]) > 1.5 * np.std(res_diff.rh_air_percent[:, 1])
    assert np.std(res_diff.t_air_c[:, 0]) > 1.5 * np.std(res_diff.t_air_c[:, 1])
