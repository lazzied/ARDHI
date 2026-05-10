"""Report-based crop yield scorer that returns one yield record per crop."""
import logging
import logging.handlers
from pathlib import Path

from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.connections import get_ardhi_connection, get_hwsd_connection
from ardhi.db.hwsd import HwsdRepository
from data_scripts.gaez_scripts.metadata.gaez_metadata_templates import CROP_REGISTRY
from engines.OCR_processing.models import DRIP_IRRIGATED_CROPS, GRAVITY_IRRIGATED_CROPS, RAINFED_SPRINKLER_CROPS, InputLevel, IrrigationType, ScenarioConfig, WaterSupply
from engines.OCR_processing.yield_service.models import YIELD_LAYERS
from engines.OCR_processing.yield_service.yield_calc import YieldCalcOrchestrator
from engines.global_engines.yield_service.debug_print_yield import print_ranking_summary
from engines.global_engines.yield_service.models import CropYieldScore, RankingYield
from raster.tiff_operations import read_tiff_pixel


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Debug file logger
# ---------------------------------------------------------------------------
_debug_logger = logging.getLogger("report_crop_yield.debug")
_debug_logger.setLevel(logging.DEBUG)
_debug_logger.propagate = False

_log_path = Path(__file__).parent / "report_crop_yield_debug.log"
_fh = logging.FileHandler(_log_path, mode="w", encoding="utf-8")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S"))
_debug_logger.addHandler(_fh)


