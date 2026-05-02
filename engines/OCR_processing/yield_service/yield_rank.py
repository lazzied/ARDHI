from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.connections import get_ardhi_connection
from engines.OCR_processing.models import InputLevel, ScenarioConfig, SiteContext, Texture, WaterSupply, pH_level
from engines.OCR_processing.yield_service.models import YIELD_LAYERS
from engines.OCR_processing.yield_service.yield_calc import run_yield_pipeline
from engines.global_engines.yield_service.debug_print_yield import print_ranking_summary
from engines.global_engines.yield_service.models import CropYieldScore, RankingYield
from data_scripts.gaez_scripts.metadata.gaez_metadata_templates import CROP_REGISTRY
from raster.tiff_operations import get_smu_id_value, read_tiff_pixel


class ReportCropYield:

    def __init__(
        self,
        report_soil_path: str,
        hwsd_soil_path: str,
        ardhi_repo: ArdhiRepository,
        input_level: InputLevel,
        water_supply: WaterSupply,
        ph_level: pH_level,
        texture_class: Texture,
        coord: tuple,                        # Fix 3: added missing coord parameter
    ):
        self.report_soil_path = report_soil_path
        self.hwsd_soil_path = hwsd_soil_path
        self.ardhi_repo = ardhi_repo
        
        self.input_level = input_level
        self.water_supply = water_supply
        self.ph_level = ph_level
        self.texture_class = texture_class
        self.coord = coord                   # Fix 3: store coord

        self.crop_names = self.build_crop_names()
        self.tiff_dict = {}                  # Fix 1: initialize before calling build_tiff_dict
        self.build_tiff_dict()               # Fix 1: mutates in place, don't assign return value

    @staticmethod
    def build_crop_names() -> dict:
        """
        Build {RES05_crop_code: crop_name} from CROP_REGISTRY.
        {'ALF': 'Alfalfa', 'AVOC': 'Avocado', 'AVOST': 'Subtropical ecotype', ...}
        """
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
    
    def scenario_and_context_factory(self,crop_name):
        
        smu_id = get_smu_id_value(self.coord)
        scenario = ScenarioConfig(crop_name,self.input_level,self.water_supply)
        site = SiteContext(self.coord,self.ph_level,self.texture_class,smu_id)
        
        return scenario, site 
    
    def build_tiff_dict(self) -> None:       # Fix 1: return type is None, mutates self.tiff_dict
        for key, map_code in YIELD_LAYERS.items():
            paths = self.ardhi_repo.get_crops_tiff_paths(map_code, self.input_level, self.water_supply)
            self.tiff_dict[key.lower()] = paths

    def build_crop_actual_yield(self, scenario: ScenarioConfig, site: SiteContext):
        
        calculated_yield = run_yield_pipeline(
            ardhi_repo=self.ardhi_repo,
            scenario=scenario,
            site=site,
            report_soil_path=self.report_soil_path,   # Fix 2: was self.report_soil_prop_path
            hwsd_soil_path=self.hwsd_soil_path         # Fix 2: was self.hwsd_soil_prop_path
        )
        return calculated_yield

    def build_crop_score(
        self,
        calculated_yield,                    # Fix 4: kept as explicit argument
        crop_code: str,
    ) -> CropYieldScore | None:

        # Fix 5: guard against missing tiff path
        yxx_path = self.tiff_dict["yxx"].get(crop_code)
        if not yxx_path:
            print(f"[SKIP] Missing yxx tiff path for crop: {crop_code}")
            return None

        potential_regional_yield = read_tiff_pixel(yxx_path.strip(), self.coord[0], self.coord[1])

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

            scenario, site = self.scenario_and_context_factory(crop_name.lower())

            try:
                calculated_yield = self.build_crop_actual_yield(scenario, site)
            except ValueError as e:
                print(f"[SKIP] {crop_name} ({crop_code}): {e}")
                continue
            except FileNotFoundError as e:
                print(f"[SKIP] {crop_name} ({crop_code}): no tiff path in DB -> {e}")
                continue

            score = self.build_crop_score(calculated_yield, crop_code)
            if score is not None:
                crop_scores.append(score)

        return RankingYield(scores=crop_scores)
    
        
if __name__ == "__main__":
    
    conn = get_ardhi_connection()
    ardhi_repo = ArdhiRepository(conn)
    input_level=InputLevel.HIGH
    water_supply=WaterSupply.RAINFED
    ph_level=pH_level.BASIC
    texture_class=Texture.MEDIUM
    
    
    hwsd_soil_path = "engines/soil_properties_builder/output/results/hwsd_results/hwsd_soil.xlsx"
    report_soil_path = "engines/soil_properties_builder/output/results/report_results/report_soil.xlsx"
    
    coord = (37.024050, 9.435166) 

    crop_yield = ReportCropYield(report_soil_path,
                                 hwsd_soil_path,
                                 ardhi_repo,
                                 input_level,
                                 water_supply,
                                 ph_level,
                                 texture_class,
                                 coord)
    
    ranking_yield = crop_yield.build_ranking_class()
    
    print_ranking_summary(ranking_yield)
        
    
    

        
        
        
        