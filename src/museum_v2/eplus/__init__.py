"""EnergyPlus Layer B museum model builder and headless runner (Task S1.2)."""

from .build_model import (
    CONTROLLED_ZONES,
    DEFAULT_BASE_EPJSON,
    build_museum_epjson,
    compute_humidity_capacity_multipliers,
)
from .runner import (
    EnergyPlusResult,
    find_energyplus_binary,
    parse_eplus_err,
    run_energyplus_simulation,
)

__all__ = [
    "CONTROLLED_ZONES",
    "DEFAULT_BASE_EPJSON",
    "EnergyPlusResult",
    "build_museum_epjson",
    "compute_humidity_capacity_multipliers",
    "find_energyplus_binary",
    "parse_eplus_err",
    "run_energyplus_simulation",
]
