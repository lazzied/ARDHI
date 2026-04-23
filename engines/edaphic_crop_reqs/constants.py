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
    1:  {"name": "wheat"},
    2:  {"name": "wetland rice"},
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
    43: {"name": "cacao commun"},
    44: {"name": "cacao hybrid"},
    45: {"name": "arabica coffee"},
    46: {"name": "robusta coffee"},
    48: {"name": "tobacco"},
    49: {"name": "maize silage"},
    50: {"name": "alfalfa"},
    51: {"name": "napier grass"},
    52: {"name": "pasture legume"},
    53: {"name": "grass"},
    54: {"name": "sorghum biomass"},
}

CROPS_DRIP_IRRIGATION: dict[int, dict] = {
    21: {"name": "phaseolus bean"},
    31: {"name": "oil palm"},
    32: {"name": "olive"},
    33: {"name": "cabbage"},
    34: {"name": "carrot"},
    35: {"name": "onion"},
    36: {"name": "tomato"},
    37: {"name": "banana plantain"},
    38: {"name": "citrus"},
    39: {"name": "coconut"},
    43: {"name": "cacao commun"},
    44: {"name": "cacao hybrid"},
    45: {"name": "arabica coffee"},
    46: {"name": "robusta coffee"},
    47: {"name": "tea"},
}

HEADER_TO_ATTRIBUTE = {
    "Soil Organic Carbon (SOC % weight)": "OC",
    "Soil Reaction (pHH2O)": "pH",
    "Total Exchangeable Bases (TEB)": "TEB",
    "Cation Exchange Capacity of Clay (CECclay)": "CECclay",
    "Base Saturation (BS)": "BS",
    "Rooting / Soil Depth": "RSD",
    "Electrical Conductivity (EC)": "EC",
    "Coarse Fragments (CF)": "CF",
    "Exchangeable Sodium Percentage (ESP)": "ESP",
    "Calcium Carbonate (CCB)": "CCB",
    "Calcium Sulphate (GYP)": "GYP",
    "Vertic Soil Properties": "VSP",
    "Cation Exchange Capacity Soil (CECsoil)": "CECsoil",
    "Gelic Soil Properties": "GSP",
    "Soil Texture Classes": "TXT",
    "Drainage Class": "DRG",
    "Soil Phase": "SPH",
}


SPECIAL_ATTRIBUTES = {
    "Soil Texture Classes": "TXT",
    "Drainage Class": "DRG",
    "Soil Phase": "SPH",
}

ATTRIBUTE_VALUES = {
    "TXT": {  # Soil Texture Classes
        "values": [
            "clay (heavy)", "silty clay", "clay (light)", "silty clay loam",
            "clay loam", "silt", "silt loam", "sandy clay",
            "loam", "sandy clay loam", "sandy loam", "loamy sand", "sand"
        ]
    },

    "DRG": {  # Drainage Class
        "values": [
            "very poor", "poor", "imperfectly", "moderately well",
            "well", "somewhat excessive", "excessive"
        ],
        "codes": {
            "very poor": "VP",
            "poor": "P",
            "imperfectly": "I",
            "moderately well": "MW",
            "well": "W",
            "somewhat excessive": "SE",
            "excessive": "E"
        }
    },

    "SPH": {  # Soil Phase
        "values": [
            "stony", "lithic", "petric", "petrocalcic", "petrogypsic",
            "petroferric", "fragipan", "duripan", "anthraquic", "placic",
            "rudic", "skeletic", "erosion", "gravelly", "concretionary",
            "obstacle to roots", "no information",
            "no obstacle to roots between 0 and 80 cm",
            "obstacle to roots between 60 and 80 cm depth",
            "obstacle to roots between 40 and 60 cm depth",
            "obstacle to roots between 20 and 40 cm depth",
            "obstacle to roots between 0 and 20 cm depth",
            "impermeable layer", "no impermeable layer within 150 cm depth",
            "impermeable layer between 80 and 150 cm depth",
            "impermeable layer between 40 and 80 cm depth",
            "impermeable layer within 40 cm depth",
            "phreatic", "inundic", "excessively drained", "flooded",
            "wetness", "no wetness within 80 cm for over 3 months",
            "wetness within 80 cm for 3 to 6 months",
            "wetness within 80 cm over 6 months",
            "wetness within 40 cm depth for over 11 month",
            "saline", "sodic", "salic",
            "no limitation to agricultural use"
        ]
    },

    "SPH_share": {  # Soil Phase Applicability Share
        "values": ["100%", "50%"]
    }
}

# Maps abbreviated attribute labels in constraint class row to short names
# used in the output (matching the reference maiz file)
ATTR_ABBREV_MAP: dict[str, str] = {
    "SOC": "OC",        # Soil Organic Carbon
    "pH": "pH",         # same
    "TEB": "TEB",       # same
    "CECa": "CECclay",  # CEC of clay
    "BS": "BS",         # same
    "RC": "RSD",        # Rooting Conditions → Rooting/Soil Depth
    "CF": "CF",         # same (fixed from old GRC confusion)
    "EC": "EC",         # same
    "ESP": "ESP",       # same
    "CCB": "CCB",       # same
    "GYP": "GYP",       # same
    "V": "VSP",         # Vertic → Vertic Soil Properties
    "CECs": "CECsoil",  # soil-level CEC
    "G": "GSP",         # Gelic → Gelic Soil Properties
}