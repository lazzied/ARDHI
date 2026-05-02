KEEP_CODES = [
    # suitability_classes
    "RES05-SIX30AS", "RES05-SCX30AS",
    # suitability_index
    "RES05-SXX30AS", "RES05-SX2",
    # agro-ecological_attainable_yield
    "RES05-YCX30AS",
    # crop_water_indicators
    "RES05-ETL", "RES05-WDL",
    # area_yield_and_production
    "RES06-HAR", "RES06-PRD", "RES06-YLD",
    # Agro-climatic_Potential_Yield
    "RES02-YLD",
    # constraints (climate constraints)
    "RES02-FC0", "RES02-FC1", "RES02-FC2", "RES02-FC3",
    # constraints (soil constraints) - MISSING
    "SQX", "SQ-IDX",
    # growth_cycle_attributes (crop specific)
    "RES02-CBD", "RES02-CYL", "RES02-ETA", "RES02-TSC", "RES02-WDE",
    # moisture regime
    "RES01-ET0", "RES01-PRC", "RES01-RID", "RES01-RIW", "RES01-RIS",
    # climate classification
    "RES01-MCL", "RES01-MC2",
    # growing period 
    "RES01-LGP", "RES01-LGD", "RES01-LD1", "RES01-LGB", "RES01-NDD",
    # intensification
    "RES01-MCR", "RES01-MCI",
    # terrain
    "AEZ57", "SLOPE-MED", "LR-IRR",
]

"""
    SSP (climate scenarios) — keep only HIST, drop the rest
    SSP126, SSP370, SSP585 are future emissions scenarios.
    For your current-baseline recommendation system using AGERA5 + HP0120, you only need HIST.
    The future SSPs become relevant only if you add a "climate projection" tab later.

    CLIM (climate models) — keep only AGERA5,
    drop the rest
    GFDL-ESM4, IPSL-CM6A-LR, MPI-ESM1-2-HR, MRI-ESM2-0, UKESM1-0-LL are all future GCM models
    paired with SSP scenarios. ENSEMBLE is useful only if doing multi-model averaging for projections.
    For historical current conditions, AGERA5 is the only one you need.

    PERIOD — keep HP0120, drop the rest
    HP8100 (1981–2000) is outdated as a baseline. FP2140, FP4160, FP6180, FP8100 are all future projections
    — drop unless you build a future scenario feature.
        
"""
DROP_MODEL_PARAMETERS= [
    # SSP
    "SSP126", "SSP370", "SSP585",
    # CLIM
    "GFDL-ESM4", "IPSL-CM6A-LR", "MPI-ESM1-2-HR", "MRI-ESM2-0", "UKESM1-0-LL", "ENSEMBLE",
    # PERIOD
    "HP8100", "FP2140", "FP4160", "FP6180", "FP8100",
    
     
]

"""
these are the crops tht are nearly impossible to grow in tunisian soil and climate conditions
"""
"""
DROP_CROP = [
    # Cacao
    "COCO", "COCC", "COCH", "COC",
    # Coffee
    "COFA", "COFR", "COFF", "COF",
    # Oil palm
    "OILP", "OLP",
    # Rubber
    "PRUB", "RUB",
    # Coconut
    "COCN", "CON", "COC1", "COC2", "COC3",
    # Tea
    "TEAS", "TEA",
    # Banana
    "BANA", "BAN",
    # Energy cane
    "ECAN", "ECANV2", "ECANV3", "ECN", "EC2", "EC3",
    # Brachiaria
    "BRCH", "BCH",
    # Napier grass
    "NAPR", "NAP",
    # Macauba palm
    "MCAU", "MCAU2", "MCA",
    # Yams
    "GYAM", "WYAM", "YYAM", "YAMS", "YAM",
    # Tannia
    "TANN",
    # Taro
    "TARODL", "TAROWL", "TAROW", "TAROD", "CYA",
    # Cassava
    "CASV", "CSV",
    # Cashew
    "CASH", "CSH",
    # Pigeon pea
    "PIGP", "PIG",
    # Cowpea
    "COWP", "COW",
    # Fonio
    "FONIO",
    # Reed canary grass
    "RCGR", "RCG",
    # Switchgrass
    "SWGR", "SWG",
    # Miscanthus
    "MISC", "MIS",
    # Tef
    "TEFF", "TEF",
    # Wetland rice
    "RICW", "RCW",
]
"""

"""
Impossible — wrong climate entirely:

COCO/COCC/COCH/COC — Cacao: needs humid equatorial belt, 2000mm+ rainfall
COFA/COFR/COFF/COF — Coffee: needs tropical highlands or humid tropics
OILP/OLP — Oil palm: strictly humid equatorial, needs >1800mm/year
PRUB/RUB — Rubber: humid tropical only
COCN/CON/COC1/COC2/COC3 — Coconut: needs coastal tropical humid climate
TEAS/TEA — Tea: needs high rainfall + acidic soils, incompatible with Tunisian soils
BANA/BAN — Banana: can survive in extreme southern coastal pockets but commercially impossible at scale
ECAN/ECANV2/ECANV3/ECN/EC2/EC3 — Energy cane: tropical humid crop
BRCH/BCH — Brachiaria: tropical pasture grass, needs humid conditions
NAPR/NAP — Napier grass: tropical humid forage
MCAU/MCAU2/MCA — Macauba palm: Brazilian tropical palm
GYAM/WYAM/YYAM/YAMS/YAM — Yams: humid tropical tubers
TANN — Tannia: humid tropical root crop
TARODL/TAROWL/TAROW/TAROD/CYA — Taro: needs waterlogged or very humid conditions
CASV/CSV — Cassava: marginal at best, needs humid tropics for commercial yield
CASH/CSH — Cashew: tropical coastal, needs humidity
PIGP/PIG — Pigeon pea: tropical/sub-tropical, very marginal in Tunisia
COWP/COW — Cowpea: borderline, survives but negligible yield in Tunisian conditions
FONIO — Fonio: West African cereal, humid tropics
RCGR/RCG — Reed canary grass: temperate waterlogged soils, not Tunisia
SWGR/SWG — Switchgrass: North American prairie grass, wrong climate
MISC/MIS — Miscanthus: temperate humid bioenergy crop
TEFF/TEF — Tef: Ethiopian highland crop, possible in theory but zero agricultural tradition
RICW/RCW — Wetland rice: needs flooded paddies, not viable at scale in Tunisia
GYAM — Greater yam: humid tropical
Keep everything else — crops like olive, wheat, barley, sorghum, sunflower, chickpea, tomato, watermelon, citrus, alfalfa, groundnut, sesame, soybean, cotton, sugarbeet, mango, and the temperate cereals all have genuine presence or strong potential in Tunisia.
"""