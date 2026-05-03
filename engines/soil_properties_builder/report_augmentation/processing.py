"""Core report-augmentation logic that mixes lab report values with HWSD-derived properties."""
import json
from typing import Any, Dict
from ardhi.db.connections import close_connection, get_hwsd_connection
from ardhi.db.hwsd import HwsdRepository
from engines.OCR_processing.models import AugmentedLayer, AugmentedLayersGroup, pH_level
from engines.soil_properties_builder.hwsd2_prop.hwsd_prop_generator import HWSDPropGenerator
from engines.soil_properties_builder.output.output import Output
from engines.soil_properties_builder.report_augmentation.constants import CLASS_ATTRIBUTES, HWSD_COLUMNS,  NUM_ATTRIBUTES, REPORT_MAP, SOIL_DEPTH


class ReportOperations():
    def __init__(self, report: str | list[dict] | dict):
        # report can be a json file path or already-parsed attribute/value data.
        if isinstance(report, str):
            with open(report, encoding="utf-8") as f:
                self.data = json.load(f)
        elif isinstance(report, dict):
            self.data = report.get("lab_report", report.get("data", []))
        else:
            self.data = report
        
    def get_attribute_value(self, attribute: str):
        for item in self.data:
            if item["attribute"] == attribute:
                return item["value"]
        return None
    
    def get_report_ph_class(self)-> pH_level:
        ph_value = float(self.get_attribute_value("pH"))
        return pH_level.BASIC if ph_value > 7 else pH_level.ACIDIC


class ReadStrategy():
    def __init__(self, report_operations: ReportOperations):
        self.report_operations = report_operations

    def compute(self) -> dict:
        return {
            attr: self.report_operations.get_attribute_value(REPORT_MAP[attr])
            for attr in REPORT_MAP
        }


class AugStrategy():
    def __init__(self, hwsd_repo: HwsdRepository, smu_id: int):
        self.smu_id = smu_id
        self.hwsd_repo = hwsd_repo

    def apply_transformations(self, raw: dict) -> dict:
        result = {}

        result["DRG"]      = raw.get("DRAINAGE")
        result["GYP"]      = raw.get("GYPSUM")
        result["GRC"]      = raw.get("COARSE")
        result["CEC_clay"] = raw.get("CEC_CLAY")
        result["CEC_soil"] = raw.get("CEC_SOIL")

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
    
    def compute(self, fao_90_class,smu_id):
        raw_dict = self.hwsd_repo.get_single_layer_attributes(HWSD_COLUMNS, fao_90_class,"D1", smu_id)
        return self.apply_transformations(raw_dict)


class CalcStrategy():
    def __init__(self, report_operations: ReportOperations, hwsd_repo: HwsdRepository, smu_id:int):
        self.report_operations = report_operations
        self.hwsd_repo = hwsd_repo
        self.smu_id = smu_id


    
    def compute_TEB(self, Ca: float, Mg: float, K: float, Na: float):
        
        def to_cmolc(g_per_kg, atomic_mass, charge):
            return (g_per_kg * charge * 100) / atomic_mass
        
        ca = to_cmolc(float(Ca), atomic_mass=40.08, charge=2)
        mg = to_cmolc(float(Mg), atomic_mass=24.31, charge=2)
        k  = to_cmolc(float(K),  atomic_mass=39.10, charge=1)
        na = to_cmolc(float(Na), atomic_mass=22.99, charge=1)
        
        return round(ca + mg + k + na, 4), round(na, 4)

    def compute_BS(self, TEB: float, CEC_SOIL: float) -> float:
        if not CEC_SOIL:
            return 0.0
        return round(min(100.0 * TEB / CEC_SOIL, 100.0), 4)

    def compute_ESP(self, Na_cmolc: float, CEC_SOIL: float) -> float:
        if not CEC_SOIL:
            return 0.0
        return round(min(100.0 * Na_cmolc / CEC_SOIL, 100.0), 4)

    def compute(self, fao_90_class):
        
        ca       = self.report_operations.get_attribute_value("Calcium échangeable")
        mg       = self.report_operations.get_attribute_value("Magnésium échangeable")
        k        = self.report_operations.get_attribute_value("Potassium échangeable")
        na       = self.report_operations.get_attribute_value("Sodium échangeable")
        
        CEC_soil = self.hwsd_repo.get_layer_attribute(self.smu_id,"CEC_SOIL", fao_90_class, "D1")
        
        print(f"[CalcStrategy.compute] smu_id={self.smu_id} "
              f"ca={ca} mg={mg} k={k} na={na} CEC_soil={CEC_soil}")

        teb, na_cmolc = self.compute_TEB(ca, mg, k, na)

        return {
            "TEB": teb,
            "BS":  self.compute_BS(teb, CEC_soil),
            "ESP": self.compute_ESP(na_cmolc, CEC_soil),
        }
        

