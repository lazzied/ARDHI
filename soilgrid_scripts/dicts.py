from pathlib import Path

SOIL_PROPERTIES = {
    "phh2o":    "http://maps.isric.org/mapserv?map=/map/phh2o.map",
    "nitrogen": "http://maps.isric.org/mapserv?map=/map/nitrogen.map",
    "soc":      "http://maps.isric.org/mapserv?map=/map/soc.map",
    "sand":     "http://maps.isric.org/mapserv?map=/map/sand.map",
    "clay":     "http://maps.isric.org/mapserv?map=/map/clay.map",
    "silt":     "http://maps.isric.org/mapserv?map=/map/silt.map",
    "bdod":     "http://maps.isric.org/mapserv?map=/map/bdod.map",
    "cec":      "http://maps.isric.org/mapserv?map=/map/cec.map",
    "cfvo":     "http://maps.isric.org/mapserv?map=/map/cfvo.map",
    "ocd":      "http://maps.isric.org/mapserv?map=/map/ocd.map",
    #"ocs":      "http://maps.isric.org/mapserv?map=/map/ocs.map",
    "wv0010":   "http://maps.isric.org/mapserv?map=/map/wv0010.map",
    "wv0033":   "http://maps.isric.org/mapserv?map=/map/wv0033.map",
    "wv1500":   "http://maps.isric.org/mapserv?map=/map/wv1500.map",

}

SOIL_CLASSIFICATION = {
    "wrb": "http://maps.isric.org/mapserv?map=/map/wrb.map",
}


UNITS = {
    "phh2o":    "pH",
    "nitrogen": "g/kg",
    "soc":      "g/kg",
    "sand":     "%",
    "clay":     "%",
    "silt":     "%",
    "bdod":     "kg/dm³",
    "cec":      "mmol(c)/kg",
    "cfvo":     "%",
    "ocd":      "kg/m³",
    #"ocs":      "kg/m²",
    "wv0010":   "m³/m³",
    "wv0033":   "m³/m³",
    "wv1500":   "m³/m³",
}


SOILGRIDS_ID = {
    "ph_water":               "phh2o",
    "nitrogen":               "nitrogen",
    "organic_carbon":         "soc",
    "sand":                   "sand",
    "clay":                   "clay",
    "silt":                   "silt",
    "bulk_density":           "bdod",
    "cation_exchange":        "cec",
    "coarse_fragments":       "cfvo",
    "organic_carbon_density": "ocd",
    "organic_carbon_stock":   "ocs",
    "water_retention_10kpa":  "wv0010",
    "water_retention_33kpa":  "wv0033",
    "water_retention_1500kpa":"wv1500",

}

# Scale factors to convert raw integer values to real units
# SoilGrids stores values as integers — divide by scale to get actual value
SCALE_FACTORS = {
    "phh2o":    10,
    "nitrogen": 100,
    "soc":      10,
    "sand":     10,
    "clay":     10,
    "silt":     10,
    "bdod":     100,
    "cec":      10,
    "cfvo":     10,
    "ocd":      10,
    "ocs":      10,
    "wv0010":   1000,
    "wv0033":   1000,
    "wv1500":   1000,
}

DESCRIPTIONS = {
    "phh2o":    "Soil acidity/alkalinity — critical for nutrient availability",
    "nitrogen": "Total nitrogen — key macronutrient for plant growth",
    "soc":      "Soil organic carbon — indicator of soil health and fertility",
    "sand":     "Sand fraction — affects drainage and aeration",
    "clay":     "Clay fraction — affects water retention and nutrient holding",
    "silt":     "Silt fraction — affects soil structure and erosion risk",
    "bdod":     "Mass per unit volume — indicates soil compaction",
    "cec":      "Nutrient holding capacity — higher means more fertile",
    "cfvo":     "Stones and gravel — affects root penetration",
    "ocd":      "Organic carbon per volume — carbon stock indicator",
    #"ocs":      "Total organic carbon in the soil column",
    "wv0010":   "Water at field capacity — available after free drainage",
    "wv0033":   "Plant available water — optimal irrigation reference point",
    "wv1500":   "Water at wilting point — unavailable to plant roots",
    "wrb":      "WRB soil classification — international soil type system",
}

DEPTHS = ["0-5cm", "5-15cm", "15-30cm"]

TUNISIA_SUBSETS = [('X', 1174846, 1714576), ('Y', 3361849, 4174481)]
CRS             = "http://www.opengis.net/def/crs/EPSG/0/152160"
DATA_DIR        = Path("soil_data")