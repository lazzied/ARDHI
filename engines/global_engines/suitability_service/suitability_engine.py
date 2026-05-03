"""Global raster-based suitability engine that computes per-crop suitability scores."""
import logging

from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.connections import get_ardhi_connection
from data_scripts.gaez_scripts.metadata.gaez_metadata_templates import CROP_REGISTRY
from engines.OCR_processing.models import InputLevel, WaterSupply
from engines.global_engines.suitability_service.debug_print_suitability import print_suitability_ranking
from engines.global_engines.suitability_service.models import SUITABILITY_LAYERS, CropSuitabilityScore, RankingSuitability
from raster.tiff_operations import read_tiff_pixel

"""
Uses three suitability layers:
  - RES05-SXX30AS: continuous suitability index (0-10000) as the primary ranking metric
  - RES05-SIX30AS: suitability class index (1-9) as the human-readable class label
  - RES05-SX2: share of VS+S+MS land (0-10000, 10 km) as the regional overview
"""


logger = logging.getLogger(__name__)


class CropSuitability:
    def __init__(
        self,
        ardhi_repo: ArdhiRepository,
        input_level: InputLevel,
        water_supply: WaterSupply,
        coord: tuple,
    ):
        self.ardhi_repo = ardhi_repo
        self.input_level = input_level
        self.water_supply = water_supply
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

    def build_tiff_dict(self) -> None:
        for key, map_code in SUITABILITY_LAYERS.items():
            paths_dict = self.ardhi_repo.get_crops_tiff_paths(map_code, self.input_level, self.water_supply)
            self.tiff_dict[key.lower()] = paths_dict
        logger.debug("Loaded suitability raster maps for %s crop codes", len(self.crop_names))

    def build_crop_score(self, crop_code: str) -> CropSuitabilityScore | None:
        crop_name = self.crop_names.get(crop_code)
        sxx_path = self.tiff_dict["sxx"].get(crop_code)
        six_path = self.tiff_dict["six"].get(crop_code)
        sx2_path = self.tiff_dict["sx2"].get(crop_code)

        if not sxx_path or not six_path or not sx2_path:
            logger.debug("Skipping %s due to missing suitability raster path", crop_code)
            return None

        sxx_val = read_tiff_pixel(sxx_path.strip(), self.coord)
        six_val = read_tiff_pixel(six_path.strip(), self.coord)
        sx2_val = read_tiff_pixel(sx2_path.strip(), self.coord)

        return CropSuitabilityScore(
            crop_code=crop_code,
            crop_name=crop_name,
            input_level=self.input_level,
            water_supply=self.water_supply,
            suitability_index=int(sxx_val),
            suitability_class=int(six_val),
            regional_share=int(sx2_val),
        )

    def build_ranking_class(self) -> RankingSuitability:
        crop_scores = []
        for crop_code in self.crop_names:
            score = self.build_crop_score(crop_code)
            if score is not None:
                crop_scores.append(score)
        return RankingSuitability(scores=crop_scores)


if __name__ == "__main__":
    conn = get_ardhi_connection()
    ardhi_repo = ArdhiRepository(conn)
    input_level = InputLevel.HIGH
    water_supply = WaterSupply.RAINFED
    coord = (37.024050, 9.435166)

    crop_suitability = CropSuitability(
        ardhi_repo,
        input_level,
        water_supply,
        coord,
    )

    ranking_suitability = crop_suitability.build_ranking_class()
    print_suitability_ranking(ranking_suitability)