class ReportPropGenerator:
    def __init__(self, smu_id, fao_90_class, report_ops, hwsd_repo, hwsd_prop_generator: HWSDPropGenerator, output_dir,filename):
        self.smu_id              = smu_id
        self.fao_90_class        = fao_90_class
        self.report_ops          = report_ops
        self.hwsd_repo           = hwsd_repo
        self.hwsd_prop_generator = hwsd_prop_generator
        self.output_dir          = output_dir
        self.filename            = filename
        
    def interpolate(self, d1: AugmentedLayer, d2_hwsd: AugmentedLayer) -> AugmentedLayer:
        
        values: Dict[str, Any] = {}
        for attr in NUM_ATTRIBUTES:
            v1 = d1.values.get(attr)
            v2 = d2_hwsd.values.get(attr)
            if attr in CLASS_ATTRIBUTES:
                values[attr] = v2 if v2 is not None else v1
                continue
            if v1 is not None and v2 is not None:
                values[attr] = round(0.5 * float(v1) + 0.5 * float(v2), 4)
            elif v2 is not None:
                values[attr] = float(v2)
            elif v1 is not None:
                values[attr] = float(v1)
            else: 
                values[attr] = None
                
        return AugmentedLayer("D2", values, d2_hwsd.smu_id)

    def build_D1_augmented_layer(self) -> AugmentedLayer:
        
        aug_strategy = AugStrategy(self.hwsd_repo, self.smu_id)
        read_strategy = ReadStrategy(self.report_ops)
        calc_strategy = CalcStrategy(self.report_ops, self.hwsd_repo,self.smu_id)
        
        aug_attributes = aug_strategy.compute(self.fao_90_class, self.smu_id)
        read_attributes = read_strategy.compute()
        print("read_attrs:",read_attributes)
        calc_attributes = calc_strategy.compute(self.fao_90_class)
        
        full_attributes = aug_attributes | read_attributes | calc_attributes
        
        
        return AugmentedLayer("D1", full_attributes, self.smu_id)

    def build_augmented_layers(
        self,
        d1: AugmentedLayer | None = None,
        d2: AugmentedLayer | None = None,
    ) -> AugmentedLayersGroup:
            if d1 is None:
                d1 = self.build_D1_augmented_layer()
            if d2 is None:
                d2_hwsd = self.hwsd_prop_generator.compute("D2")
                d2 = self.interpolate(d1, d2_hwsd)
            
            d3_to_d7_group = self.hwsd_prop_generator.build_range_augmented_layers((3, 7))
            d3_to_d7_layers = d3_to_d7_group.layers
            
            return AugmentedLayersGroup([d1, d2] + d3_to_d7_layers)


    def layers_orchestrator(self) -> str:
            group = self.build_augmented_layers()
            return Output().to_xlsx(group, self.output_dir, self.filename)

   
if __name__ == "__main__":
    report       = "engines/soil_properties_builder/report_augmentation/input/rapport_values.json"
    hwsd_db      = "hwsd.db"
    smu_id       = 31835
    output       = "engines/soil_properties_builder/output/results/report_results"
    filename     = "report_soil"
    
    conn = get_hwsd_connection()
    try:
        hwsd_repo           = HwsdRepository(conn)
        fao_90_class = hwsd_repo.get_fao_90(smu_id)
        hwsd_repo.debug_query(smu_id, fao_90_class)

        report_ops          = ReportOperations(report)
        hwsd_prop_generator = HWSDPropGenerator(smu_id,fao_90_class, hwsd_repo,output,filename)
        
        report_prop_generator = ReportPropGenerator(
            smu_id              = smu_id,
            fao_90_class        = fao_90_class,
            report_ops          = report_ops,
            hwsd_repo           = hwsd_repo,
            hwsd_prop_generator = hwsd_prop_generator,
            output_dir          = output,
            filename            = filename,
        )
        output_path = report_prop_generator.layers_orchestrator()
        print("output_path", output_path)
        
    finally:
        close_connection(conn)
    
    print(f"Done → {output}")
"""Core report-augmentation logic that mixes lab report values with HWSD-derived properties."""
