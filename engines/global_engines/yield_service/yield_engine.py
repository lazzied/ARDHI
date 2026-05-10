"""Global raster-based crop-yield engine that builds per-crop yield scores."""
import logging

from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.connections import get_ardhi_connection
from data_scripts.gaez_scripts.metadata.gaez_metadata_templates import CROP_REGISTRY
from engines.OCR_processing.models import DRIP_IRRIGATED_CROPS, GRAVITY_IRRIGATED_CROPS, RAINFED_SPRINKLER_CROPS, InputLevel, IrrigationType, WaterSupply
from engines.global_engines.yield_service.debug_print_yield import print_ranking_summary
from engines.global_engines.yield_service.models import YIELD_LAYERS, CropYieldScore, RankingYield
from raster.tiff_operations import read_tiff_pixel


logger = logging.getLogger(__name__)


class CropYield:
    def __init__(
        self,
        ardhi_repo: ArdhiRepository,
        input_level: InputLevel,
        water_supply: WaterSupply,
        irrigation_type: IrrigationType | None,
        coord: tuple,
    ):
        self.ardhi_repo = ardhi_repo
        self.input_level = input_level
        self.water_supply = water_supply
        self.irrigation_type = irrigation_type
        self.coord = coord

        self.crop_names = self.build_crop_names(self.get_valid_crops())
        self.tiff_dict = {}
        self.build_tiff_dict()
        
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
    
    def build_tiff_dict(self) -> None:
        for key, map_code in YIELD_LAYERS.items():
            paths = self.ardhi_repo.get_crops_tiff_paths(
                map_code,
                self.input_level,
                self.water_supply,
                self.irrigation_type,
            )
            self.tiff_dict[key.lower()] = paths

    def build_crop_score(self, crop_code: str) -> CropYieldScore | None:
        ylx_path = self.tiff_dict["ylx"].get(crop_code)
        yxx_path = self.tiff_dict["yxx"].get(crop_code)

        if not ylx_path or not yxx_path:
            logger.debug("Skipping %s due to missing yield raster path", crop_code)
            return None

        crop_name = self.crop_names.get(crop_code)
        ylx_val = read_tiff_pixel(ylx_path.strip(), self.coord)
        yxx_val = read_tiff_pixel(yxx_path.strip(), self.coord)

        return CropYieldScore(
            crop_code=crop_code,
            crop_name=crop_name,
            input_level=self.input_level,
            water_supply=self.water_supply,
            actual_yield=int(ylx_val),
            regional_yield=int(yxx_val),
        )

    def build_ranking_class(self) -> RankingYield:
        crop_scores = []
        for crop_code in self.crop_names:
            score = self.build_crop_score(crop_code)
            if score is not None:
                crop_scores.append(score)
        return RankingYield(scores=crop_scores)


if __name__ == "__main__":
    conn = get_ardhi_connection()
    ardhi_repo = ArdhiRepository(conn)

    crop_yield = CropYield(
        ardhi_repo,
        input_level=InputLevel.HIGH,
        water_supply=WaterSupply.RAINFED,
        irrigation_type=None,
        coord=(37.024050, 9.435166),
    )

    ranking_yield = crop_yield.build_ranking_class()
    print_ranking_summary(ranking_yield,50)
