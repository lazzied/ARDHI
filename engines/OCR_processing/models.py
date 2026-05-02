from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List

from data_scripts.gaez_scripts.metadata.gaez_metadata_templates import CROP_REGISTRY


@dataclass
class AugmentedLayer:
    layer:    str
    values:   Dict[str, Any]
    smu_id:   int = 0


@dataclass
class AugmentedLayersGroup:
    layers : List[AugmentedLayer]
    
    
class InputLevel(Enum):
    LOW          = "low"
    INTERMEDIATE = "intermediate"
    HIGH         = "high"


class IrrigationType(Enum):
    DRIP      = "drip"
    SPRINKLER = "sprinkler"
    GRAVITY   = "gravity"


class WaterSupply(Enum):
    RAINFED   = "rainfed"
    IRRIGATED = "irrigated"


class WaterSupplyIndex(Enum):
    RAINFED   = "R"
    IRRIGATED = "I"
    
class pH_level(Enum):
    ACIDIC = "acidic"
    BASIC = "basic"

class Texture(Enum):
    FINE= "fine"
    MEDIUM = "medium"
    COARSE= "coarse"
    
@dataclass(frozen=True)
class ScenarioConfig:
    crop_name: str
    input_level: InputLevel
    water_supply: WaterSupply
    irrigation_type: IrrigationType | None = None

@dataclass(frozen=True)
class SiteContext:
    coordinates: tuple[float, float]
    ph_level: pH_level
    texture_class: Texture
    smu_id: int | None = None  # Optional: can be resolved later
    
@dataclass
class CropSuitability:
    crop_name:         str
    potential_yield:   float
    constrained_yield: float
    ratio:             float
    pixel_class:       str
    SI:                float
    SC:                int
    SC_label:          str

INPUT_LEVEL_TO_PYAEZ = {
    InputLevel.LOW:          "L",
    InputLevel.INTERMEDIATE: "I",
    InputLevel.HIGH:         "H",
}


CROPS_RAINFED_SPRINKLER: dict[int, dict] = {
    1:  {"name": "wheat"},
    2:  {"name": "wetland rice"},
    3:  {"name": "dryland rice"},
    4:  {"name": "maize"},
    5:  {"name": "barley"},
    6:  {"name": "sorghum"},
    7:  {"name": "rye"},
    8:  {"name": "pearl millet"},
    9:  {"name": "foxtail millet"},
    10: {"name": "oat"},
    11: {"name": "buckwheat"},
    12: {"name": "white potato"},
    13: {"name": "sweet potato"},
    14: {"name": "cassava"},
    15: {"name": "white yam"},
    16: {"name": "greater yam"},
    17: {"name": "yellow yam"},
    18: {"name": "cocoyam"},
    19: {"name": "sugarcane"},
    20: {"name": "sugar beet"},
    21: {"name": "phaseolus bean"},
    22: {"name": "chickpea"},
    23: {"name": "cowpea"},
    24: {"name": "dry pea"},
    25: {"name": "gram"},
    26: {"name": "pigeonpea"},
    27: {"name": "groundnut"},
    28: {"name": "soybean"},
    29: {"name": "sunflower"},
    30: {"name": "rape"},
    31: {"name": "oil palm"},
    32: {"name": "olive"},
    33: {"name": "cabbage"},
    34: {"name": "carrot"},
    35: {"name": "onion"},
    36: {"name": "tomato"},
    37: {"name": "banana plantain"},
    38: {"name": "citrus"},
    39: {"name": "coconut"},
    40: {"name": "cotton"},
    41: {"name": "flax"},
    42: {"name": "para rubber"},
    43: {"name": "cacao commun"},
    44: {"name": "cacao hybrid"},
    45: {"name": "arabica coffee"},
    46: {"name": "robusta coffee"},
    47: {"name": "tea"},
    48: {"name": "tobacco"},
    49: {"name": "maize silage"},
    50: {"name": "alfalfa"},
    51: {"name": "napier grass"},
    52: {"name": "pasture legume"},
    53: {"name": "grass"},
    54: {"name": "sorghum biomass"},
    55: {"name": "jatropha"},
    56: {"name": "miscanthus"},
    57: {"name": "switchgrass"},
    58: {"name": "reed canary grass"},
}

