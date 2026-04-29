import sqlite3
import difflib
from rasterio.transform import rowcol
from pyaez import SoilConstraints
import rasterio 
from contextlib import closing
from enum import Enum
from engines.hwsd2_prop.hwsd_prop_generator import HWSDPropGenerator
from engines.report_augmentation.processing import LayerInterpolator, Output
from gaez_scripts.metadata.gaez_metadata_templates import CROP_REGISTRY
from engines.edaphic_crop_reqs.constants import CROPS_RAINFED_SPRINKLER, CROPS_GRAVITY_IRRIGATION, CROPS_DRIP_IRRIGATION


def get_crop_code(crop_name: str, map_code: str) -> str | None:
    """
    Returns the crop code for a given crop name and map code.
    Checks both the top-level crop and its subtypes.

    Args:
        crop_name: key in CROP_REGISTRY (e.g. "wheat", "barley")
        map_code:  resolution key (e.g. "RES02", "RES05")

    Returns:
        crop code string or None if not found
    """
    entry = CROP_REGISTRY.get(crop_name)
    if not entry:
        return None

    # Check top-level codes first
    code = entry.get("codes", {}).get(map_code)
    if code:
        return code

    # Check subtypes
    for subtype in entry.get("subtypes", {}).values():
        code = subtype.get("codes", {}).get(map_code)
        if code:
            return code

    return None

class InputLevel(Enum):
    LOW          = "low"
    INTERMEDIATE = "intermediate"
    HIGH         = "high"
  
class IrrigationType(Enum):
    DRIP = "drip"
    SPRINKLER = "sprinkler"
    GRAVITY = "gravity"
    
  
class WaterSupply(Enum):
    RAINFED = "rainfed"
    IRRIGATED = "irrigated"
    
class WaterSupplyIndex(Enum):
    RAINFED = "R"
    IRRIGATED = "I"

