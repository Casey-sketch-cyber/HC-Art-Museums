"""Generate a per-zone-thermostat variant of Sinergym's 5-zone building.

The stock ``5ZoneAutoDXVAV.epJSON`` drives all five zones from a single shared
heating/cooling schedule pair (``Htg-SetP-Sch`` / ``Clg-SetP-Sch``), so the RL
agent can only move every zone together. That single-thermostat constraint is
what makes the museum conservation envelopes near-infeasible in the original
Sinergym validation.

This script rewrites the model so each zone owns an independent dual-setpoint
thermostat backed by its own pair of schedules, exposing 10 actuatable
schedules (5 heating + 5 cooling). The result lets the controller differentiate
setpoints per zone, mirroring the five-zone mock simulator.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path

import sinergym  # noqa: F401

PKG = Path(sinergym.__file__).resolve().parent
BASE = PKG / "data" / "buildings" / "5ZoneAutoDXVAV.epJSON"
OUT = Path(__file__).resolve().parent / "assets" / "5ZoneAutoDXVAV_multizone.epJSON"

ZONES = ["SPACE1-1", "SPACE2-1", "SPACE3-1", "SPACE4-1", "SPACE5-1"]


def build() -> Path:
    b = json.loads(BASE.read_text())

    htg_base = b["Schedule:Compact"]["Htg-SetP-Sch"]
    clg_base = b["Schedule:Compact"]["Clg-SetP-Sch"]

    for i, zone in enumerate(ZONES, start=1):
        htg_name = f"Htg-SetP-Sch-{i}"
        clg_name = f"Clg-SetP-Sch-{i}"
        dual_name = f"DualSetPoint-{i}"

        # Independent per-zone schedule copies.
        b["Schedule:Compact"][htg_name] = copy.deepcopy(htg_base)
        b["Schedule:Compact"][clg_name] = copy.deepcopy(clg_base)

        # Independent per-zone dual-setpoint thermostat.
        b.setdefault("ThermostatSetpoint:DualSetpoint", {})[dual_name] = {
            "heating_setpoint_temperature_schedule_name": htg_name,
            "cooling_setpoint_temperature_schedule_name": clg_name,
        }

        # Point this zone's controller at its own dual setpoint (control type
        # schedule resolves to 4 = DualSetpoint during the run period).
        ctrl = b["ZoneControl:Thermostat"][f"{zone} Control"]
        ctrl["control_3_name"] = dual_name

    # Remove the now-unused shared dual setpoint to avoid a dangling reference.
    b.get("ThermostatSetpoint:DualSetpoint", {}).pop("DualSetPoint", None)

    _add_humidification(b)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(b, indent=1))
    return OUT


def _add_humidification(b: dict) -> None:
    """Add a central steam humidifier so the supply air can hold the RH band.

    The stock 5-zone DX/VAV system has no active humidification, so indoor RH
    sits far below the ASHRAE Class A1 band in winter. We insert a
    Humidifier:Steam:Electric on the main supply branch (between the heating
    coil and the supply fan), drive it from a single-zone minimum-humidity
    setpoint manager tied to a humidistat, and expose the humidistat's RH
    setpoint schedule (HUMIDIFY-SETP-SCH) so the controller can actuate it.
    """
    HEAT_OUT = "Main Heating Coil 1 Outlet Node"
    HUM_OUT = "Humidifier Outlet Node"
    CTRL_ZONE_NODE = "SPACE5-1 Node"

    # 1. Steam humidifier between the heating coil and the supply fan.
    b.setdefault("Humidifier:Steam:Electric", {})["Main Humidifier"] = {
        "availability_schedule_name": "Humidifier Avail Sched",
        "rated_capacity": "Autosize",
        "rated_power": "Autosize",
        "air_inlet_node_name": HEAT_OUT,
        "air_outlet_node_name": HUM_OUT,
    }

    # 2. Reroute the supply fan inlet to the humidifier outlet.
    fan = b["Fan:VariableVolume"]["Supply Fan 1"]
    assert fan["air_inlet_node_name"] == HEAT_OUT, fan["air_inlet_node_name"]
    fan["air_inlet_node_name"] = HUM_OUT

    # 3. Insert the humidifier into the supply branch and rewire the fan's
    #    branch-component inlet so the node chain stays continuous:
    #    heating coil -> humidifier(HEAT_OUT->HUM_OUT) -> fan(HUM_OUT->outlet).
    br = b["Branch"]["VAV Sys 1 Main Branch"]["components"]
    for idx, c in enumerate(br):
        if c["component_name"] == "Supply Fan 1":
            c["component_inlet_node_name"] = HUM_OUT
            br.insert(idx, {
                "component_object_type": "Humidifier:Steam:Electric",
                "component_name": "Main Humidifier",
                "component_inlet_node_name": HEAT_OUT,
                "component_outlet_node_name": HUM_OUT,
            })
            break

    # 4. Schedules: humidifier availability (always on) + actuatable RH setpoint.
    b["Schedule:Compact"]["Humidifier Avail Sched"] = {
        "schedule_type_limits_name": "On/Off",
        "data": [{"field": "Through: 12/31"}, {"field": "For: AllDays"},
                 {"field": "Until: 24:00"}, {"field": 1}],
    }
    b["Schedule:Compact"]["HUMIDIFY-SETP-SCH"] = {
        "schedule_type_limits_name": "Any Number",
        "data": [{"field": "Through: 12/31"}, {"field": "For: AllDays"},
                 {"field": "Until: 24:00"}, {"field": 50.0}],   # %RH default
    }

    # 5. Humidistat on the control zone + minimum-humidity setpoint manager.
    b.setdefault("ZoneControl:Humidistat", {})["SPACE5-1 Humidistat"] = {
        "zone_name": "SPACE5-1",
        "humidifying_relative_humidity_setpoint_schedule_name": "HUMIDIFY-SETP-SCH",
    }
    b.setdefault("SetpointManager:SingleZone:Humidity:Minimum", {})[
        "Humidifier Setpoint Manager"] = {
        "control_zone_air_node_name": CTRL_ZONE_NODE,
        "setpoint_node_or_nodelist_name": HUM_OUT,
    }


def actuators() -> dict:
    """Per-zone thermostat actuators in EplusEnv tuple format.

    EplusEnv (when constructed directly) expects actuators as
    ``{custom_name: (component_type, control_type, actuator_unique_name)}`` and
    calls ``get_actuator_handle(state, component_type, control_type, name)``.
    We use EnergyPlus's ``Zone Temperature Control`` actuator, which overrides
    each zone's heating/cooling setpoint directly. Order is htg_i, clg_i for
    i = 1..5, matching the 10-D action vector.
    """
    act = {}
    for z in ZONES:
        act[f"{z.lower()}_heating"] = (
            "Zone Temperature Control", "Heating Setpoint", z)
        act[f"{z.lower()}_cooling"] = (
            "Zone Temperature Control", "Cooling Setpoint", z)
    return act


if __name__ == "__main__":
    p = build()
    b = json.loads(p.read_text())
    n_sched = sum(1 for k in b["Schedule:Compact"] if "SetP-Sch-" in k)
    n_dual = len(b.get("ThermostatSetpoint:DualSetpoint", {}))
    print(f"wrote {p}")
    print(f"  per-zone schedules: {n_sched} (expect 10)")
    print(f"  dual setpoints: {n_dual} (expect 5)")
    for z in ZONES:
        print(f"  {z} Control.control_3 ="
              f" {b['ZoneControl:Thermostat'][z + ' Control']['control_3_name']}")