CROPS_GRAVITY_IRRIGATION: dict[int, dict] = {
    1:  {"name": "wheat"},      2:  {"name": "wetland rice"},
    4:  {"name": "maize"},      5:  {"name": "barley"},
    6:  {"name": "sorghum"},    7:  {"name": "rye"},
    8:  {"name": "pearl millet"}, 9: {"name": "foxtail millet"},
    10: {"name": "oat"},        11: {"name": "buckwheat"},
    12: {"name": "white potato"}, 13: {"name": "sweet potato"},
    19: {"name": "sugarcane"},  20: {"name": "sugar beet"},
    21: {"name": "phaseolus bean"}, 22: {"name": "chickpea"},
    23: {"name": "cowpea"},     24: {"name": "dry pea"},
    25: {"name": "gram"},       26: {"name": "pigeonpea"},
    27: {"name": "groundnut"},  28: {"name": "soybean"},
    29: {"name": "sunflower"},  30: {"name": "rape"},
    32: {"name": "olive"},      33: {"name": "cabbage"},
    34: {"name": "carrot"},     35: {"name": "onion"},
    36: {"name": "tomato"},     37: {"name": "banana plantain"},
    38: {"name": "citrus"},     39: {"name": "coconut"},
    40: {"name": "cotton"},     41: {"name": "flax"},
    43: {"name": "cacao commun"}, 44: {"name": "cacao hybrid"},
    45: {"name": "arabica coffee"}, 46: {"name": "robusta coffee"},
    48: {"name": "tobacco"},    49: {"name": "maize silage"},
    50: {"name": "alfalfa"},    51: {"name": "napier grass"},
    52: {"name": "pasture legume"}, 53: {"name": "grass"},
    54: {"name": "sorghum biomass"},
}

CROPS_DRIP_IRRIGATION: dict[int, dict] = {
    21: {"name": "phaseolus bean"}, 31: {"name": "oil palm"},
    32: {"name": "olive"},      33: {"name": "cabbage"},
    34: {"name": "carrot"},     35: {"name": "onion"},
    36: {"name": "tomato"},     37: {"name": "banana plantain"},
    38: {"name": "citrus"},     39: {"name": "coconut"},
    43: {"name": "cacao commun"}, 44: {"name": "cacao hybrid"},
    45: {"name": "arabica coffee"}, 46: {"name": "robusta coffee"},
    47: {"name": "tea"},
}

IRRIGATION_TO_DB_STR = {
    IrrigationType.DRIP:      "irrigated_drip",
    IrrigationType.SPRINKLER: "irrigated_sprinkler",
    IrrigationType.GRAVITY:   "irrigated_gravity",
}

RAINFED_SPRINKLER_CROPS = {v["name"].lower() for v in CROPS_RAINFED_SPRINKLER.values()}
GRAVITY_IRRIGATED_CROPS = {v["name"].lower() for v in CROPS_GRAVITY_IRRIGATION.values()}
DRIP_IRRIGATED_CROPS    = {v["name"].lower() for v in CROPS_DRIP_IRRIGATION.values()}

def get_crop_code(crop_name: str, map_code: str) -> str | None:
    """
    Returns the crop code for a given crop name and map code.
    Checks both the top-level crop and its subtypes.

    Args:
        crop_name: key in CROP_REGISTRY (e.g. "wheat", "barley")
        map_code:  resolution key (e.g. "RES02", "RES05")

    Returns:
        crop code string or None if not found
    """
    entry = CROP_REGISTRY.get(crop_name)
    if not entry:
        return None

    # Check top-level codes first
    code = entry.get("codes", {}).get(map_code)
    if code:
        return code

    # Check subtypes
    for subtype in entry.get("subtypes", {}).values():
        code = subtype.get("codes", {}).get(map_code)
        if code:
            return code

    return None
