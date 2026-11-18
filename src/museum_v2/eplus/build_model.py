"""Build 5-zone IdealLoads museum epJSON models (Layer B) from Sinergym's geometry.

Generates EnergyPlus 23.2 ``epJSON`` models for ``historic``, ``retrofitted``,
and ``modern`` building tiers directly parameterized by ``configs/building_<tier>.yaml``:
  * Preserves exact 5-zone floorplan, partitions, windows, and passive return plenum
    from ``src/museum/assets/5ZoneAutoDXVAV_multizone.epJSON``.
  * Replaces central AirLoopHVAC VAV + central steam humidifier with independent per-zone
    ``ZoneHVAC:IdealLoadsAirSystem``, dual-setpoint thermostat, and dual-limit
    ``ZoneControl:Humidistat`` (separate humidifying & dehumidifying RH setpoints).
  * Applies per-zone ``ZoneCapacitanceMultiplier:ResearchSpecial`` moisture capacity
    multipliers ``1 + M_buffer / M_air`` synchronized with Task S1.1b NORDTEST MBV
    calibration, plus symmetric ``ZoneMixing`` doorway air exchange.
  * Replaces office schedules with museum opening schedules (Tue-Sun 09:00-17:00,
    Monday closed) and occupancy-coupled outdoor air ventilation.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from ..rom import MuseumROMConfig, load_building_tier

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BASE_EPJSON = REPO_ROOT / "src" / "museum" / "assets" / "5ZoneAutoDXVAV_multizone.epJSON"

CONTROLLED_ZONES: tuple[str, ...] = (
    "SPACE1-1",
    "SPACE2-1",
    "SPACE3-1",
    "SPACE4-1",
    "SPACE5-1",
)

# Standard ISO 6946 opaque film resistances used to size construction layers [m2*K/W]
R_FILM_EXT = 0.17  # R_si (0.13) + R_se (0.04)
R_FILM_INT = 0.26  # 2 * R_si (0.13)

# Objects belonging solely to the legacy central VAV AirLoopHVAC system
_LEGACY_HVAC_KEYS = (
    "AirLoopHVAC",
    "AirLoopHVAC:ControllerList",
    "AirLoopHVAC:OutdoorAirSystem",
    "AirLoopHVAC:OutdoorAirSystem:EquipmentList",
    "AirLoopHVAC:ReturnPath",
    "AirLoopHVAC:ReturnPlenum",
    "AirLoopHVAC:SupplyPath",
    "AirLoopHVAC:ZoneSplitter",
    "AirTerminal:SingleDuct:VAV:Reheat",
    "AvailabilityManager:Scheduled",
    "AvailabilityManagerAssignmentList",
    "Branch",
    "BranchList",
    "Coil:Cooling:DX:TwoSpeed",
    "Coil:Heating:Electric",
    "CoilSystem:Cooling:DX",
    "Controller:OutdoorAir",
    "Curve:Biquadratic",
    "Curve:Cubic",
    "Curve:Quadratic",
    "Fan:VariableVolume",
    "Humidifier:Steam:Electric",
    "NodeList",
    "OutdoorAir:Mixer",
    "OutdoorAir:Node",
    "OutdoorAir:NodeList",
    "SetpointManager:MixedAir",
    "SetpointManager:SingleZone:Humidity:Minimum",
    "SetpointManager:Warmest",
    "Sizing:System",
    "ThermostatSetpoint:SingleCooling",
    "ThermostatSetpoint:SingleHeating",
    "ZoneHVAC:AirDistributionUnit",
)


def compute_humidity_capacity_multipliers(config: MuseumROMConfig) -> dict[str, float]:
    """Compute per-zone EnergyPlus ``humidity_capacity_multiplier`` matched to S1.1b ``M_buffer``.

    In the A-layer ROM, zone moisture capacitance sums zone air dry mass ``M_a = rho * V``
    and calibrated interior material buffer ``M_b``. Setting EnergyPlus
    ``ZoneCapacitanceMultiplier:ResearchSpecial.humidity_capacity_multiplier = 1 + M_b / M_a``
    aligns the B-layer room moisture capacitance to the identical NORDTEST MBV budget.
    """
    rho = config.constants.rho_air_kg_m3
    return {
        z.name: round(1.0 + z.m_buffer_kg / (rho * z.volume_m3), 4)
        for z in config.zones
    }


def _const_compact_schedule(value: float, limits_name: str = "Any Number") -> dict[str, Any]:
    return {
        "schedule_type_limits_name": limits_name,
        "data": [
            {"field": "Through: 12/31"},
            {"field": "For: AllDays"},
            {"field": "Until: 24:00"},
            {"field": float(value)},
        ],
    }


def _configure_museum_schedules(ep: dict[str, Any]) -> None:
    """Install museum operating schedules (Tue-Sun 09:00-17:00 open, Mon closed)."""
    scheds = ep.setdefault("Schedule:Compact", {})
    limits = ep.setdefault("ScheduleTypeLimits", {})
    limits.setdefault(
        "Humidity",
        {"lower_limit_value": 0.0, "upper_limit_value": 100.0, "numeric_type": "Continuous"},
    )

    scheds["AlwaysOn"] = _const_compact_schedule(1.0, "On/Off")
    scheds["Zone Control Type Sched"] = _const_compact_schedule(4.0, "Control Type")
    scheds["INFIL-SCH"] = _const_compact_schedule(1.0, "Fraction")
    scheds["Min OARequirements Sched"] = _const_compact_schedule(1.0, "Fraction")

    # Visitor schedule: Closed Mondays (0.05 staff only), open Tue-Sun 09:00-17:00
    scheds["OCCUPY-1"] = {
        "schedule_type_limits_name": "Fraction",
        "data": [
            {"field": "Through: 12/31"},
            {"field": "For: Monday"},
            {"field": "Until: 09:00"},
            {"field": 0.0},
            {"field": "Until: 17:00"},
            {"field": 0.05},
            {"field": "Until: 24:00"},
            {"field": 0.0},
            {"field": "For: AllOtherDays"},
            {"field": "Until: 09:00"},
            {"field": 0.0},
            {"field": "Until: 11:00"},
            {"field": 0.65},
            {"field": "Until: 14:00"},
            {"field": 0.90},
            {"field": "Until: 16:00"},
            {"field": 0.85},
            {"field": "Until: 17:00"},
            {"field": 0.50},
            {"field": "Until: 24:00"},
            {"field": 0.0},
        ],
    }

    # Gallery exhibition lighting: low security baseline off-hours, exhibition lighting Tue-Sun 08:30-17:30
    scheds["LIGHTS-1"] = {
        "schedule_type_limits_name": "Fraction",
        "data": [
            {"field": "Through: 12/31"},
            {"field": "For: Monday"},
            {"field": "Until: 08:30"},
            {"field": 0.05},
            {"field": "Until: 17:30"},
            {"field": 0.25},
            {"field": "Until: 24:00"},
            {"field": 0.05},
            {"field": "For: AllOtherDays"},
            {"field": "Until: 08:30"},
            {"field": 0.05},
            {"field": "Until: 17:30"},
            {"field": 0.80},
            {"field": "Until: 24:00"},
            {"field": 0.05},
        ],
    }

    # Equipment (environmental sensors, AV displays, security)
    scheds["EQUIP-1"] = {
        "schedule_type_limits_name": "Fraction",
        "data": [
            {"field": "Through: 12/31"},
            {"field": "For: Monday"},
            {"field": "Until: 08:30"},
            {"field": 0.15},
            {"field": "Until: 17:30"},
            {"field": 0.35},
            {"field": "Until: 24:00"},
            {"field": 0.15},
            {"field": "For: AllOtherDays"},
            {"field": "Until: 08:30"},
            {"field": 0.15},
            {"field": "Until: 17:30"},
            {"field": 0.70},
            {"field": "Until: 24:00"},
            {"field": 0.15},
        ],
    }


def _configure_envelope_and_infiltration(ep: dict[str, Any], config: MuseumROMConfig) -> None:
    """Apply tier U-values, glazing SHGC, partition U, and constant design ACH infiltration."""
    env = config.envelope
    mats = ep.setdefault("Material", {})
    nomass = ep.setdefault("Material:NoMass", {})
    constructions = ep.setdefault("Construction", {})

    # 1. Exterior Walls (WALL-1)
    if config.tier == "modern":
        # Preserve original lightweight framed WALL-1 (U_with_film = 0.3815 W/(m2*K))
        pass
    elif config.tier == "retrofitted":
        # 240 mm brick masonry + mineral interior retrofit insulation yielding target U_wall
        mats["MASONRY-BRICK-240"] = {
            "roughness": "MediumRough",
            "thickness": 0.24,
            "conductivity": 0.72,
            "density": 1800.0,
            "specific_heat": 840.0,
        }
        r_insul = max(0.02, 1.0 / env.u_wall_w_m2_k - R_FILM_EXT - 0.24 / 0.72 - 0.0127 / 0.16)
        nomass["INSUL-WALL-RETRO"] = {
            "roughness": "MediumSmooth",
            "thermal_resistance": round(r_insul, 4),
            "thermal_absorptance": 0.9,
            "solar_absorptance": 0.7,
            "visible_absorptance": 0.7,
        }
        constructions["WALL-1"] = {
            "outside_layer": "MASONRY-BRICK-240",
            "layer_2": "INSUL-WALL-RETRO",
            "layer_3": "GP01",
        }
    elif config.tier == "historic":
        # Uninsulated heavyweight solid stone/brick wall sized to exact target U_wall
        r_wall_mat = max(0.05, 1.0 / env.u_wall_w_m2_k - R_FILM_EXT)
        thickness = 0.40
        mats["MASONRY-HIST-400"] = {
            "roughness": "Rough",
            "thickness": thickness,
            "conductivity": round(thickness / r_wall_mat, 4),
            "density": 1950.0,
            "specific_heat": 880.0,
        }
        constructions["WALL-1"] = {"outside_layer": "MASONRY-HIST-400"}

    # 2. Exterior Roof (ROOF-1)
    if config.tier == "modern":
        pass
    elif config.tier == "retrofitted":
        mats["CONC-SLAB-100"] = {
            "roughness": "MediumRough",
            "thickness": 0.10,
            "conductivity": 1.31,
            "density": 2240.0,
            "specific_heat": 840.0,
        }
        r_roof_insul = max(0.02, 1.0 / env.u_roof_w_m2_k - R_FILM_EXT - 0.10 / 1.31 - 0.0191 / 0.115)
        nomass["INSUL-ROOF-RETRO"] = {
            "roughness": "Rough",
            "thermal_resistance": round(r_roof_insul, 4),
            "thermal_absorptance": 0.9,
            "solar_absorptance": 0.7,
            "visible_absorptance": 0.7,
        }
        constructions["ROOF-1"] = {
            "outside_layer": "INSUL-ROOF-RETRO",
            "layer_2": "CONC-SLAB-100",
            "layer_3": "WD01",
        }
    elif config.tier == "historic":
        r_roof_mat = max(0.05, 1.0 / env.u_roof_w_m2_k - R_FILM_EXT)
        mats["TIMBER-ROOF-HIST"] = {
            "roughness": "Rough",
            "thickness": 0.12,
            "conductivity": round(0.12 / r_roof_mat, 4),
            "density": 650.0,
            "specific_heat": 1350.0,
        }
        constructions["ROOF-1"] = {"outside_layer": "TIMBER-ROOF-HIST"}

    # 3. Interior partitions (INT-WALL-1)
    if config.tier != "modern":
        r_part = max(0.05, 1.0 / env.u_interzone_wall_w_m2_k - R_FILM_INT)
        mats["PART-MASONRY"] = {
            "roughness": "MediumSmooth",
            "thickness": 0.16,
            "conductivity": round(0.16 / r_part, 4),
            "density": 1600.0,
            "specific_heat": 840.0,
        }
        constructions["INT-WALL-1"] = {"outside_layer": "PART-MASONRY"}

    # 4. Windows and Glass Doors via SimpleGlazingSystem (matches YAML U_window & SHGC cleanly)
    simple_glz = ep.setdefault("WindowMaterial:SimpleGlazingSystem", {})
    glz_name = f"MUSEUM-GLZ-{config.tier.upper()}"
    simple_glz[glz_name] = {
        "u_factor": float(env.u_window_w_m2_k),
        "solar_heat_gain_coefficient": float(env.window_shgc),
        "visible_transmittance": 0.65,
    }
    constructions["MUSEUM-WIN"] = {"outside_layer": glz_name}
    for fen in ep.get("FenestrationSurface:Detailed", {}).values():
        fen["construction_name"] = "MUSEUM-WIN"

    # 5. Infiltration (year-round constant ACH matched to config.envelope.infiltration_ach_design)
    infil_dict = ep.setdefault("ZoneInfiltration:DesignFlowRate", {})
    for z in config.zones:
        key = f"{z.name} Infil 1"
        infil_dict[key] = {
            "zone_or_zonelist_or_space_or_spacelist_name": z.name,
            "schedule_name": "INFIL-SCH",
            "design_flow_rate_calculation_method": "AirChanges/Hour",
            "air_changes_per_hour": float(env.infiltration_ach_design),
            "constant_term_coefficient": 1.0,
            "temperature_term_coefficient": 0.0,
            "velocity_term_coefficient": 0.0,
            "velocity_squared_term_coefficient": 0.0,
        }


def _configure_per_zone_idealloads(
    ep: dict[str, Any],
    config: MuseumROMConfig,
    zone_setpoints: dict[str, tuple[float, float, float, float]],
) -> None:
    """Replace central VAV AirLoop with independent per-zone IdealLoads, Thermostat & Humidistat."""
    for legacy_key in _LEGACY_HVAC_KEYS:
        ep.pop(legacy_key, None)

    scheds = ep.setdefault("Schedule:Compact", {})
    # Remove stale centralized setpoint schedules before creating per-zone ones
    for obsolete in ("Htg-SetP-Sch", "Clg-SetP-Sch", "HUMIDIFY-SETP-SCH", "Humidifier Avail Sched"):
        scheds.pop(obsolete, None)

    dual_sp = ep["ThermostatSetpoint:DualSetpoint"] = {}
    thermostats = ep["ZoneControl:Thermostat"] = {}
    humidistats = ep["ZoneControl:Humidistat"] = {}
    ideal_loads = ep["ZoneHVAC:IdealLoadsAirSystem"] = {}
    eq_lists = ep["ZoneHVAC:EquipmentList"] = {}
    eq_conns = ep["ZoneHVAC:EquipmentConnections"] = {}
    nodelists = ep["NodeList"] = {}
    oa_nodes: list[dict[str, str]] = []
    cap_mult = ep["ZoneCapacitanceMultiplier:ResearchSpecial"] = {}
    zone_mixing = ep["ZoneMixing"] = {}

    # Occupancy-coupled fresh air requirements on DesignSpecification:OutdoorAir
    dsoa = ep.setdefault("DesignSpecification:OutdoorAir", {})
    dsoa.pop("ZoneMinOARequirements", None)
    for z in config.zones:
        dsoa[f"SZ DSOA {z.name}"] = {
            "outdoor_air_method": "Sum",
            "outdoor_air_flow_per_person": 0.00472,        # ~4.72 L/(s*person) = 17 m3/(h*person)
            "outdoor_air_flow_per_zone_floor_area": 0.0003, # Low background envelope purge (~0.3 L/(s*m2))
            "outdoor_air_flow_per_zone": 0.0,
            "outdoor_air_schedule_name": "AlwaysOn",
        }

    hum_mults = compute_humidity_capacity_multipliers(config)

    for idx, z in enumerate(config.zones, start=1):
        t_h, t_c, rh_h, rh_d = zone_setpoints[z.name]
        if t_h > t_c:
            raise ValueError(f"{z.name}: heating setpoint {t_h} > cooling setpoint {t_c}")
        if rh_h > rh_d:
            raise ValueError(f"{z.name}: humidify setpoint {rh_h} > dehumidify setpoint {rh_d}")

        htg_sch = f"Htg-SetP-Sch-{idx}"
        clg_sch = f"Clg-SetP-Sch-{idx}"
        hum_sch = f"Hum-SetP-Sch-{idx}"
        dehum_sch = f"Dehum-SetP-Sch-{idx}"

        scheds[htg_sch] = _const_compact_schedule(t_h, "Temperature")
        scheds[clg_sch] = _const_compact_schedule(t_c, "Temperature")
        scheds[hum_sch] = _const_compact_schedule(rh_h, "Humidity")
        scheds[dehum_sch] = _const_compact_schedule(rh_d, "Humidity")

        dual_name = f"DualSetPoint-{idx}"
        dual_sp[dual_name] = {
            "heating_setpoint_temperature_schedule_name": htg_sch,
            "cooling_setpoint_temperature_schedule_name": clg_sch,
        }

        thermostats[f"{z.name} Control"] = {
            "zone_or_zonelist_name": z.name,
            "control_type_schedule_name": "Zone Control Type Sched",
            "control_1_object_type": "ThermostatSetpoint:DualSetpoint",
            "control_1_name": dual_name,
        }

        humidistats[f"{z.name} Humidistat"] = {
            "zone_name": z.name,
            "humidifying_relative_humidity_setpoint_schedule_name": hum_sch,
            "dehumidifying_relative_humidity_setpoint_schedule_name": dehum_sch,
        }

        inlet_node = f"{z.name} Ideal Loads Supply Air Node"
        exhaust_node = f"{z.name} Ideal Loads Exhaust Air Node"
        oa_node = f"{z.name} Ideal Loads OA Node"
        oa_nodes.append({"node_or_nodelist_name": oa_node})
        inlet_list = f"{z.name} In Nodes"
        nodelists[inlet_list] = {"nodes": [{"node_name": inlet_node}]}

        sys_name = f"{z.name} Ideal Loads"
        ideal_loads[sys_name] = {
            "availability_schedule_name": "AlwaysOn",
            "zone_supply_air_node_name": inlet_node,
            "zone_exhaust_air_node_name": exhaust_node,
            "outdoor_air_inlet_node_name": oa_node,
            "maximum_heating_supply_air_temperature": 50.0,
            "minimum_cooling_supply_air_temperature": 13.0,
            "maximum_heating_supply_air_humidity_ratio": 0.025,
            "minimum_cooling_supply_air_humidity_ratio": 0.002,
            "heating_limit": "NoLimit",
            "cooling_limit": "NoLimit",
            "dehumidification_control_type": "Humidistat",
            "humidification_control_type": "Humidistat",
            "design_specification_outdoor_air_object_name": f"SZ DSOA {z.name}",
            "demand_controlled_ventilation_type": "OccupancySchedule",
            "outdoor_air_economizer_type": "NoEconomizer",
            "heat_recovery_type": "None",
        }

        eq_list_name = f"{z.name} Eq"
        eq_lists[eq_list_name] = {
            "load_distribution_scheme": "SequentialLoad",
            "equipment": [
                {
                    "zone_equipment_object_type": "ZoneHVAC:IdealLoadsAirSystem",
                    "zone_equipment_name": sys_name,
                    "zone_equipment_cooling_sequence": 1,
                    "zone_equipment_heating_or_no_load_sequence": 1,
                }
            ],
        }

        eq_conns[f"ZoneHVAC:EquipmentConnections {idx}"] = {
            "zone_name": z.name,
            "zone_conditioning_equipment_list_name": eq_list_name,
            "zone_air_inlet_node_or_nodelist_name": inlet_list,
            "zone_air_exhaust_node_or_nodelist_name": exhaust_node,
            "zone_air_node_name": f"{z.name} Node",
            "zone_return_air_node_or_nodelist_name": f"{z.name} Out Node",
        }

        cap_mult[f"{z.name} Moisture Buffer Multiplier"] = {
            "zone_or_zonelist_name": z.name,
            "temperature_capacity_multiplier": 1.0,
            "humidity_capacity_multiplier": hum_mults[z.name],
            "carbon_dioxide_capacity_multiplier": 1.0,
            "generic_contaminant_capacity_multiplier": 1.0,
        }

    ep["OutdoorAir:NodeList"] = {"OutdoorAir:NodeList 1": {"nodes": oa_nodes}}

    # Symmetric inter-zone doorway air mixing matching ROM m_inter
    vols = {z.name: z.volume_m3 for z in config.zones}
    ach_inter = config.envelope.interzone_air_exchange_ach
    for p_idx, part in enumerate(config.interzone_partitions, start=1):
        flow_m3_s = min(vols[part.zone_a], vols[part.zone_b]) * (ach_inter / 3600.0)
        if flow_m3_s <= 0.0:
            continue
        zone_mixing[f"Mix_{p_idx}_AB"] = {
            "zone_or_space_name": part.zone_a,
            "schedule_name": "AlwaysOn",
            "design_flow_rate_calculation_method": "Flow/Zone",
            "design_flow_rate": round(flow_m3_s, 6),
            "source_zone_or_space_name": part.zone_b,
            "delta_temperature": 0.0,
        }
        zone_mixing[f"Mix_{p_idx}_BA"] = {
            "zone_or_space_name": part.zone_b,
            "schedule_name": "AlwaysOn",
            "design_flow_rate_calculation_method": "Flow/Zone",
            "design_flow_rate": round(flow_m3_s, 6),
            "source_zone_or_space_name": part.zone_a,
            "delta_temperature": 0.0,
        }

    # Update People outdoor-air link? Sizing:Zone keeps DSOA object names cleanly
    for sz in ep.get("Sizing:Zone", {}).values():
        zname = sz.get("zone_or_zonelist_name", "")
        if zname in zone_setpoints:
            sz["design_specification_outdoor_air_object_name"] = f"SZ DSOA {zname}"
            sz["zone_load_sizing_method"] = "Sensible And Latent Load"


def _configure_outputs(ep: dict[str, Any]) -> None:
    """Request hourly outdoor, zone state, IdealLoads sensible/latent/total energy, and infiltration."""
    ep["Version"] = {"Version 1": {"version_identifier": "23.2"}}
    ep["SimulationControl"] = {
        "SimulationControl 1": {
            "do_zone_sizing_calculation": "No",
            "do_system_sizing_calculation": "No",
            "do_plant_sizing_calculation": "No",
            "run_simulation_for_sizing_periods": "No",
            "run_simulation_for_weather_file_run_periods": "Yes",
        }
    }

    vars_req = [
        ("Environment", "Site Outdoor Air Drybulb Temperature"),
        ("Environment", "Site Outdoor Air Relative Humidity"),
        ("*", "Zone Air Temperature"),
        ("*", "Zone Air Relative Humidity"),
        ("*", "Zone Air Humidity Ratio"),
        ("*", "Zone Ideal Loads Supply Air Sensible Heating Energy"),
        ("*", "Zone Ideal Loads Supply Air Sensible Cooling Energy"),
        ("*", "Zone Ideal Loads Supply Air Latent Heating Energy"),
        ("*", "Zone Ideal Loads Supply Air Latent Cooling Energy"),
        ("*", "Zone Ideal Loads Supply Air Total Heating Energy"),
        ("*", "Zone Ideal Loads Supply Air Total Cooling Energy"),
        ("*", "Zone Ideal Loads Outdoor Air Mass Flow Rate"),
        ("*", "Zone Infiltration Mass Flow Rate"),
    ]
    out_vars: dict[str, Any] = {}
    for idx, (key_value, var_name) in enumerate(vars_req, start=1):
        out_vars[f"Output:Variable {idx}"] = {
            "key_value": key_value,
            "variable_name": var_name,
            "reporting_frequency": "Hourly",
        }
    ep["Output:Variable"] = out_vars
    ep["Output:VariableDictionary"] = {"Output:VariableDictionary 1": {"key_field": "IDF"}}
    ep["OutputControl:Table:Style"] = {"OutputControl:Table:Style 1": {"column_separator": "HTML"}}


def build_museum_epjson(
    tier: str = "modern",
    *,
    t_heat_sp_c: float = 21.0,
    t_cool_sp_c: float = 21.0,
    rh_hum_sp_percent: float = 50.0,
    rh_dehum_sp_percent: float = 50.0,
    zone_setpoints: dict[str, tuple[float, float, float, float]] | None = None,
    base_epjson_path: str | Path | None = None,
    output_path: str | Path | None = None,
    timestep_per_hour: int = 4,
) -> dict[str, Any]:
    """Build an EnergyPlus 23.2 museum epJSON dictionary for the specified building tier.

    Parameters
    ----------
    tier:
        One of ``"historic"``, ``"retrofitted"``, or ``"modern"``.
    t_heat_sp_c, t_cool_sp_c, rh_hum_sp_percent, rh_dehum_sp_percent:
        Default uniform dual setpoints applied to all 5 controlled zones unless
        overridden by ``zone_setpoints``.
    zone_setpoints:
        Optional mapping ``zone_name -> (t_heat, t_cool, rh_hum, rh_dehum)``.
    """
    config = load_building_tier(tier)
    src_path = Path(base_epjson_path) if base_epjson_path is not None else DEFAULT_BASE_EPJSON
    ep = copy.deepcopy(json.loads(src_path.read_text(encoding="utf-8")))

    sp_map: dict[str, tuple[float, float, float, float]] = {
        z.name: (t_heat_sp_c, t_cool_sp_c, rh_hum_sp_percent, rh_dehum_sp_percent)
        for z in config.zones
    }
    if zone_setpoints is not None:
        for zname, vals in zone_setpoints.items():
            if zname not in sp_map:
                raise KeyError(f"Unknown zone '{zname}' in zone_setpoints.")
            sp_map[zname] = tuple(float(v) for v in vals)  # type: ignore[assignment]

    ep["Timestep"] = {"Timestep 1": {"number_of_timesteps_per_hour": int(timestep_per_hour)}}
    _configure_museum_schedules(ep)
    _configure_envelope_and_infiltration(ep, config)
    _configure_per_zone_idealloads(ep, config, sp_map)
    _configure_outputs(ep)

    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(ep, indent=2), encoding="utf-8")

    return ep
