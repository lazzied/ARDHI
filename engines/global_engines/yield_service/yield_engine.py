from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.connections import get_ardhi_connection
from engines.OCR_processing.models import InputLevel, WaterSupply
from engines.global_engines.yield_service.models import YIELD_LAYERS, CropYieldScore, LayerDicts, RankingYield
from data_scripts.gaez_scripts.metadata.gaez_metadata_templates import CROP_REGISTRY
from raster.tiff_operations import read_tiff_pixel
from engines.global_engines.yield_service.debug_print_yield import print_ranking_summary


class CropYield:

    def __init__(self,
                 ardhi_repo: ArdhiRepository,
                 input_level: InputLevel,
                 water_supply: WaterSupply,
                 coord: tuple):          # ← Bug 1: coord was missing from __init__

        self.ardhi_repo = ardhi_repo
        self.input_level = input_level   # ← Bug 2: must be set BEFORE build_tiff_dict
        self.water_supply = water_supply #           (build_tiff_dict uses them)
        self.coord = coord

        self.crop_names = self.build_crop_names()
        self.tiff_dict = {}              # ← Bug 3: must init dict BEFORE calling build_tiff_dict
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

    def build_tiff_dict(self) -> None:   # ← Bug 4: return type was LayerDicts but nothing returned
        for key, map_code in YIELD_LAYERS.items():
            paths = self.ardhi_repo.get_crops_tiff_paths(map_code, self.input_level, self.water_supply)
            self.tiff_dict[key.lower()] = paths

    def build_crop_score(self, crop_code: str) -> CropYieldScore | None:
        # Guard: check both layers have a path for this crop
        ylx_path = self.tiff_dict["ylx"].get(crop_code)
        yxx_path = self.tiff_dict["yxx"].get(crop_code)

        if not ylx_path or not yxx_path:
            print(f"[SKIP] Missing tiff path for crop: {crop_code}")
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
            potential_regional_yield=int(yxx_val),
        )

    def build_ranking_class(self) -> RankingYield:
        crop_scores = []
        for crop_code in self.crop_names.keys():
            score = self.build_crop_score(crop_code)
            if score is not None:        # ← filter out skipped crops
                crop_scores.append(score)
        return RankingYield(scores=crop_scores)


if __name__ == "__main__":
    conn = get_ardhi_connection()
    ardhi_repo = ArdhiRepository(conn)

    crop_yield = CropYield(
        ardhi_repo,
        input_level=InputLevel.HIGH,
        water_supply=WaterSupply.RAINFED,
        coord=(37.024050, 9.435166),        # ← (lat, lon) Tunis
    )

    ranking_yield = crop_yield.build_ranking_class()
    print_ranking_summary(ranking_yield)