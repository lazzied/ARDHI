"""Shared category sets and lookup tables for the FAO soil decision logic."""
# ============================================================
# 1. CATEGORIZATION — Tunisia subset
# ============================================================

CATEGORY_OF = {
    # Wet (gleyed in place)
    "Eutric Gleysols": "wet", "Calcic Gleysols": "wet",

    # Alluvial (river-deposited; Salic kept here taxonomically but
    # also routed through the "salty flat" answer in Q1)
    "Calcaric Fluvisols": "alluvial", "Eutric Fluvisols": "alluvial",
    "Salic Fluvisols": "alluvial",

    # Saline (Solonchaks)
    "Solonchaks": "saline",
    "Gleyic Solonchaks": "saline", "Haplic Solonchaks": "saline",
    "Sodic Solonchaks": "saline", "Gypsic Solonchaks": "saline",

    # Sodic (Solonetz)
    "Haplic Solonetz": "sodic", "Calcic Solonetz": "sodic",

    # Calcareous dry
    "Haplic Calcisols": "calcareous_dry",
    "Luvic Calcisols": "calcareous_dry",
    "Petric Calcisols": "calcareous_dry",

    # Gypsic dry
    "Gypsisols": "gypsic_dry",
    "Haplic Gypsisols": "gypsic_dry",
    "Calcic Gypsisols": "gypsic_dry",
    "Petric Gypsisols": "gypsic_dry",
    "Gypsic Regosols": "gypsic_dry",
    "Gypsic Vertisols": "gypsic_dry",

    # Young / undeveloped
    "Regosols": "young", "Calcaric Regosols": "young", "Eutric Regosols": "young",

    # Sandy
    "Calcaric Arenosols": "sandy", "Haplic Arenosols": "sandy",
    "Dunes & shift.sands": "sandy",

    # Shallow (Leptosols)
    "Eutric Leptosols": "shallow", "Rendzic Leptosols": "shallow",
    "Mollic Leptosols": "shallow", "Lithic Leptosols": "shallow",

    # Dark fertile (steppe / forest-steppe transitions)
    "Haplic Kastanozems": "dark_fertile", "Calcic Kastanozems": "dark_fertile",
    "Luvic Phaeozems": "dark_fertile",

    # Clay-cracking (Vertisols)
    "Vertisols": "clay_cracking",
    "Eutric Vertisols": "clay_cracking",
    "Calcic Vertisols": "clay_cracking",

    # Bleached clay (Planosols)
    "Dystric Planosols": "clay_bleached",

    # Reddish/yellow developed (Luvisols + the rare Lixisols/Alisols
    # all collapsed here — field-indistinguishable in Tunisian context)
    "Albic Luvisols": "reddish_developed", "Albic Luvsiols": "reddish_developed",
    "Gleyic Luvisols": "reddish_developed",
    "Stagnic Luvisols": "reddish_developed",
    "Calcic Luvisols": "reddish_developed",
    "Vertic Luvisols": "reddish_developed",
    "Chromic Luvisols": "reddish_developed",
    "Haplic Lixisols": "reddish_developed",
    "Haplic Alisols": "reddish_developed",

    # Brown moderate (Cambisols)
    "Calcaric Cambisols": "moderate", "Eutric Cambisols": "moderate",
    "Gleyic Cambisols": "moderate", "Humic Cambisols": "moderate",
    "Vertic Cambisols": "moderate", "Chromic Cambisols": "moderate",

    # Podzol (rare, mountainous Khroumirie)
    "Haplic Podzols": "podzol",

    # Anthropic
    "Cumulic Anthrosols": "anthropic",

    # Non-soil
    "Urban, mining, etc.": "non_soil",
    "Water bodies": "non_soil",
}


# Category groups used by the tree.
WET_CATS         = {"wet", "alluvial"}
SALTY_CATS       = {"saline"}
ALLUVIAL_SALTY   = WET_CATS | SALTY_CATS  # for the "salty flat" answer
SODIC_CATS       = {"sodic"}
ARID_CATS        = {"calcareous_dry", "gypsic_dry"}
YOUNG_CATS       = {"young", "sandy", "shallow"}
DEVELOPED_CATS   = {"dark_fertile", "clay_cracking", "clay_bleached",
                    "reddish_developed", "moderate", "podzol"}
ANTHRO_CATS      = {"anthropic"}
NONSOIL_CATS     = {"non_soil"}

# All non-wet, non-salty categories — used as the "keep" set for the
# "no, the ground is dry" answer in Q1.
DRY_UNIVERSE = (SODIC_CATS | ARID_CATS | YOUNG_CATS |
                DEVELOPED_CATS | ANTHRO_CATS | NONSOIL_CATS |
                {"clay_cracking"})  # cracking clays are dry-tolerant

