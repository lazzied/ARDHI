CROPS: dict[int, dict] = {
    1:  {"name": "wheat",             "row": 8},
    2:  {"name": "wetland rice",      "row": 9},
    3:  {"name": "dryland rice",      "row": 10},
    4:  {"name": "maize",             "row": 11},
    5:  {"name": "barley",            "row": 12},
    6:  {"name": "sorghum",           "row": 13},
    7:  {"name": "rye",               "row": 14},
    8:  {"name": "pearl millet",      "row": 15},
    9:  {"name": "foxtail millet",    "row": 16},
    10: {"name": "oat",               "row": 17},
    11: {"name": "buckwheat",         "row": 18},
    12: {"name": "white potato",      "row": 19},
    13: {"name": "sweet potato",      "row": 20},
    14: {"name": "cassava",           "row": 21},
    15: {"name": "white yam",         "row": 22},
    16: {"name": "greater yam",       "row": 23},
    17: {"name": "yellow yam",        "row": 24},
    18: {"name": "cocoyam",           "row": 25},
    19: {"name": "sugarcane",         "row": 26},
    20: {"name": "sugar beet",        "row": 27},
    21: {"name": "phaseolus bean",    "row": 28},
    22: {"name": "chickpea",          "row": 29},
    23: {"name": "cowpea",            "row": 30},
    24: {"name": "dry pea",           "row": 31},
    25: {"name": "gram",              "row": 32},
    26: {"name": "pigeonpea",         "row": 33},
    27: {"name": "groundnut",         "row": 34},
    28: {"name": "soybean",           "row": 35},
    29: {"name": "sunflower",         "row": 36},
    30: {"name": "rape",              "row": 37},
    31: {"name": "oil palm",          "row": 38},
    32: {"name": "olive",             "row": 39},
    33: {"name": "cabbage",           "row": 40},
    34: {"name": "carrot",            "row": 41},
    35: {"name": "onion",             "row": 42},
    36: {"name": "tomato",            "row": 43},
    37: {"name": "banana plantain",   "row": 44},
    38: {"name": "citrus",            "row": 45},
    39: {"name": "coconut",           "row": 46},
    40: {"name": "cotton",            "row": 47},
    41: {"name": "flax",              "row": 48},
    42: {"name": "para rubber",       "row": 49},
    43: {"name": "cacao commun",      "row": 50},
    44: {"name": "cacao hybrid",      "row": 51},
    45: {"name": "arabica coffee",    "row": 52},
    46: {"name": "robusta coffee",    "row": 53},
    47: {"name": "tea",               "row": 54},
    48: {"name": "tobacco",           "row": 55},
    49: {"name": "maize silage",      "row": 56},
    50: {"name": "alfalfa",           "row": 57},
    51: {"name": "napier grass",      "row": 58},
    52: {"name": "pasture legume",    "row": 59},
    53: {"name": "grass",             "row": 60},
    54: {"name": "sorghum biomass",   "row": 61},
    55: {"name": "jatropha",          "row": 62},
    56: {"name": "miscanthus",        "row": 63},
    57: {"name": "switchgrass",       "row": 64},
    58: {"name": "reed canary grass", "row": 65},
}
HEADER_TO_ATTRIBUTE = {
    "Soil Organic Carbon": "OC",
    "Soil Reaction": "pH",
    "Total Exchangeable Bases": "TEB",
    "Base Saturation": "BS",
    "Cation Exchange Capacity Soil": "CECsoil",
    "Cation Exchange Capacity of Clay": "CECclay",
    "Rooting/Soil Depth": "RSD",
    "Rooting/Soil Depth - D": "RSD",
    "Coarse Fragments": "GRC",
    "Electric Conductivity": "EC",
    "Exchangeable Sodium Percentage": "ESP",
    "Calcium Carbonate": "CCB",
    "Calcium Sulphate": "GYP",
    "Vertic Soils Properties": "VSP",
    "Gelic Soil Properties": "GRC",  # adjust if needed
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
    "SOC":  "OC",
    "pH":   "pH",
    "TEB":  "TEB",
    "CECa": "CECclay",
    "BS":   "BS",
    "RC":   "RSD",
    "CF":   "GRC",
    "EC":   "EC",
    "ESP":  "ESP",
    "CCB":  "CCB",
    "GYP":  "GYP",
    "V":    "VSP",
    "CECs": "CECsoil",
    "G":    "GEL",
}