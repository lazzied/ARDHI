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