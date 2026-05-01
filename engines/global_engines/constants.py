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
