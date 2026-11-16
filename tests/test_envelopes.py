"""锁住 S0.2 的包络数字，防止以后把二手转述改成没有出处的常数。"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "envelopes.yaml"
STANDARDS = ROOT / "docs" / "STANDARDS.md"


def load():
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def test_ashrae_numbers_match_cci_tables():
    data = load()
    assert data["provenance"]["ashrae_access"] == "secondhand"
    aa = data["envelopes"]["ASHRAE_AA"]
    a1 = data["envelopes"]["ASHRAE_A1"]
    a2 = data["envelopes"]["ASHRAE_A2"]
    b = data["envelopes"]["ASHRAE_B"]

    assert aa["temperature"]["seasonal_increase_C"] == 5
    assert aa["temperature"]["seasonal_decrease_C"] == 5
    assert aa["temperature"]["short_term_plus_minus_C"] == 2
    assert aa["temperature"]["outer_min_C"] == 10
    assert aa["temperature"]["outer_max_C"] == 25
    assert aa["relative_humidity"]["seasonal_increase_percent"] == 0
    assert aa["relative_humidity"]["short_term_plus_minus_percent"] == 5
    assert (aa["relative_humidity"]["outer_min_percent"], aa["relative_humidity"]["outer_max_percent"]) == (35, 65)

    assert a1["temperature"]["seasonal_decrease_C"] == 10
    assert a1["relative_humidity"]["seasonal_increase_percent"] == 10
    assert a1["relative_humidity"]["short_term_plus_minus_percent"] == 5

    assert a2["relative_humidity"]["seasonal_increase_percent"] == 0
    assert a2["relative_humidity"]["short_term_plus_minus_percent"] == 10

    assert b["temperature"]["seasonal_increase_C"] == 10
    assert b["temperature"]["seasonal_decrease_C"] == 20
    assert b["temperature"]["seasonal_decrease_is_upper_bound"] is True
    assert b["temperature"]["outer_min_C"] is None
    assert b["temperature"]["outer_max_C"] == 30
    assert b["temperature"]["short_term_plus_minus_C"] == 5
    assert (b["relative_humidity"]["outer_min_percent"], b["relative_humidity"]["outer_max_percent"]) == (30, 70)

    assert data["short_term_means_shorter_than"] == {
        "temperature_days": 7,
        "relative_humidity_days": 30,
    }


def test_bizot_does_not_invent_a_temperature_fluctuation():
    bizot = load()["envelopes"]["Bizot_2023"]
    assert bizot["temperature"]["outer_min_C"] == 16
    assert bizot["temperature"]["outer_max_C"] == 25
    assert bizot["temperature"]["short_term_plus_minus_C"] is None
    assert bizot["temperature"]["seasonal_increase_C"] is None
    rh = bizot["relative_humidity"]
    assert (rh["outer_min_percent"], rh["outer_max_percent"]) == (40, 60)
    assert rh["short_term_plus_minus_percent"] == 10


def test_en15757_is_a_method_not_a_fixed_band():
    spec = load()["EN_15757"]
    assert spec["fixed_numbers"] is False
    assert "30-day" in spec["target_level"]
    assert "7th" in spec["allowable_band"] and "93rd" in spec["allowable_band"]
    text = CONFIG.read_text(encoding="utf-8") + STANDARDS.read_text(encoding="utf-8")
    assert "EN 15757 速率上限" not in text
