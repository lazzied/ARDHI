"""Report-based crop yield scorer that returns one yield record per crop."""
import logging

from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.connections import get_ardhi_connection, get_hwsd_connection
from ardhi.db.hwsd import HwsdRepository
from data_scripts.gaez_scripts.metadata.gaez_metadata_templates import CROP_REGISTRY
from engines.OCR_processing.models import InputLevel, IrrigationType, ScenarioConfig, WaterSupply
from engines.OCR_processing.yield_service.models import YIELD_LAYERS
from engines.OCR_processing.yield_service.yield_calc import YieldCalcOrchestrator
from engines.global_engines.yield_service.debug_print_yield import print_ranking_summary
from engines.global_engines.yield_service.models import CropYieldScore, RankingYield
from raster.tiff_operations import read_tiff_pixel


logger = logging.getLogger(__name__)


class ReportCropYield:
    def __init__(
        self,
        hwsd_repo: HwsdRepository,
        ardhi_repo: ArdhiRepository,
        input_level: InputLevel,
        water_supply: WaterSupply,
        irrigation_type: IrrigationType | None,
        coord: tuple,
    ):
        self.ardhi_repo = ardhi_repo
        self.hwsd_repo = hwsd_repo
        self.input_level = input_level
        self.water_supply = water_supply
        self.irrigation_type = irrigation_type
        self.coord = coord

        self.crop_names = self.build_crop_names()
        self.tiff_dict = {}
        self.build_tiff_dict()

    @staticmethod
    def build_crop_names() -> dict:
        names = {}
        for crop_key, crop in CROP_REGISTRY.items():
            caption = crop.get("caption", crop_key)
            res05_code = crop.get("codes", {}).get("RES05")
            if res05_code:
                names[res05_code] = caption
            for st_key, st in crop.get("subtypes", {}).items():
                st_code = st.get("codes", {}).get("RES05")
                if st_code:
                    names[st_code] = st.get("description", f"{caption} ({st_key})")
        return names

    def scenario_config_factory(self, crop_name: str) -> ScenarioConfig:
        return ScenarioConfig(crop_name, self.input_level, self.water_supply, self.irrigation_type)

    def build_tiff_dict(self) -> None:
        for key, map_code in YIELD_LAYERS.items():
            paths = self.ardhi_repo.get_crops_tiff_paths(map_code, self.input_level, self.water_supply)
            self.tiff_dict[key.lower()] = paths

    def build_crop_actual_yield(self, scenario: ScenarioConfig):
        orchestrator = YieldCalcOrchestrator(
            coord=self.coord,
            scenario=scenario,
            hwsd_repo=self.hwsd_repo,
            ardhi_repo=self.ardhi_repo,
        )
        return orchestrator.run()

    def build_crop_score(self, calculated_yield, crop_code: str) -> CropYieldScore | None:
        yxx_path = self.tiff_dict["yxx"].get(crop_code)
        if not yxx_path:
            logger.debug("Skipping %s due to missing yxx raster path", crop_code)
            return None

        potential_regional_yield = read_tiff_pixel(yxx_path.strip(), self.coord)
        return CropYieldScore(
            crop_code=crop_code,
            crop_name=self.crop_names[crop_code],
            input_level=self.input_level,
            water_supply=self.water_supply,
            actual_yield=int(calculated_yield),
            potential_regional_yield=int(potential_regional_yield),
        )

    def build_ranking_class(self) -> RankingYield:
        crop_scores = []
        for crop_code, crop_name in self.crop_names.items():
            scenario = self.scenario_config_factory(crop_name.lower())

            try:
                calculated_yield = self.build_crop_actual_yield(scenario)
            except ValueError as exc:
                logger.warning("Skipping %s (%s): %s", crop_name, crop_code, exc)
                continue
            except FileNotFoundError as exc:
                logger.warning("Skipping %s (%s) due to missing DB tiff path: %s", crop_name, crop_code, exc)
                continue

            score = self.build_crop_score(calculated_yield, crop_code)
            if score is not None:
                crop_scores.append(score)

        return RankingYield(scores=crop_scores)


if __name__ == "__main__":
    ardhi_conn = get_ardhi_connection()
    hwsd_conn = get_hwsd_connection()

    ardhi_repo = ArdhiRepository(ardhi_conn)
    hwsd_repo = HwsdRepository(hwsd_conn)

    crop_yield = ReportCropYield(
        hwsd_repo,
        ardhi_repo,
        InputLevel.HIGH,
        WaterSupply.RAINFED,
        None,
        (37.024050, 9.435166),
    )
    print_ranking_summary(crop_yield.build_ranking_class())