class ReportCropYield:
    def __init__(
        self,
        hwsd_repo: HwsdRepository,
        ardhi_repo: ArdhiRepository,
        input_level: InputLevel,
        water_supply: WaterSupply,
        irrigation_type: IrrigationType | None,
        coord: tuple,
        paths
    ):
        self.ardhi_repo = ardhi_repo
        self.hwsd_repo = hwsd_repo
        self.input_level = input_level
        self.water_supply = water_supply
        self.irrigation_type = irrigation_type
        self.coord = coord
        self.paths = paths
        self.crop_names = self.build_crop_names(self.get_valid_crops())
        self.tiff_dict = {}
        self.build_tiff_dict()

        _debug_logger.debug(
            "ReportCropYield init | coord=%s  input_level=%s  water_supply=%s  irrigation=%s",
            coord, input_level, water_supply, irrigation_type,
        )
        _debug_logger.debug("Crops loaded: %d  → %s", len(self.crop_names), list(self.crop_names.values()))
        _debug_logger.debug("Tiff dict keys: %s", list(self.tiff_dict.keys()))
        
    def get_valid_crops(self) -> set[str]:
        if self.water_supply == WaterSupply.RAINFED:
            return RAINFED_SPRINKLER_CROPS
        elif self.water_supply == WaterSupply.IRRIGATED:
            if self.irrigation_type == IrrigationType.SPRINKLER:
                return RAINFED_SPRINKLER_CROPS
            elif self.irrigation_type == IrrigationType.GRAVITY:
                return GRAVITY_IRRIGATED_CROPS
            elif self.irrigation_type == IrrigationType.DRIP:
                return DRIP_IRRIGATED_CROPS
        raise ValueError(f"Unhandled water_supply={self.water_supply}, irrigation_type={self.irrigation_type}")

    @staticmethod
    def build_crop_names(valid_crops: set[str]) -> dict:
        names = {}
        for crop_key, crop in CROP_REGISTRY.items():
            pyaez_name = crop.get("pyaez_name") or crop.get("caption", crop_key).lower()
            res05_code = crop.get("codes", {}).get("RES05")

            if res05_code and pyaez_name in valid_crops:
                names[res05_code] = pyaez_name

            for st_key, st in crop.get("subtypes", {}).items():
                st_pyaez = st.get("pyaez_name") or st.get("description", f"{pyaez_name} ({st_key})").lower()
                st_code = st.get("codes", {}).get("RES05")
                if st_code and st_pyaez in valid_crops:
                    names[st_code] = st_pyaez

        return names

    def scenario_config_factory(self, crop_name: str) -> ScenarioConfig:
        return ScenarioConfig(crop_name, self.input_level, self.water_supply, self.irrigation_type)

    def build_tiff_dict(self) -> None:
        for key, map_code in YIELD_LAYERS.items():
            paths = self.ardhi_repo.get_crops_tiff_paths(map_code, self.input_level, self.water_supply)
            self.tiff_dict[key.lower()] = paths

    def build_crop_actual_yield(self, scenario: ScenarioConfig):
        # --- DEBUG SKIP ---
        if scenario.crop_name.lower() == "gram":
            _debug_logger.debug("Skipping gram before orchestrator init (known missing SPH_val)")
            raise ValueError("gram skipped — known missing SPH_val in edaphic table")
        # --- END DEBUG SKIP ---
        
        orchestrator = YieldCalcOrchestrator(
            coord=self.coord,
            scenario=scenario,
            hwsd_repo=self.hwsd_repo,
            ardhi_repo=self.ardhi_repo,
        )
        
        orchestrator.paths = self.paths
        return orchestrator.run()

    def build_crop_score(self, calculated_yield, crop_code: str) -> CropYieldScore | None:
        yxx_path = self.tiff_dict["yxx"].get(crop_code)
        if not yxx_path:
            _debug_logger.debug("build_crop_score | %s — no yxx path, skipping", crop_code)
            logger.debug("Skipping %s due to missing yxx raster path", crop_code)
            return None

        potential_regional_yield = read_tiff_pixel(yxx_path.strip(), self.coord)
        _debug_logger.debug(
            "build_crop_score | %-20s  calculated=%s  potential_regional=%s",
            crop_code, calculated_yield, potential_regional_yield,
        )
        return CropYieldScore(
            crop_code=crop_code,
            crop_name=self.crop_names[crop_code],
            input_level=self.input_level,
            water_supply=self.water_supply,
            actual_yield=int(calculated_yield),
            regional_yield=int(potential_regional_yield),
        )

    def build_ranking_class(self) -> RankingYield:
        crop_scores = []
        _debug_logger.debug("--- build_ranking_class START (%d crops) ---", len(self.crop_names))

        for crop_code, crop_name in self.crop_names.items():
            print(crop_name)
            if crop_name.lower() == "gram" or crop_name.lower() ==  "maize silage":
                _debug_logger.debug("Skipping gram (known missing SPH_val)")
                continue
            scenario = self.scenario_config_factory(crop_name.lower())

            try:
                calculated_yield = self.build_crop_actual_yield(scenario)
                _debug_logger.debug("yield OK  | %-20s  yield=%s", crop_name, calculated_yield)
            except ValueError as exc:
                _debug_logger.debug("yield SKIP (ValueError)  | %-20s  %s", crop_name, exc)
                logger.warning("Skipping %s (%s): %s", crop_name, crop_code, exc)
                continue
            except FileNotFoundError as exc:
                _debug_logger.debug("yield SKIP (FileNotFoundError)  | %-20s  %s", crop_name, exc)
                logger.warning("Skipping %s (%s) due to missing DB tiff path: %s", crop_name, crop_code, exc)
                continue

            score = self.build_crop_score(calculated_yield, crop_code)
            if score is not None:
                crop_scores.append(score)

        _debug_logger.debug("--- build_ranking_class END | %d scores collected ---", len(crop_scores))
        return RankingYield(scores=crop_scores)


if __name__ == "__main__":
    ardhi_conn = get_ardhi_connection()
    hwsd_conn = get_hwsd_connection()

    ardhi_repo = ArdhiRepository(ardhi_conn)
    hwsd_repo = HwsdRepository(hwsd_conn)

    paths = {
            "report_input": "engines/soil_properties_builder/report_augmentation/input/rapport_values.json",
            "hwsd_out": "engines/soil_properties_builder/output/results/hwsd_results",
            "report_out": "engines/soil_properties_builder/output/results/report_results"
        }
    
    crop_yield = ReportCropYield(
        hwsd_repo,
        ardhi_repo,
        InputLevel.LOW,
        WaterSupply.RAINFED,
        None,
        (36.08, 10.25),
        paths
    )
    print_ranking_summary(crop_yield.build_ranking_class())