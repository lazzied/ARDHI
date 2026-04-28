from pyaez import SoilConstraints 

EDAPHIC_PATH_RAINFED = "" # maize/rainfed/intermediate
EDAPHIC_PATH_IRRIGATED = "" # maize/sprinkler/intermediate
SOIL_PARAM_PATH = "" # this includes topsoil and bottomsoil



soil_constraints = SoilConstraints.SoilConstraints()

# Importing the excel sheet of soil  
soil_constraints.importSoilReductionSheets(EDAPHIC_PATH_RAINFED,EDAPHIC_PATH_IRRIGATED)


# Soil Qualities 
soil_constraints.calculateSoilQualities("I", SOIL_PARAM_PATH, SOIL_PARAM_PATH) 

soil_constraints.calculateSoilRating("I") 

# Extracting soil qualities 
soil_ratings = soil_constraints.getSoilRatings() 

SOIL_SMU_ID = [[]] # 
YIELD_IN = [[]] # yield before soil reduction factors; # but becareful this still hasn't applied the terrain constraints, dso this isn't the final output

# Soil Constraints 
yield_out = soil_constraints.applySoilConstraints(SOIL_SMU_ID, YIELD_IN)

# FC0 groups (FC1 / FC2 / FC3) ;; this is the input ; the output is the new yield with soil constraints applied
# then the yield will be fed to the terrain constraints; and outputs the final yield


"""
    Function Arguments 
soil_map 2D NumPy array, corresponding to soil unit. Each pixel value must be SMU. This 
code is used to match the soil rating with the input yield. 
yield_in 2D NumPy array, corresponding to the yield before applying the soil reduction 
factors (either rainfed or irrigated conditions) 
Function Returns 
yield_out 2D NumPy array. The yield reduced by soil-related factors [same unit as 
yield_in]    
"""

