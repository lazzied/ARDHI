from abc import ABC
import json
from typing import Any, Dict
import sqlite3
from pathlib import Path                          # fix 5: was from zipfile

from engines.edaphic_crop_reqs.xlxs_merger import merge_csvs_to_xlsx
from engines.OCR_processing.report_augmentation.models_and_io import AugmentedLayer, AugmentedLayersGroup
from engines.OCR_processing.report_augmentation.vocabulary import CLASS_ATTRIBUTES, HWSD_MAPPER, NUM_ATTRIBUTES
import csv

def get_code_value(cursor, attribute: str, code) -> str | None:
    table = f"D_{attribute}"
    cursor.execute(f"SELECT VALUE FROM {table} WHERE CODE = ?", (code,))
    row = cursor.fetchone()
    return row["VALUE"] if row else None  # return first column for now

class AttributeStrategy(ABC):
    def __init__(self, report: str):
        # report is the json file path with attribute/value pairs
        with open(report, encoding="utf-8") as f:
            self.data = json.load(f)


class ReadStrategy(AttributeStrategy):
    def __init__(self, report: str):                   # fix 1: accept report
        super().__init__(report)                  # fix 1: call super
        self.read_attributes: dict[str, Any] = {}

    def get_attribute_value(self, attribute: str):
        for item in self.data:
            if item["attribute"] == attribute:
                return item["value"]
        return None

    def compute(self, attr):
        if attr == "OC":
            self.read_attributes["OC"] = self.get_attribute_value("Taux de carbone")
        if attr == "pH":
            self.read_attributes["pH"] = self.get_attribute_value("pH")
        if attr == "EC":
            self.read_attributes["EC"] = self.get_attribute_value("Conductivité")
        if attr == "CCB":
            self.read_attributes["CCB"] = self.get_attribute_value("Carbonates de Calcium")
        return self.read_attributes


class AugStrategy(AttributeStrategy):
    def __init__(self, hwsd_db: str, report: str, smu_id: int):
        super().__init__(report)
        self.augmented_attributes: dict[str, Any] = {}
        self.smu_id = smu_id
        self.conn = sqlite3.connect(hwsd_db)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def get_layers_value(self, attribute: str, fao_90_class:str, layer: str = "D1" ):
        self.cursor.execute(
            f"SELECT {attribute} FROM HWSD2_LAYERS WHERE HWSD2_SMU_ID = ? AND LAYER = ? AND FAO90 = ?",
            (self.smu_id, layer,fao_90_class)
        )
        row = self.cursor.fetchone()
        return row[attribute] if row else None

    def get_code_value(self, attribute, code):
        D_table_name = f"D_{attribute}"
        self.cursor.execute(
            f"SELECT code FROM {D_table_name} WHERE CODE = ?", (code,))
        row = self.cursor.fetchone()
        return row[code] if row else None

    def get_SMU_value(self, attribute: str, fao_90_class:str):
        self.cursor.execute(
            f"SELECT {attribute} FROM HWSD2_SMU WHERE HWSD2_SMU_ID = ? AND FAO90 = ? ", (self.smu_id,fao_90_class)
        )
        row = self.cursor.fetchone()
        return row[attribute] if row else None

    def close(self):
        self.conn.close()

    def compute(self, attr, fao_90_class):
        if attr == "TXT":
            code_val = get_code_value(self.cursor, "TEXTURE_USDA", self.get_layers_value("TEXTURE_USDA", fao_90_class))
            self.augmented_attributes["TXT"] = code_val.lower() if code_val else None
            print("TXT from hwsd:", self.augmented_attributes["TXT"])
        if attr == "DRG":
            self.augmented_attributes["DRG"] = self.get_layers_value("DRAINAGE", fao_90_class)
            print("DRG from hwsd:", self.augmented_attributes["DRG"])
        if attr == "OSD":
            val = self.get_SMU_value("ADD_PROP", fao_90_class)
            self.augmented_attributes["OSD"] = 1 if val == 2 else 0
        if attr in ("SPR", "VSP"):
            val = self.get_SMU_value("ADD_PROP", fao_90_class)
            self.augmented_attributes[attr] = 1 if val == 3 else 0  # fix: was hardcoded "OSD"
        if attr == "SPH":
            code_val = get_code_value(self.cursor, "PHASE", self.get_layers_value("PHASE1", fao_90_class))
            self.augmented_attributes["SPH"] = code_val.split(" ")[0] if code_val else "obstacle to roots no information"
            
        if attr == "RSD":
            code_val = get_code_value(self.cursor, "ROOT_DEPTH", self.get_layers_value("ROOT_DEPTH", fao_90_class))
            SOIL_DEPTH = {
                "Deep (> 100cm)": 150,
                "Moderately Deep (< 100cm)": 75,
                "Shallow (< 50cm)": 30,
                "Very Shallow (< 10cm)": 5,
            }
            self.augmented_attributes["RSD"] = SOIL_DEPTH.get(code_val, 100)
        if attr == "GYP":
            self.augmented_attributes["GYP"] = self.get_layers_value("GYPSUM", fao_90_class) 
        if attr == "GRC":
            self.augmented_attributes["GRC"] = self.get_layers_value("COARSE", fao_90_class)
        if attr == "CEC_CLAY":
            self.augmented_attributes["CEC_clay"] = self.get_layers_value("CEC_CLAY", fao_90_class)
        if attr == "CEC_SOIL":
            self.augmented_attributes["CEC_soil"] = self.get_layers_value("CEC_SOIL", fao_90_class)
        return self.augmented_attributes


