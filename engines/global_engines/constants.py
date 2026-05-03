"""Shared constant tables for global crop, soil, and EcoCrop-related workflows."""
from typing import Dict


SUITABILITY_CLASSES_SIX = {
    1: {"label": "Very high",      "si_min": 85, "description": "Excellent conditions for this crop"},
    2: {"label": "High",           "si_min": 70, "description": "Very good conditions with minor limitations"},
    3: {"label": "Good",           "si_min": 55, "description": "Good conditions with moderate limitations"},
    4: {"label": "Medium",         "si_min": 40, "description": "Moderate conditions, yield notably below potential"},
    5: {"label": "Moderate",       "si_min": 25, "description": "Marginal conditions, significant limitations"},
    6: {"label": "Marginal",       "si_min": 10, "description": "Poor conditions, low yield expected"},
    7: {"label": "Very marginal",  "si_min": 0,  "description": "Very poor conditions, minimal yield"},
    8: {"label": "Not suitable",   "si_min": None, "description": "Cannot grow this crop here"},
    9: {"label": "Water",          "si_min": None, "description": "Water body, not land"},
}

INPUT_LEVEL_LABELS = {
    "HRLM": "Rain-fed, high input",
    "HILM": "Irrigated, high input",
    "LRLM": "Rain-fed, low input",
    "LILM": "Irrigated, low input",
}


# Units note shown alongside yield values
YIELD_UNIT_NOTE = "kg(DW)/ha — dry weight. Sugar beet/cane: kg sugar/ha, oil palm: kg oil/ha, cotton: kg lint/ha."

ECO_CROP = [
    "alfalfa",
    "arabica coffee",
    "barley",
    "buckwheat",
    "cabbage",
    "carrot",
    "cassava",
    "chickpea",
    "citrus",
    "coconut",
    "cocoyam",
    "cotton",
    "cowpea",
    "flax",
    "foxtail millet",
    "gram",
    "grass",
    "greater yam",
    "groundnut",
    "jatropha",
    "maize",
    "napier grass",
    "oat",
    "oil palm",
    "olive",
    "onion",
    "pearl millet",
    "rape",
    "robusta coffee",
    "rye",
    "sorghum",
    "soybean",
    "sugarcane",
    "sunflower",
    "sweet potato",
    "switchgrass",
    "tea",
    "tobacco",
    "tomato",
    "wheat",
    "white potato",
    "white yam"
]

CROP_COLUMNS= [
    "common_name",
    "scientific_name",
    "life_form",
    "physiology",
    "habit",
    "category",
    "life_span",
    "plant_attributes",
    "notes",
]

ECOLOGY_COLUMNS = [
    "temp_opt_min",
    "temp_opt_max",
    "temp_abs_min",
    "temp_abs_max",
    "rainfall_opt_min",
    "rainfall_opt_max",
    "rainfall_abs_min",
    "rainfall_abs_max",
    "soil_ph_opt_min",
    "soil_ph_opt_max",
    "soil_ph_abs_min",
    "soil_ph_abs_max",
    "altitude_abs_min",
    "altitude_abs_max",
    "latitude_abs_min",
    "latitude_abs_max",
    "soil_texture_optimal",
    "soil_texture_absolute",
    "soil_depth_optimal",
    "soil_depth_absolute",
    "soil_fertility_optimal",
    "soil_fertility_absolute",
    "soil_drainage_optimal",
    "soil_drainage_absolute",
    "soil_salinity_optimal",
    "soil_salinity_absolute",
    "light_intensity_optimal",
    "light_intensity_absolute"
]

CULTIVATION_COLUMNS = [
    "production_system",
    "crop_cycle_min",
    "crop_cycle_max",
    "cropping_system",
    "subsystem",
    "companion_species",
    "mechanization_level",
    "labour_intensity"]


CLIMATE_COLUMNS = [
    "climate_zone",
    "photoperiod",
    "killing_temp_rest",
    "killing_temp_growth",
    "abiotic_tolerance",
    "abiotic_susceptibility",
    "introduction_risks"
]
# ── Mapping: logical need → DB column names ──────────────────────────────────

CLIMATE_NEEDS_COLUMNS = {
    "temperature":     ["temp_opt_min", "temp_opt_max", "temp_abs_min", "temp_abs_max"],
    "rainfall":        ["rainfall_opt_min", "rainfall_opt_max", "rainfall_abs_min", "rainfall_abs_max"],
    "light_intensity": ["light_intensity_optimal", "light_intensity_absolute"],
}

TERRAIN_NEEDS_COLUMNS = {
    "altitude": ["altitude_abs_min", "altitude_abs_max"],
    "latitude": ["latitude_abs_min", "latitude_abs_max"],
}

SOIL_NEEDS_COLUMNS = {
    "pH":            ["soil_ph_opt_min", "soil_ph_opt_max", "soil_ph_abs_min", "soil_ph_abs_max"],
    "soil_texture":  ["soil_texture_optimal", "soil_texture_absolute"],
    "soil_depth":    ["soil_depth_optimal", "soil_depth_absolute"],
    "soil_fertility":["soil_fertility_optimal", "soil_fertility_absolute"],
    "soil_drainage": ["soil_drainage_optimal", "soil_drainage_absolute"],
    "soil_salinity": ["soil_salinity_optimal", "soil_salinity_absolute"],
}
SHEET_NAMES = {
        "SQ1": "nutrient_availability",
        "SQ2": "nutrient_retention_capacity",
        "SQ3": "rooting_conditions",
        "SQ4": "oxygen_availability",
        "SQ5": "salinity_and_sodicity",
        "SQ6": "lime_and_gypsum",
        "SQ7": "workability",
    }

ATTRIBUTE_TO_HEADER: Dict[str, str] = {
    "OC":      "soil organic carbon (soc % weight)",
    "TEB":     "total exchangeable bases (teb)",
    "CECclay": "cation exchange capacity of clay (cecclay)",
    "BS":      "base saturation (bs)",
    "EC":      "electrical conductivity (ec)",
    "GRC":     "coarse fragments (cf)",
    "ESP":     "exchangeable sodium percentage (esp)",
    "CCB":     "calcium carbonate (ccb)",
    "GYP":     "calcium sulphate (gyp)",
    "SPR":     "soil property rating",
    "VSP":     "vertic soil properties",
    "CECsoil": "cation exchange capacity soil (cecsoil)",
    "SPH":     "soil phase",
    "OSD":     "gelic soil properties",
}

STANDARD_UNITS: Dict[str, str] = {
    "OC":      "% weight",
    "TEB":     "cmol(+)/kg",
    "CECclay": "cmol(+)/kg",
    "BS":      "%",
    "EC":      "dS/m",
    "GRC":     "%",
    "ESP":     "%",
    "CCB":     "%",
    "GYP":     "%",
    "SPR":     "boolean",
    "VSP":     "boolean",
    "CECsoil": "cmol(+)/kg",
    "SPH":     "categorical",
    "OSD":     "boolean",
}

# fct == 100 → no constraint; abs = lowest non-zero non-null (tightest threshold)
ASCENDING_ATTRIBUTES  = {"OC", "TEB", "CECclay", "BS", "CECsoil"}
# fct == 100 → no constraint; abs = highest non-zero non-null (worst extreme)
DESCENDING_ATTRIBUTES = {"EC", "ESP", "CCB", "GYP", "GRC"}
# val is binary 0/1 → convert to bool
BOOLEAN_ATTRIBUTES    = {"VSP", "SPR", "OSD"}
