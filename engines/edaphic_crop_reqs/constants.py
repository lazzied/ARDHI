
from __future__ import annotations
from typing import Dict


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


# --------------------------------------------------------------------------
# Appendix header -> canonical attribute name.
# The right-hand side MUST be in CANONICAL_ATTRIBUTES.
# Changes vs. the legacy map:
#   CECclay  -> CEC_clay   (canonical rename)
#   CECsoil  -> CEC_soil   (canonical rename)
#   CF       -> GRC        (canonical rename: "gravel / coarse fragments")
#   GSP      -> REMOVED    (not in canonical; Tunisia has no permafrost)
#   SPR, OSD -> added      (present in canonical; produced downstream by
#                           splitting the SPH rating curve on phase-token groups)
# --------------------------------------------------------------------------
ATTRIBUTE_TO_HEADER: Dict[str, list[str]] = {
    "OC":       ["Soil Organic Carbon (SOC % weight)"],
    "pH":       ["Soil Reaction (pHH2O)"],
    "TEB":      ["Total Exchangeable Bases (TEB)"],
    "CEC_clay": ["Cation Exchange Capacity of Clay (CECclay)"],
    "BS":       ["Base Saturation (BS)"],
    "RSD":      ["Rooting / Soil Depth"],
    "EC":       ["Electrical Conductivity (EC)"],
    "GRC":      ["Coarse Fragments (CF)", "Gravel / Coarse Fragments"],
    "ESP":      ["Exchangeable Sodium Percentage (ESP)"],
    "CCB":      ["Calcium Carbonate (CCB)"],
    "GYP":      ["Calcium Sulphate (GYP)"],
    "SPR":      ["Vertic Soil Properties", "Soil Property Rating"],
    "VSP":      ["Vertic Soil Properties"],
    "CEC_soil": ["Cation Exchange Capacity Soil (CECsoil)"],
    "TXT":      ["Soil Texture Classes"],
    "DRG":      ["Drainage Class"],
    "SPH":      ["Soil Phase Rating", "Soil Phase"],
    "OSD":      ["Gelic soil properties"],
}



ATTR_ABBREV_MAP: Dict[str, list[str]] = {
    "SOC":  ["OC"],
    "pH":   ["pH"],
    "TEB":  ["TEB"],
    "CECa": ["CEC_clay"],
    "BS":   ["BS"],
    "RC":   ["RSD"],
    "CF":   ["GRC"],
    "EC":   ["EC"],
    "ESP":  ["ESP"],
    "CCB":  ["CCB"],
    "GYP":  ["GYP"],
    "V":    ["VSP", "SPR"],
    "CECs": ["CEC_soil"],
    "G":    ["OSD"],
}

DRAINAGE_ABBREV_MAP: Dict[str, str] = {
    "very poor": "VP",
    "poor":      "P",
    "imperfecty": "I",
    "moderately well": "MW",
    "well":       "W",
    "somewhat excessive": "SE",
    "excessive": "E"
    }
    

SPH_APPLICABILITY_SHARE_VALUES = ("100%", "50%")