class CalcStrategy(AugStrategy):
    def __init__(self, report: str, hwsd_db: str, smu_id: int):
        super().__init__(hwsd_db, report, smu_id)  # fix 2: correct order
        self.calculated_attributes: dict[str, Any] = {}

    def get_attribute_value(self, attribute: str):
        for item in self.data:
            if item["attribute"] == attribute:
                return item["value"]
        return None

    def compute_TEB(self, Ca: float, Mg: float, K: float, Na: float):  # fix 7: added self
        def to_cmolc(g_per_kg, atomic_mass, charge):
            return (g_per_kg * charge * 100) / atomic_mass
        ca = to_cmolc(Ca, atomic_mass=40.08, charge=2)
        mg = to_cmolc(Mg, atomic_mass=24.31, charge=2)
        k  = to_cmolc(K,  atomic_mass=39.10, charge=1)
        na = to_cmolc(Na, atomic_mass=22.99, charge=1)
        return round(ca + mg + k + na, 4), round(na, 4)

    def compute_BS(self, TEB: float, CEC_SOIL: float) -> float:       # fix 7: added self
        return round(min(100.0 * TEB / CEC_SOIL, 100.0), 4)

    def compute_ESP(self, Na_cmolc: float, CEC_SOIL: float) -> float:  # fix 7: added self
        return round(min(100.0 * Na_cmolc / CEC_SOIL, 100.0), 4)

    def compute(self, fao_90_class):
        ca       = self.get_attribute_value("Calcium échangeable")
        mg       = self.get_attribute_value("Magnésium échangeable")
        k        = self.get_attribute_value("Potassium échangeable")
        na       = self.get_attribute_value("Sodium échangeable")
        CEC_soil = self.get_layers_value("CEC_SOIL", fao_90_class)  
        print(f"[CalcStrategy.compute] smu_id={self.smu_id} "
          f"ca={ca} mg={mg} k={k} na={na} CEC_soil={CEC_soil}")# fix 6: was get_value

        teb, na_cmolc = self.compute_TEB(ca, mg, k, na)
        bs            = self.compute_BS(teb, CEC_soil)
        esp           = self.compute_ESP(na_cmolc, CEC_soil)

        self.calculated_attributes["TEB"] = teb
        self.calculated_attributes["BS"]  = bs
        self.calculated_attributes["ESP"] = esp
        return self.calculated_attributes


STRATEGIES: Dict[str, str] = {
    "OC": "READ", "pH": "READ", "EC": "READ", "CCB": "READ",
    "TXT": "AUG", "DRG": "AUG", "OSD": "AUG", "SPR": "AUG",
    "VSP": "AUG", "SPH": "AUG", "RSD": "AUG", "GYP": "AUG",
    "GRC": "AUG", "CEC_CLAY": "AUG", "CEC_SOIL": "AUG",
    "TEB": "CALC", "BS": "CALC", "ESP": "CALC",
}


def build_augmented_layer(report: str, hwsd_db: str, smu_id: int, fao_90_class: str) -> AugmentedLayer:
    attrs = list(STRATEGIES.keys())

    read_strat = ReadStrategy(report)
    aug_strat  = AugStrategy(hwsd_db, report, smu_id)
    calc_strat = CalcStrategy(report, hwsd_db, smu_id)

    calc_done = False
    for attr in attrs:
        strat = STRATEGIES[attr]
        if strat == "READ":
            read_strat.compute(attr)
        elif strat == "AUG":
            aug_strat.compute(attr, fao_90_class)
        elif strat == "CALC" and not calc_done:
            calc_strat.compute(fao_90_class)
            calc_done = True

    aug_strat.close()

    attributes_dict = read_strat.read_attributes | aug_strat.augmented_attributes | calc_strat.calculated_attributes  # fix 3: removed extra {}

    return AugmentedLayer(layer="D1", values=attributes_dict, smu_id=smu_id)


