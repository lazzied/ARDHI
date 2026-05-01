

from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.connections import get_ardhi_connection
from engines.OCR_processing.models import InputLevel, WaterSupply
from engines.global_engines.yield_service.models import YIELD_LAYERS, CropYieldScore, LayerDicts, RankingYield
from gaez_scripts.metadata.gaez_metadata_templates import CROP_REGISTRY
from raster.tiff_operations import read_tiff_pixel
from _debug_print_yield import print_ranking_summary


    
class CropYield:
    
    def __init__(self,
                 ardhi_repo: ArdhiRepository,
                 input_level:InputLevel,
                 water_supply:WaterSupply):
        
        self.ardhi_repo = ardhi_repo
        self.crop_names = self.build_crop_names()
        self.tiff_dict  =  self.build_tiff_dict()
        
        self.input_level = input_level
        self.water_supply = water_supply

    @staticmethod
    def build_crop_names() -> dict:
        """
        Build {RES05_crop_code: crop_name} from CROP_REGISTRY.
        {'ALF': 'Alfalfa', 'AVOC': 'Avocado', 'AVOST': 'Subtropical ecotype', 'AVOTH': 'Tropical highland',
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
    
    def build_tiff_dict(self)-> LayerDicts:
        for key , map_code in YIELD_LAYERS.items():
            dict = self.ardhi_repo.get_crops_tiff_paths(map_code,self.input_level,self.water_supply)
            self.tiff_dict[key.lower()] = dict
        
    
    def build_crop_score(
        self,
        crop_code: str,  
    ) -> CropYieldScore:

        crop_name = self.crop_names.get(crop_code)


        ylx_val = read_tiff_pixel(self.tiff_dict["ylx"].get(crop_code), self.coord[0], self.coord[1])
        yxx_val = read_tiff_pixel(self.tiff_dict["yxx"].get(crop_code), self.coord[0], self.coord[1])

        return CropYieldScore(
            crop_code=crop_code,
            crop_name=crop_name,
            input_level=self.input_level,
            water_supply = self.water_supply,
            actual_yield=int(ylx_val),
            potential_regional_yield=int(yxx_val),
            
        )
        
    def build_ranking_class(self) -> RankingYield:
        crop_scores =[]
        for crop_code in self.crop_names.keys():
            crop_scores.append(self.build_crop_score(crop_code))
        return RankingYield(scores = crop_scores)


if __name__ == "__main__":
    conn = get_ardhi_connection()
    ardhi_repo = ArdhiRepository(conn)
    input_level=InputLevel.HIGH
    water_supply=WaterSupply.RAINFED
    crop_yield = CropYield(ardhi_repo,
                           input_level
                           ,water_supply)
    
    ranking_yield = crop_yield.build_ranking_class()
    print_ranking_summary(ranking_yield)