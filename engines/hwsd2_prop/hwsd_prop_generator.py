import sqlite3
from typing import Any

from engines.report_augmentation.models_and_io import AugmentedLayer, AugmentedLayersGroup
from engines.report_augmentation.processing import Output, get_code_value
from engines.report_augmentation.vocabulary import HWSD_MAPPER

class HWSDPropGenerator:
    def __init__(self, smu_id: int, hwsd_db: str):
        self.smu_id = smu_id
        self.conn = sqlite3.connect(hwsd_db)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        
        self.hwsd_attributes = dict[str, Any] = {}

    def get_layers_value(self, attribute: str, layer: str = "D1"):
        self.cursor.execute(
            f"SELECT {attribute} FROM HWSD2_LAYERS WHERE HWSD2_SMU_ID = ? AND LAYER = ?",
            (self.smu_id, layer)
        )
        row = self.cursor.fetchone()
        return row[attribute] if row else None

    def get_code_value(self, attribute, code):
        D_table_name = f"D_{attribute}"
        self.cursor.execute(
            f"SELECT code FROM {D_table_name} WHERE CODE = ?", (code,))
        row = self.cursor.fetchone()
        return row[code] if row else None

    def get_SMU_value(self, attribute: str):
        self.cursor.execute(
            f"SELECT {attribute} FROM HWSD2_SMU WHERE HWSD2_SMU_ID = ?", (self.smu_id,)
        )
        row = self.cursor.fetchone()
        return row[attribute] if row else None

    def close(self):
        self.conn.close()
        
    def compute(self, attr): # this is when you try to get a specific atribute
        if attr == "TXT":
            self.hwsd_attributes["TXT"] = self.get_layers_value("TEXTURE_USDA")
        if attr == "DRG":
            self.hwsd_attributes["DRG"] = self.get_layers_value("DRAINAGE")
        if attr == "OSD":
            val = self.get_SMU_value("ADD_PROP")
            self.hwsd_attributes["OSD"] = 1 if val == 2 else 0
        if attr in ("SPR", "VSP"):
            val = self.get_SMU_value("ADD_PROP")
            self.hwsd_attributes[attr] = 1 if val == 3 else 0  # fix: was hardcoded "OSD"
        if attr == "SPH":
            code_val = self.get_code_value(self.cursor, "WRB_PHASES", self.get_layers_value("WRB_PHASES"))
            self.hwsd_attributes["SPH"] = code_val.split(" ")[0] if code_val else None
        if attr == "RSD":
            code_val = self.get_code_value(self.cursor, "ROOT_DEPTH", self.get_layers_value("ROOT_DEPTH"))
            SOIL_DEPTH = {
                "Deep (> 100cm)": 150,
                "Moderately Deep (< 100cm)": 75,
                "Shallow (< 50cm)": 30,
                "Very Shallow (< 10cm)": 5,
            }
            self.hwsd_attributes["RSD"] = SOIL_DEPTH.get(code_val, None)
        if attr == "GYP":
            self.hwsd_attributes["GYP"] = self.get_layers_value("GYPSUM")
        if attr == "GRC":
            self.hwsd_attributes["GRC"] = self.get_layers_value("COARSE")
        if attr == "CEC_CLAY":
            self.hwsd_attributes["CEC_CLAY"] = self.get_layers_value("CEC_CLAY")
        if attr == "CEC_SOIL":
            self.hwsd_attributes["CEC_SOIL"] = self.get_layers_value("CEC_SOIL")
        if attr == "OC":
            self.hwsd_attributes["OC"] = self.get_layers_value("ORG_CARBON")
        if attr == "pH":
            self.hwsd_attributes["pH"] = self.get_layers_value("PH_WATER")
        if attr == "EC":
            self.hwsd_attributes["EC"] = self.get_layers_value("ELEC_COND")
        if attr == "CCB":
            self.hwsd_attributes["CCB"] = self.get_layers_value("TCARBON_EQ")
        if attr == "TEB":
            self.hwsd_attributes["TEB"] = self.get_layers_value("TEB")
        if attr == "BS":
            self.hwsd_attributes["BS"] = self.get_layers_value("BSAT")
        if attr == "ESP":
            self.hwsd_attributes["ESP"] = self.get_layers_value("ESP")
        return self.hwsd_attributes
    
    def get_hwsd_layer(self, layer: str, smu_id: int) -> AugmentedLayer:
        columns = ", ".join(HWSD_MAPPER.keys())
        self.cursor.execute(
            f"SELECT {columns} FROM HWSD2_LAYERS WHERE HWSD2_SMU_ID = ? AND LAYER = ?",
            (smu_id, layer)
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
            elif hwsd_col == "WRB_PHASES":
                code_val = get_code_value(self.cursor, "WRB_PHASES", row["WRB_PHASES"])  # use row directly
                values["SPH"] = code_val.split(" ")[0] if code_val else None
                continue  # ← also add this so it doesn't fall through to values[abbrv]

            values[abbrv] = row[hwsd_col]

        return AugmentedLayer(smu_id=smu_id, values=values, layer=layer)
    
    def build_augmented_layers(self, smu_id: int) -> AugmentedLayersGroup:
            d1 = self.get_hwsd_layer("D1", smu_id)   
            d2 = self.get_hwsd_layer("D2", smu_id)
            d3 = self.get_hwsd_layer("D3", smu_id) 
            d4 = self.get_hwsd_layer("D4", smu_id)
            d5 = self.get_hwsd_layer("D5", smu_id)
            d6 = self.get_hwsd_layer("D6", smu_id)
            d7 = self.get_hwsd_layer("D7", smu_id)
            
            return AugmentedLayersGroup([d1, d2, d3, d4, d5, d6, d7])
        
    def orchestrator(self, output_path: str) -> AugmentedLayersGroup:
        try:
            group = self.build_augmented_layers(self.smu_id)
            return Output().to_xlsx(group, output_path)
        finally:
            self.close()    