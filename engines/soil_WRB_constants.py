"""Shared category sets and lookup tables for the WRB4 soil decision logic."""

# ============================================================
# 1. CATEGORIZATION — Tunisia subset (WRB 4th edition)
# ============================================================

CATEGORY_OF = {
    # Wet (Gleysols)
    "GLeu": "wet", "GLcc": "wet",

    # Alluvial (Fluvisols)
    "FLca": "alluvial", "FLeu": "alluvial", "SCfv": "alluvial",

    # Saline (Solonchaks)
    "SCha": "saline", "SCgl": "saline", "SCcso": "saline", "SCgy": "saline",

    # Sodic (Solonetz)
    "SNha": "sodic", "SNcc": "sodic",

    # Calcareous dry (Calcisols)
    "CLha": "calcareous_dry", "CLlv": "calcareous_dry", "CLpt": "calcareous_dry",

    # Gypsic dry (Gypsisols)
    "GY":   "gypsic_dry", "GYha": "gypsic_dry",
    "GYcc": "gypsic_dry", "GYpt": "gypsic_dry",
    "RGgp": "gypsic_dry", "VRgy": "gypsic_dry",

    # Young / undeveloped (Regosols)
    "RG":   "young", "RGca": "young", "RGeu": "young",

    # Sandy (Arenosols)
    "ALha": "sandy", "ARca": "sandy", "AR": "sandy",
    "ARpr": "sandy", "ARay": "sandy",

    # Shallow (Leptosols)
    "LPeu": "shallow", "LPrz": "shallow",
    "LPmo": "shallow", "LPli": "shallow",

    # Dark fertile (Kastanozems + Phaeozems)
    "KSha": "dark_fertile", "KScc": "dark_fertile",
    "PHlv": "dark_fertile",

    # Clay-cracking (Vertisols)
    "VR":   "clay_cracking", "VRha": "clay_cracking",
    "VRcc": "clay_cracking",

    # Bleached clay (Planosols)
    "PLdy": "clay_bleached",

    # Reddish/yellow developed (Luvisols + Lixisols)
    "LVab": "reddish_developed", "LVgl": "reddish_developed",
    "LVcc": "reddish_developed", "LVvr": "reddish_developed",
    "LVcr": "reddish_developed", "STlv": "reddish_developed",
    "LXha": "reddish_developed",

    # Brown moderate (Cambisols)
    "CMca": "moderate", "CMeu": "moderate", "CMgl": "moderate",
    "UMcm": "moderate", "CMvr": "moderate", "CMcr": "moderate",

    # Podzol
    "PZal": "podzol",

    # Anthropic (Anthrosols + Technosols)
    "ATpa": "anthropic", "ATtr": "anthropic", "TC": "non_soil",

    # Non-soil
    "WR": "non_soil",
}


# ============================================================
# 2. CATEGORY GROUPS — unchanged structure, WRB4 labels
# ============================================================

WET_CATS       = {"wet", "alluvial"}
SALTY_CATS     = {"saline"}
ALLUVIAL_SALTY = WET_CATS | SALTY_CATS
SODIC_CATS     = {"sodic"}
ARID_CATS      = {"calcareous_dry", "gypsic_dry"}
YOUNG_CATS     = {"young", "sandy", "shallow"}
DEVELOPED_CATS = {"dark_fertile", "clay_cracking", "clay_bleached",
                  "reddish_developed", "moderate", "podzol"}
ANTHRO_CATS    = {"anthropic"}
NONSOIL_CATS   = {"non_soil"}

DRY_UNIVERSE = (SODIC_CATS | ARID_CATS | YOUNG_CATS |
                DEVELOPED_CATS | ANTHRO_CATS | NONSOIL_CATS |
                {"clay_cracking"})