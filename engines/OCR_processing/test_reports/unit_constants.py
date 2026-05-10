# this part handle the conversion between units
# all of the units

APPENDIX_UNITS = {
    "SOC": "% weight",
    "pHH2O": "-log(H+)",
    "TEB": "cmol/kg",
    "CECa": "cmol/kg",
    "BS": "%",
    "RC": "cm",
    "D": "cm",
    "CF": "%",
    "EC": "dS/m",
    "ESP": "%",
    "CCB": "%",
    "GYP": "%",
    "V": None,
    "CECs": "cmol/kg",
    "G": None
}

APPENDIX_TO_PyAEZ = {
    "OC":       ["Soil Organic Carbon (SOC % weight)"],
    "pH":       ["Soil Reaction (pHH2O)"],
    "TEB":      ["Total Exchangeable Bases (TEB)"],
    "CECclay":  ["Cation Exchange Capacity of Clay (CECclay)"],
    "BS":       ["Base Saturation (BS)"],
    "RSD":      ["Rooting / Soil Depth"],
    "EC":       ["Electrical Conductivity (EC)"],
    "GRC":      ["Coarse Fragments (CF)", "Gravel / Coarse Fragments"],
    "ESP":      ["Exchangeable Sodium Percentage (ESP)"],
    "CCB":      ["Calcium Carbonate (CCB)"],
    "GYP":      ["Calcium Sulphate (GYP)"],
    "SPR":      ["Vertic Soil Properties", "Soil Property Rating"],
    "VSP":      ["Vertic Soil Properties"],
    "CECsoil": ["Cation Exchange Capacity Soil (CECsoil)"],
    "TXT":      ["Soil Texture Classes"],
    "DRG":      ["Drainage Class"],
    "SPH":      ["Soil Phase Rating", "Soil Phase"],
    "OSD":      ["Gelic soil properties"],
}

REPORT_UNITS = {
    "pH": "---",
    "Conductivité": "mS/Cm",
    "Salinité": "%",
    "Humidité": "%",
    "Matière sèche": "%",
    "Matière Organique": "%",
    "Azote total": "%",
    "Rapport C/N": "---",
    "Souffre": "%",
    "Taux de carbone": "%",
    "Carbonates de Calcium": "%",
    "Phosphore": "g/Kg MS",
    "Potassium": "g/Kg MS",
    "Magnésium": "g/Kg MS",
    "Calcium": "g/Kg MS",
    "Manganèse": "g/Kg MS",
    "Bore": "g/Kg MS",
    "Cuivre": "g/Kg MS",
    "Fer": "g/Kg MS",
    "Zinc": "g/Kg MS",
    "Molybdène": "g/Kg MS",
    "Calcium échangeable": "g/Kg MS",
    "Magnésium échangeable": "g/Kg MS",
    "Potassium échangeable": "g/Kg MS",
    "Phosphore échangeable": "g/Kg MS",
    "Sodium échangeable": "g/Kg MS",
    "Calcaire actif": "%"
}

HWSD_UNITS = {
    "ID": None,
    "HWSD2_SMU_ID": None,
    "WISE30s_SMU_ID": None,
    "HWSD1_SMU_ID": None,
    "COVERAGE": None,
    "SEQUENCE": None,
    "SHARE": "%",
    "NSC_MU_SOURCE1": None,
    "NSC_MU_SOURCE2": None,
    "WRB_PHASES": "Class",
    "WRB4": "Class",
    "WRB2": "Class",
    "FAO90": "Class",
    "ROOT_DEPTH": "Class",
    "PHASE1": None,
    "PHASE2": None,
    "ROOTS": "cm",
    "IL": "cm",
    "SWR": "Class",
    "DRAINAGE": "Class",
    "AWC": "mm",
    "ADD_PROP": "Class",
    "LAYER": None,
    "TOPDEP": "cm",
    "BOTDEP": "cm",
    "COARSE": "% volume",
    "SAND": "% weight",
    "SILT": "% weight",
    "CLAY": "% weight",
    "TEXTURE_USDA": None,
    "TEXTURE_SOTER": None,
    "BULK": "g/cm3",
    "REF_BULK": "g/cm3",
    "ORG_CARBON": "% weight",
    "PH_WATER": "-log(H+)",
    "TOTAL_N": "g/kg",
    "CN_RATIO": None,
    "CEC_SOIL": "cmolc/kg",
    "CEC_CLAY": "cmolc/kg",
    "CEC_EFF": "cmolc/kg",
    "TEB": "cmolc/kg",
    "BSAT": "% CECsoil",
    "ALUM_SAT": "% ECEC",
    "ESP": "%",
    "TCARBON_EQ": "% weight",
    "GYPSUM": "% weight",
    "ELEC_COND": "dS/m"
}

EXPECTED_PyAEZ_UNITS = {
"TXT1": None,          # categorical (Fine/Medium/Coarse)
"TXT2": None,          # categorical (Fine/Medium/Coarse)
"TXT7": None,          # categorical (Fine/Medium/Coarse)
"OC": "% weight",
"pH": "-log(H+)",
"TEB": "cmolc/kg",
"BS": "%",
"CECsoil": "cmolc/kg",
"CECclay": "cmolc/kg",
"RSD": "cm",
"GRC": "% volume",
"DRG": None,           # categorical (VP/P/I/MW/W/SE/E)
"ESP": "%",
"EC": "dS/m",
"SPH3": None,          # categorical (Lithic/skeletic/hyperskeletic)
"SPH4": None,          # categorical (Lithic/skeletic/hyperskeletic)
"SPH5": None,          # categorical (Lithic/skeletic/hyperskeletic)
"SPH6": None,          # categorical (Lithic/skeletic/hyperskeletic)
"SPH7": None,          # categorical (Lithic/skeletic/hyperskeletic)
"OSD": "cm",
"SPR": None,           # binary (0/1)
"CCB": "% weight",
"GYP": "% weight",
"VSP": None            # binary (0/1)
}




