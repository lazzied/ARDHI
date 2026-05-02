
from ardhi.db.connections import close_connection, get_hwsd_connection
from ardhi.db.hwsd import HwsdRepository
from engines.OCR_processing.models import AugmentedLayer, AugmentedLayersGroup
from engines.soil_properties_builder.hwsd2_prop.constants import COLUMNS, SOIL_DEPTH
from engines.soil_properties_builder.output.output import Output


class HWSDPropGenerator:
    def __init__(self, smu_id: int, fao_90_class: str, hwsd_repo: HwsdRepository, output_dir: str, filename: str):
        self.smu_id       = smu_id
        self.fao_90_class = fao_90_class
        self.hwsd_repo    = hwsd_repo
        self.output_dir   = output_dir
        self.filename     = filename
        
    def apply_transformations(self, raw: dict) -> dict:
        result = {}

        result["DRG"]      = raw.get("DRAINAGE")
        result["GYP"]      = raw.get("GYPSUM")
        result["GRC"]      = raw.get("COARSE")
        result["CEC_clay"] = raw.get("CEC_CLAY")
        result["CEC_soil"] = raw.get("CEC_SOIL")
        result["OC"]       = raw.get("ORG_CARBON")
        result["pH"]       = raw.get("PH_WATER")
        result["EC"]       = raw.get("ELEC_COND")
        result["CCB"]      = raw.get("TCARBON_EQ")
        result["TEB"]      = raw.get("TEB")
        result["BS"]       = raw.get("BSAT")
        result["ESP"]      = raw.get("ESP")

        add_prop = raw.get("ADD_PROP")
        result["OSD"] = 1 if add_prop == 2 else 0
        result["SPR"] = 1 if add_prop == 3 else 0
        result["VSP"] = 1 if add_prop == 3 else 0
        
        code_val = self.hwsd_repo.get_code_value("TEXTURE_USDA", raw.get("TEXTURE_USDA"))
        result["TXT"] = code_val.lower() if code_val else None       
        
        code_val = self.hwsd_repo.get_code_value("PHASE", raw.get("PHASE1"))
        result["SPH"] = code_val.split(" ")[0] if code_val else "obstacle to roots no information"

        code_val = self.hwsd_repo.get_code_value("ROOT_DEPTH", raw.get("ROOT_DEPTH"))
        result["RSD"] = SOIL_DEPTH.get(code_val, 100)

        return result
    
    def compute(self, layer: str): # this is when you try to get a specific atribute
        
        raw_dict = self.hwsd_repo.get_single_layer_attributes(COLUMNS, self.fao_90_class, layer, self.smu_id)
        final_dict = self.apply_transformations(raw_dict)
        
        return AugmentedLayer(smu_id=self.smu_id, values=final_dict, layer=layer)
    
    
    def build_augmented_layers(self) -> AugmentedLayersGroup:
        
        results = {
            f"D{i}": self.compute(f"D{i}")
            for i in range(1, 8)
        }
        return AugmentedLayersGroup(list(results.values()))
    
    def build_range_augmented_layers(self, layer_range: tuple) -> AugmentedLayersGroup:
        
        results = {
            f"D{i}": self.compute(f"D{i}")
            for i in range(layer_range[0], layer_range[1] + 1)
        }
        return AugmentedLayersGroup(list(results.values()))
    
    def layers_orchestrator(self) -> str:
        
        group = self.build_augmented_layers()
        print(f"Group: {group}")
        return Output().to_xlsx(group, self.output_dir, self.filename)

if __name__ == "__main__":
    
    smu_id = 31802
    output_dir = "engines/soil_properties_builder/output/results/hwsd_results"
    filename = "hwsd_augmented_layers"

    conn = get_hwsd_connection()
    try:
        hwsd_repo = HwsdRepository(conn)
        fao_90_class = hwsd_repo.get_fao_90(smu_id)

        generator = HWSDPropGenerator(smu_id, fao_90_class, hwsd_repo, output_dir, filename)
        generator.layers_orchestrator()
    finally:
        close_connection(conn)