def get_agroclimatic_yield(input_level: InputLevel,
                           water_supply: WaterSupply,
                           crop_name: str,
                           coordinates: tuple[float, float]) -> float:
    tiff_db = "ardhi.db"
    conn = sqlite3.connect(tiff_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    crop_code = get_crop_code(crop_name, "RES02")  
    
    cursor.execute("""
        SELECT file_path FROM tiff_files 
        WHERE input_level = ? 
        AND water_supply = ? 
        AND crop_code = ? 
        AND map_code = ?""",
        (input_level.value, water_supply.value, crop_code, "RES02-YLD"))
    
    row = cursor.fetchone()
    tiff_path = row["file_path"].strip() if row else None
    
    lat, lon = coordinates
    with rasterio.open(tiff_path) as src:
        row, col = rowcol(src.transform, lon, lat)  # rowcol wants (xs, ys) = (lon, lat)
        value = src.read(1)[row, col]
    
    conn.close()

    return value

def get_smu_value(coord: tuple[float, float]):
    """
    Args:
        coord: (lat, lon)
    """
    lat, lon = coord
    with rasterio.open("hwsd_data/hwsd2_smu_tunisia.tif") as src:
        val = list(src.sample([(lon, lat)]))[0][0]
        if val == src.nodata:
            return None
        return val
    
def get_hwsd_soil_properties(smu_id: int, output_path: str):
    generator = HWSDPropGenerator(smu_id=smu_id, hwsd_db="hwsd.db")
    return generator.orchestrator(output_path)
    
def get_farmer_augmented_soil_properties(report,smu_id: int,output_path: str):
    interpolator = LayerInterpolator(hwsd_db="hwsd.db")
    group        = interpolator.layers_orchestrator(report, smu_id)
    interpolator.close()

    return Output().to_xlsx(group, output_path)
    

# Build once (outside function)
RAINFED_SPRINKLER_CROPS = {v["name"].lower() for v in CROPS_RAINFED_SPRINKLER.values()}
GRAVITY_IRRIGATED_CROPS = {v["name"].lower() for v in CROPS_GRAVITY_IRRIGATION.values()}
DRIP_IRRIGATED_CROPS = {v["name"].lower() for v in CROPS_DRIP_IRRIGATION.values()}


def normalize(name: str) -> str:
    return name.strip().lower()


def suggest(name: str, choices: set[str], n=3):
    return difflib.get_close_matches(name, choices, n=n, cutoff=0.5)


def validate_crop_name(
    crop_name: str,
    water_supply: WaterSupply,
    irrigation_type: IrrigationType = None
):
    name = normalize(crop_name)

    # Select correct crop set
    if water_supply == WaterSupply.RAINFED:
        valid_crops = RAINFED_SPRINKLER_CROPS
        context = "rainfed/sprinkler"

    elif water_supply == WaterSupply.IRRIGATED:
        if irrigation_type == IrrigationType.GRAVITY:
            valid_crops = GRAVITY_IRRIGATED_CROPS
            context = "gravity irrigation"
        elif irrigation_type == IrrigationType.SPRINKLER:
            valid_crops = RAINFED_SPRINKLER_CROPS
            context = "sprinkler irrigation"
        elif irrigation_type == IrrigationType.DRIP:
            valid_crops = DRIP_IRRIGATED_CROPS
            context = "drip irrigation"
        else:
            raise ValueError(f"Invalid irrigation type: {irrigation_type}")
    else:
        raise ValueError(f"Invalid water supply: {water_supply}")

    # Validate
    if name not in valid_crops:
        suggestions = suggest(name, valid_crops)
        if suggestions:
            raise ValueError(
                f"Invalid crop '{crop_name}' for {context}. "
                f"Did you mean: {', '.join(suggestions)}?"
            )
        else:
            raise ValueError(
                f"Invalid crop '{crop_name}' for {context}."
            )

    return name

def get_edaphic_paths(crop_name: str,
                      input_level: InputLevel,
                      water_supply: WaterSupply,
                      irrigation_type: IrrigationType = None) -> tuple[str, str]:
    with closing(sqlite3.connect("ardhi.db")) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        validated_crop_name = validate_crop_name(crop_name,water_supply, irrigation_type)
    
        #prepare the namings for the query
        # rainfed_sprinkler / irrigated_drip / irrigated_gravity
        
        cursor.execute("""
            SELECT file_path FROM edaphic_outputs 
            WHERE input_level = ? 
            AND water_supply = ? 
            AND crop_name = ? 
            """,
            (input_level.value, "rainfed_sprinkler", validated_crop_name))
        row = cursor.fetchone()
        rainfed_tiff_path = row["file_path"].strip() if row else None
        
        if water_supply == WaterSupply.RAINFED:
            return rainfed_tiff_path, rainfed_tiff_path
        else:
            if irrigation_type == IrrigationType.DRIP:
                irrigation_str = "irrigated_drip"
            elif irrigation_type == IrrigationType.SPRINKLER:
                irrigation_str = "irrigated_sprinkler"
            elif irrigation_type == IrrigationType.GRAVITY:
                irrigation_str = "irrigated_gravity"
            else:
                raise ValueError("Invalid irrigation type")
            
            cursor.execute("""
                SELECT file_path FROM edaphic_outputs 
                WHERE input_level = ? 
                AND water_supply = ? 
                AND crop_name = ?""" ,
                (input_level.value, irrigation_str, validated_crop_name))
            
            row = cursor.fetchone()
            irrigated_tiff_path = row["file_path"].strip() if row else None
        
            return rainfed_tiff_path, irrigated_tiff_path


def calculate_fc5():
    pass

def calculate_fc4_yield(
    edaphic_path_rainfed: str,
    edaphic_path_irrigated: str,
    soil_prop_path: str,
    water_supply: WaterSupply,
    soil_smu_id: int,
    yield_in: float,
):
    soil_constraints = SoilConstraints.SoilConstraints()

    # Importing the excel sheet of soil  
    soil_constraints.importSoilReductionSheet(edaphic_path_rainfed,edaphic_path_irrigated)

    ws_index = WaterSupplyIndex[water_supply.name].value  # "R" or "I"
    # Soil Qualities 
    soil_constraints.calculateSoilQualities(ws_index, soil_prop_path, soil_prop_path) 
    soil_constraints.calculateSoilRatings(ws_index) 

    # Extracting soil qualities 
    #soil_ratings = soil_constraints.getSoilRatings() 

    SOIL_SMU_ID = [[soil_smu_id]] #
    YIELD_IN = [[yield_in]] 

    # Soil Constraints 
    yield_out = soil_constraints.applySoilConstraints(SOIL_SMU_ID, YIELD_IN)

    return yield_out[0][0]

# Extract scalar from 2D array
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
    
def orchestrator(coord:tuple[float,float], crop_name: str, input_level: InputLevel, water_supply: WaterSupply, irrigation_type: IrrigationType = None,): #coord is (lat, lon)
    
    soil_smu_id = get_smu_value(coord)  # Example soil mapping unit ID
    edaphic_path_rainfed, edaphic_path_irrigated = get_edaphic_paths(crop_name, input_level, water_supply,irrigation_type)
    soil_prop_path = "engines/report_augmentation/results/output.xlsx"
    yield_in = get_agroclimatic_yield(input_level, water_supply, crop_name, coord)  # Example coordinates (longitude, latitude)
    
    fc4_yield= calculate_fc4_yield(
        edaphic_path_rainfed=edaphic_path_rainfed,
        edaphic_path_irrigated=edaphic_path_irrigated,
        soil_prop_path=soil_prop_path,
        water_supply=water_supply,
        soil_smu_id=soil_smu_id,
        yield_in=yield_in  # Example input yield
    )
    print(f"Final yield after applying soil constraints: {fc4_yield}")
    
    return fc4_yield
    
    
if __name__ == "__main__":
    coord = (36.858096, 9.962084)  # Example coordinates
    crop_name = "maize"
    input_level = InputLevel.HIGH
    water_supply = WaterSupply.RAINFED
    irrigation_type = None  # Not needed for rainfed
    
    orchestrator(coord, crop_name, input_level, water_supply, irrigation_type)