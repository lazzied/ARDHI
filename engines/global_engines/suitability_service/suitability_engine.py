
from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.connections import get_ardhi_connection
from engines.OCR_processing.models import InputLevel, WaterSupply
from engines.global_engines.suitability_service.models import SUITABILITY_LAYERS, CropSuitabilityScore, LayerDicts, RankingSuitability
from gaez_scripts.metadata.gaez_metadata_templates import CROP_REGISTRY
from raster.tiff_operations import read_tiff_pixel

"""
Uses three suitability layers:
  - RES05-SXX30AS: continuous suitability index (0-10000) → primary ranking metric
  - RES05-SIX30AS: suitability class index (1-9) → human-readable class label
  - RES05-SX2:     share of VS+S+MS land (0-10000, 10km) → regional overview

"""

class CropSuitability:
    
    def __init__(self,
                 ardhi_repo: ArdhiRepository,
                 crop_registry: dict,
                 input_level:InputLevel,
                 water_supply:WaterSupply):
        
        self.ardhi_repo = ardhi_repo
        self.crop_names = self.build_crop_names(crop_registry)
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
        for key , map_code in SUITABILITY_LAYERS.items():
            dict = self.ardhi_repo.get_crops_tiff_paths(map_code,self.input_level,self.water_supply)
            self.tiff_dict[key.lower()] = dict
        
    
    def build_crop_score(
        self,
        crop_code: str,
        
    ) -> CropSuitabilityScore:
        
        crop_name = self.crop_names.get(crop_code)

        six_val = read_tiff_pixel(self.tiff_dict["six"].get(crop_code), self.coord[0], self.coord[1])
        sx2_val = read_tiff_pixel(self.tiff_dict["sx2"].get(crop_code), self.coord[0], self.coord[1])
        sxx_val = read_tiff_pixel(self.tiff_dict["sxx"].get(crop_code), self.coord[0], self.coord[1])

        return CropSuitabilityScore(
            crop_code=crop_code,
            crop_name=crop_name,
            input_level=self.input_level,
            water_supply = self.water_supply,
            
            suitability_index=int(sxx_val),
            suitability_class=int(six_val),
            regional_share=int(sx2_val),      
        )
        
    def build_ranking_class(self) -> RankingSuitability:
        crop_scores= []
        for code_crop in self.crop_names.keys():
            crop_scores.append(self.build_crop_score(code_crop))
        return RankingSuitability(scores = crop_scores)

if __name__ == "__main__":
    conn = get_ardhi_connection()
    ardhi_repo = ArdhiRepository(conn)
    input_level=InputLevel.HIGH
    water_supply=WaterSupply.RAINFED
    crop_suitability = CropSuitability(ardhi_repo,
                           input_level
                           ,water_supply)
    
    ranking_suitability = crop_suitability.build_ranking_class()