class LayerInterpolator:
    def __init__(self, hwsd_db: str):
        self.hwsd_db = hwsd_db
        self.conn = sqlite3.connect(hwsd_db)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def get_hwsd_layer(self, layer: str, smu_id: int, fao_90_class: str) -> AugmentedLayer:
        columns = ", ".join(HWSD_MAPPER.keys())
        self.cursor.execute(
            f"SELECT {columns} FROM HWSD2_LAYERS WHERE HWSD2_SMU_ID = ? AND LAYER = ? AND FAO90 = ?",
            (smu_id, layer, fao_90_class)
        )
        row = self.cursor.fetchone()
        if row is None:
            return None

        values = {}
        for hwsd_col, abbrv in HWSD_MAPPER.items():
            if hwsd_col == "ADD_PROP":
                val = row[hwsd_col]
                values["OSD"] = 1 if val == 2 else 0
                values["SPR"] = 1 if val == 3 else 0
                values["VSP"] = 1 if val == 3 else 0
                continue
            
            elif hwsd_col == "ROOT_DEPTH":
                code_val = get_code_value(self.cursor, "ROOT_DEPTH", row["ROOT_DEPTH"])
                SOIL_DEPTH = {
                    "Deep (> 100cm)": 150,
                    "Moderately Deep (< 100cm)": 75,
                    "Shallow (< 50cm)": 30,
                    "Very Shallow (< 10cm)": 5,
                }
                values["RSD"] = SOIL_DEPTH.get(code_val, 100)
                continue
            
            elif hwsd_col == "TEXTURE_USDA":
                code_val = get_code_value(self.cursor, "TEXTURE_USDA", row["TEXTURE_USDA"])
                values["TXT"] = code_val.lower() if code_val else None
                continue
            
            elif hwsd_col == "PHASE1":
                code_val = get_code_value(self.cursor, "PHASE", row["PHASE1"])  # use row directly
                values["SPH"] = code_val.split(" ")[0] if code_val else "obstacle to roots no information"
                continue  # ← also add this so it doesn't fall through to values[abbrv]

            values[abbrv] = row[hwsd_col]

        return AugmentedLayer(smu_id=smu_id, values=values, layer=layer)
    
    def close(self):
        self.conn.close()

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

    def build_augmented_layers(self, d1: AugmentedLayer, d2: AugmentedLayer, smu_id: int, fao_90_class: str) -> AugmentedLayersGroup:
        d3 = self.get_hwsd_layer("D3", smu_id, fao_90_class)   # fix 4: was self.smu_id
        d4 = self.get_hwsd_layer("D4", smu_id, fao_90_class)
        d5 = self.get_hwsd_layer("D5", smu_id, fao_90_class)
        d6 = self.get_hwsd_layer("D6", smu_id, fao_90_class)
        d7 = self.get_hwsd_layer("D7", smu_id, fao_90_class)
        return AugmentedLayersGroup([d1, d2, d3, d4, d5, d6, d7])

    def layers_orchestrator(self, report: str, smu_id: int, fao_90_class: str) -> AugmentedLayersGroup:
        d1      = build_augmented_layer(report, self.hwsd_db, smu_id, fao_90_class)
        d2_hwsd = self.get_hwsd_layer("D2", smu_id, fao_90_class)
        d2      = self.interpolate(d1, d2_hwsd)
        return self.build_augmented_layers(d1, d2, smu_id, fao_90_class)


class Output:
    def to_csv(self, layer: AugmentedLayer, output_path: str):
        fieldnames = ["CODE"] + list(layer.values.keys())
        row = {"CODE": layer.smu_id, **layer.values}
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(row)

    def to_xlsx(self, group: AugmentedLayersGroup, output_dir: str , filename: str):
        temp_folder = "temp_csvs"
        Path(temp_folder).mkdir(parents=True, exist_ok=True)
        for layer in group.layers:
            self.to_csv(layer, f"{temp_folder}/{layer.layer}.csv")
        merge_csvs_to_xlsx(folder=temp_folder, output_file=output_dir + f"/{filename}.xlsx")
        return output_dir + f"/{filename}.xlsx"


if __name__ == "__main__":
    report   = "engines/OCR_processing/report_augmentation/rapport_values.json"          # replace with your FarmerReport object
    hwsd_db  = "hwsd.db"     # replace with your .db path
    smu_id   = 31835          # replace with your SMU_ID
    fao_90_class = "Haplic Acrisols"  # replace with selected FAO-90 class for this SMU
    output   = "engines/report_augmentation/results" # replace with desired output directory
    filename = "report_augmented_layers"

    interpolator = LayerInterpolator(hwsd_db)
    group        = interpolator.layers_orchestrator(report, smu_id, fao_90_class)
    interpolator.close()

    Output().to_xlsx(group, output, filename)
    print(f"Done → {output}")