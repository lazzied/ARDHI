from typing import Dict


NUM_ATTRIBUTES  = [
    "TXT", "OC", "pH", "TEB", "BS",
    "CEC_soil", "CEC_clay", "RSD", "GRC", "DRG",
    "ESP", "EC", "SPH", "SPR", "OSD",
    "CCB", "GYP", "VSP",
]

CLASS_ATTRIBUTES = ["TXT","DRG","SPH"]

ATTRIBUTES = NUM_ATTRIBUTES + CLASS_ATTRIBUTES

HWSD_MAPPER= {
    "TEXTURE_USDA": "TXT",
    "ORG_CARBON": "OC",
    "PH_WATER": "pH",
    "TEB": "TEB",
    "BSAT": "BS",
    "CEC_SOIL": "CEC_soil",
    "CEC_CLAY": "CEC_clay",
    "ROOT_DEPTH": "RSD",
    "COARSE": "GRC",
    "DRAINAGE": "DRG",
    "ESP": "ESP",
    "ELEC_COND": "EC",
    "PHASE1": "SPH",
    "ADD_PROP": ["OSD", "SPR", "VSP"],
    "GYPSUM": "GYP",
    "TCARBON_EQ": "CCB", 
}

HWSD_COLUMNS = [
           "TEXTURE_USDA",
           "DRAINAGE",
           "ADD_PROP",
           "PHASE1",
           "ROOT_DEPTH",
           "GYPSUM",
           "COARSE",
           "CEC_clay",
           "CEC_soil"
]

REPORT_MAP = {
        "OC":  "Taux de carbone",
        "pH":  "pH",
        "EC":  "Conductivité",
        "CCB": "Carbonates de Calcium",
    }

SOIL_DEPTH = {
    "Deep (> 100cm)":           150,
    "Moderately Deep (< 100cm)": 75,
    "Shallow (< 50cm)":          30,
    "Very Shallow (< 10cm)":      5,
}

STRATEGIES: Dict[str, str] = {
    "OC": "READ", "pH": "READ", "EC": "READ", "CCB": "READ",
    "TXT": "AUG", "DRG": "AUG", "OSD": "AUG", "SPR": "AUG",
    "VSP": "AUG", "SPH": "AUG", "RSD": "AUG", "GYP": "AUG",
    "GRC": "AUG", "CEC_CLAY": "AUG", "CEC_SOIL": "AUG",
    "TEB": "CALC", "BS": "CALC", "ESP": "CALC",
}