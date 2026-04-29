import sqlite3
import difflib
import numpy as np
from rasterio.transform import rowcol
from pyaez import SoilConstraints
import rasterio
from contextlib import closing
from enum import Enum
from engines.hwsd2_prop.hwsd_prop_generator import HWSDPropGenerator
from engines.report_augmentation.processing import LayerInterpolator, Output
from gaez_scripts.metadata.gaez_metadata_templates import CROP_REGISTRY
from engines.edaphic_crop_reqs.constants import (
    CROPS_RAINFED_SPRINKLER,
    CROPS_GRAVITY_IRRIGATION,
    CROPS_DRIP_IRRIGATION,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ARDHI_DB = "ardhi.db"
HWSD_DB = "hwsd.db"
HWSD_SMU_TIFF = "hwsd_data/hwsd2_smu_tunisia.tif"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class InputLevel(Enum):
    LOW          = "low"
    INTERMEDIATE = "intermediate"
    HIGH         = "high"


class IrrigationType(Enum):
    DRIP      = "drip"
    SPRINKLER = "sprinkler"
    GRAVITY   = "gravity"


class WaterSupply(Enum):
    RAINFED   = "rainfed"
    IRRIGATED = "irrigated"


class WaterSupplyIndex(Enum):
    RAINFED   = "R"
    IRRIGATED = "I"


INPUT_LEVEL_TO_PYAEZ = {
    InputLevel.LOW:          "L",
    InputLevel.INTERMEDIATE: "I",
    InputLevel.HIGH:         "H",
}


# ---------------------------------------------------------------------------
# Crop registry helpers
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Crop-name validation
# ---------------------------------------------------------------------------
RAINFED_SPRINKLER_CROPS = {v["name"].lower() for v in CROPS_RAINFED_SPRINKLER.values()}
GRAVITY_IRRIGATED_CROPS = {v["name"].lower() for v in CROPS_GRAVITY_IRRIGATION.values()}
DRIP_IRRIGATED_CROPS    = {v["name"].lower() for v in CROPS_DRIP_IRRIGATION.values()}


def normalize(name: str) -> str:
    return name.strip().lower()


def suggest(name: str, choices: set[str], n: int = 3) -> list[str]:
    return difflib.get_close_matches(name, choices, n=n, cutoff=0.5)


def validate_crop_name(
    crop_name: str,
    water_supply: WaterSupply,
    irrigation_type: IrrigationType | None = None,
) -> str:
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

    if name not in valid_crops:
        suggestions = suggest(name, valid_crops)
        if suggestions:
            raise ValueError(
                f"Invalid crop '{crop_name}' for {context}. "
                f"Did you mean: {', '.join(suggestions)}?"
            )
        raise ValueError(f"Invalid crop '{crop_name}' for {context}.")

    return name


# ---------------------------------------------------------------------------
# Shared TIFF lookup + raster sampling
# ---------------------------------------------------------------------------
def _query_tiff_path(
    cursor: sqlite3.Cursor,
    *,
    input_level: InputLevel,
    water_supply: WaterSupply,
    crop_code: str,
    map_code: str,
) -> str | None:
    """Look up a tiff path in the `tiff_files` table."""
    cursor.execute(
        """
        SELECT file_path FROM tiff_files
        WHERE input_level = ?
          AND water_supply = ?
          AND crop_code = ?
          AND map_code = ?
        """,
        (input_level.value, water_supply.value, crop_code, map_code),
    )
    row = cursor.fetchone()
    return row["file_path"].strip() if row else None


def _sample_raster_at(tiff_path: str, coordinates: tuple[float, float]) -> float:
    """Sample the value of `tiff_path` at (lat, lon)."""
    if not tiff_path:
        raise FileNotFoundError("No TIFF path resolved for the given parameters.")

    lat, lon = coordinates
    with rasterio.open(tiff_path) as src:
        r, c = rowcol(src.transform, lon, lat)  # rowcol wants (xs, ys) = (lon, lat)
        return src.read(1)[r, c]


def _get_yield_from_map(
    input_level: InputLevel,
    water_supply: WaterSupply,
    crop_name: str,
    coordinates: tuple[float, float],
    *,
    crop_code_res: str,
    map_code: str,
) -> float:
    """
    Generic helper: resolve crop_code at `crop_code_res`, look up the matching
    raster in `tiff_files` for `map_code`, and sample it at `coordinates`.
    """
    crop_code = get_crop_code(crop_name, crop_code_res)

    with closing(sqlite3.connect(ARDHI_DB)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        tiff_path = _query_tiff_path(
            cursor,
            input_level=input_level,
            water_supply=water_supply,
            crop_code=crop_code,
            map_code=map_code,
        )

    return _sample_raster_at(tiff_path, coordinates)


def get_agroclimatic_yield(
    input_level: InputLevel,
    water_supply: WaterSupply,
    crop_name: str,
    coordinates: tuple[float, float],
) -> float:
    value = _get_yield_from_map(
        input_level, water_supply, crop_name, coordinates,
        crop_code_res="RES02", map_code="RES02-YLD",
    )
    print(f"[agroclimatic_yield] crop={crop_name} input={input_level.value} "
          f"ws={water_supply.value} coord={coordinates} -> {value}")
    return value


def get_full_constraints_yield(
    input_level: InputLevel,
    water_supply: WaterSupply,
    crop_name: str,
    coordinates: tuple[float, float],
) -> float:
    value = _get_yield_from_map(
        input_level, water_supply, crop_name, coordinates,
        crop_code_res="RES02", map_code="RES05-YLX30AS",
    )
    print(f"[full_constraints_yield] crop={crop_name} input={input_level.value} "
          f"ws={water_supply.value} coord={coordinates} -> {value}")
    return value


# ---------------------------------------------------------------------------
# Soil
# ---------------------------------------------------------------------------
def get_smu_value(coord: tuple[float, float]) -> int | None:
    """
    Args:
        coord: (lat, lon)
    """
    lat, lon = coord
    with rasterio.open(HWSD_SMU_TIFF) as src:
        val = list(src.sample([(lon, lat)]))[0][0]
        if val == src.nodata:
            print(f"[smu_value] coord={coord} -> nodata")
            return None
        val = int(val)
        print(f"[smu_value] coord={coord} -> {val}")
        return val


def get_hwsd_soil_properties(smu_id: int, output_path: str,filename: str) -> str:
    generator = HWSDPropGenerator(smu_id=smu_id, hwsd_db=HWSD_DB)
    return generator.orchestrator(output_path, filename)


def get_farmer_augmented_soil_properties(report, smu_id: int, output_path: str, filename: str) -> str:
    interpolator = LayerInterpolator(hwsd_db=HWSD_DB)
    group = interpolator.layers_orchestrator(report, smu_id)
    interpolator.close()

    return Output().to_xlsx(group, output_path,filename)


# ---------------------------------------------------------------------------
# Edaphic paths
# ---------------------------------------------------------------------------
_IRRIGATION_TO_DB_STR = {
    IrrigationType.DRIP:      "irrigated_drip",
    IrrigationType.SPRINKLER: "irrigated_sprinkler",
    IrrigationType.GRAVITY:   "irrigated_gravity",
}


def _query_edaphic_path(
    cursor: sqlite3.Cursor,
    *,
    input_level: InputLevel,
    water_supply_str: str,
    crop_name: str,
) -> str | None:
    cursor.execute(
        """
        SELECT file_path FROM edaphic_outputs
        WHERE input_level = ?
          AND water_supply = ?
          AND crop_name = ?
        """,
        (input_level.value, water_supply_str, crop_name),
    )
    row = cursor.fetchone()
    return row["file_path"].strip() if row else None


def get_edaphic_paths(
    crop_name: str,
    input_level: InputLevel,
    water_supply: WaterSupply,
    irrigation_type: IrrigationType | None = None,
) -> tuple[str, str]:
    validated_crop_name = validate_crop_name(crop_name, water_supply, irrigation_type)

    with closing(sqlite3.connect(ARDHI_DB)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # rainfed/sprinkler is always queried first
        rainfed_tiff_path = _query_edaphic_path(
            cursor,
            input_level=input_level,
            water_supply_str="rainfed_sprinkler",
            crop_name=validated_crop_name,
        )
        print(f"[edaphic_paths] rainfed/sprinkler -> {rainfed_tiff_path}")

        if water_supply == WaterSupply.RAINFED:
            return rainfed_tiff_path, rainfed_tiff_path

        if irrigation_type not in _IRRIGATION_TO_DB_STR:
            raise ValueError("Invalid irrigation type")

        irrigated_tiff_path = _query_edaphic_path(
            cursor,
            input_level=input_level,
            water_supply_str=_IRRIGATION_TO_DB_STR[irrigation_type],
            crop_name=validated_crop_name,
        )
        print(f"[edaphic_paths] {_IRRIGATION_TO_DB_STR[irrigation_type]} -> {irrigated_tiff_path}")

    return rainfed_tiff_path, irrigated_tiff_path


# ---------------------------------------------------------------------------
# FC4 / FC5
# ---------------------------------------------------------------------------
def calculate_fc4_yield(
    edaphic_path_rainfed:   str,
    edaphic_path_irrigated: str,
    soil_prop_path:         str,
    water_supply:           WaterSupply,
    input_level:            InputLevel,
    soil_smu_id:            int,
    yield_in:               float,
) -> float:
    print(f"[fc4_yield] importing edaphic sheets:")
    print(f"           rainfed   = {edaphic_path_rainfed}")
    print(f"           irrigated = {edaphic_path_irrigated}")
    print(f"           soil_prop = {soil_prop_path}")

    soil_constraints = SoilConstraints.SoilConstraints()
    soil_constraints.importSoilReductionSheet(edaphic_path_rainfed, edaphic_path_irrigated)

    ws_index = WaterSupplyIndex[water_supply.name].value   # "R" or "I"
    il_index = INPUT_LEVEL_TO_PYAEZ[input_level]           # "L", "I", or "H"
    print(f"[fc4_yield] ws_index={ws_index} il_index={il_index} smu={soil_smu_id} yield_in={yield_in}")

    soil_constraints.calculateSoilQualities(ws_index, soil_prop_path, soil_prop_path)
    soil_constraints.calculateSoilRatings(il_index)

    SOIL_SMU_ID = np.array([[soil_smu_id]], dtype=np.int64)
    YIELD_IN    = np.array([[yield_in]],    dtype=float)

    yield_out = soil_constraints.applySoilConstraints(SOIL_SMU_ID, YIELD_IN)
    result = float(yield_out[0, 0])
    print(f"[fc4_yield] yield_in={yield_in} -> yield_out={result}")
    return result


def fc4_yield_orchestrator(
    coord: tuple[float, float],   # (lat, lon)
    crop_name: str,
    input_level: InputLevel,
    water_supply: WaterSupply,
    soil_prop_path: str,
    irrigation_type: IrrigationType | None = None,
) -> float:
    print("\n" + "=" * 60)
    print(f"[fc4_orchestrator] crop={crop_name} input={input_level.value} "
          f"ws={water_supply.value} irr={irrigation_type} coord={coord}")
    print(f"[fc4_orchestrator] soil_prop_path={soil_prop_path}")
    print("=" * 60)

    soil_smu_id = get_smu_value(coord)
    if soil_smu_id is None:
        raise ValueError(f"No SMU value found at coordinates {coord} (nodata).")

    edaphic_path_rainfed, edaphic_path_irrigated = get_edaphic_paths(
        crop_name, input_level, water_supply, irrigation_type,
    )
    yield_in = get_agroclimatic_yield(input_level, water_supply, crop_name, coord)

    fc4_yield = calculate_fc4_yield(
        edaphic_path_rainfed=edaphic_path_rainfed,
        edaphic_path_irrigated=edaphic_path_irrigated,
        soil_prop_path=soil_prop_path,
        water_supply=water_supply,
        input_level=input_level,
        soil_smu_id=soil_smu_id,
        yield_in=yield_in,
    )
    print(f"[fc4_orchestrator] DONE -> fc4_yield={fc4_yield}")

    return fc4_yield


def calculate_fc5(
    input_level: InputLevel,
    water_supply: WaterSupply,
    crop_name: str,
    coordinates: tuple[float, float],
    hwsd_soil_prop_path: str,
    irrigation_type: IrrigationType | None = None,
) -> float | None:
    print("\n" + "=" * 60)
    print(f"[fc5] crop={crop_name} input={input_level.value} "
          f"ws={water_supply.value} irr={irrigation_type} coord={coordinates}")
    print(f"[fc5] hwsd_soil_prop_path={hwsd_soil_prop_path}")
    print("=" * 60)

    final_yield = get_full_constraints_yield(input_level, water_supply, crop_name, coordinates)
    fc4_yield = fc4_yield_orchestrator(
        coord=coordinates,
        crop_name=crop_name,
        input_level=input_level,
        water_supply=water_supply,
        soil_prop_path=hwsd_soil_prop_path,
        irrigation_type=irrigation_type,
    )
    fc5 = final_yield / fc4_yield if fc4_yield else None
    print(f"[fc5] full_constraints_yield={final_yield} / fc4_yield_hwsd={fc4_yield} -> fc5={fc5}")
    return fc5


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------
def main(
    input_level: InputLevel,
    water_supply: WaterSupply,
    crop_name: str,
    coord: tuple[float, float],
    report_soil_prop_path: str,
    hwsd_soil_prop_path: str,
    irrigation_type: IrrigationType | None = None,
) -> float:
    # Yatt = Ypot * (fc1*fc2*fc3*fc4) * fc5
    # First factor uses the soil-augmented (farmer report) properties.
    # fc5 uses HWSD soil properties.
    print("\n" + "#" * 70)
    print(f"# MAIN: crop={crop_name} input={input_level.value} "
          f"ws={water_supply.value} irr={irrigation_type}")
    print(f"# coord={coord}")
    print(f"# report_soil_prop_path={report_soil_prop_path}")
    print(f"# hwsd_soil_prop_path  ={hwsd_soil_prop_path}")
    print("#" * 70)

    print("\n>>> STEP 1: FC4 yield using FARMER-REPORT soil properties")
    fc4_yield = fc4_yield_orchestrator(
        coord=coord,
        crop_name=crop_name,
        input_level=input_level,
        water_supply=water_supply,
        soil_prop_path=report_soil_prop_path,
        irrigation_type=irrigation_type,
    )

    print("\n>>> STEP 2: FC5 (uses HWSD soil properties internally)")
    fc5 = calculate_fc5(
        input_level, water_supply, crop_name, coord,
        hwsd_soil_prop_path, irrigation_type,
    )

    print("\n>>> STEP 3: Final yield = fc4_yield_report * fc5")
    final_yield = fc4_yield * fc5
    print(f"    fc4_yield_report = {fc4_yield}")
    print(f"    fc5              = {fc5}")
    print(f"    final_yield      = {final_yield}")
    print("#" * 70 + "\n")
    return final_yield


if __name__ == "__main__":
    coord                 = (36.858096, 9.962084)
    crop_name             = "maize"
    input_level           = InputLevel.HIGH
    water_supply          = WaterSupply.RAINFED
    irrigation_type       = None  # Not needed for rainfed
    smu_id = get_smu_value(coord)
    
    report_json_path = "engines/report_augmentation/rapport_values.json"
    
    report_dir =  "engines/report_augmentation/results"
    hwsd_dir   = "engines/hwsd2_prop/results"
    report_soil_prop_path = get_farmer_augmented_soil_properties(report_json_path,smu_id,report_dir,"report_augmented_layers") # set as needed
    print(f"Report-augmented soil properties path: {report_soil_prop_path}")
    hwsd_soil_prop_path  = get_hwsd_soil_properties(smu_id,hwsd_dir,"hwsd_augmented_layers")         # set as needed
    print(f"HWSD soil properties path: {hwsd_soil_prop_path}")
    
    final_yield = main(
        input_level=input_level,
        water_supply=water_supply,
        crop_name=crop_name,
        coord=coord,
        report_soil_prop_path=report_soil_prop_path,
        hwsd_soil_prop_path=hwsd_soil_prop_path,
        irrigation_type=irrigation_type,
    )
    print(f"\n=== FINAL YIELD: {final_yield} ===")
