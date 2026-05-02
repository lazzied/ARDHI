import sqlite3

class HwsdRepository:
    
    def __init__(self,conn: sqlite3.Connection):
        conn.row_factory = sqlite3.Row
        self.conn = conn
        self.cursor = self.conn.cursor()
        
    
    def get_layer_attribute(self,smu_id, attribute: str, fao_90_class:str, layer: str = "D1" ):
        self.cursor.execute(
            f"SELECT {attribute} FROM HWSD2_LAYERS WHERE HWSD2_SMU_ID = ? AND LAYER = ? AND FAO90 = ?",
            (smu_id, layer, fao_90_class)
        )
        row = self.cursor.fetchone()
        return row[attribute] if row else None
    
    def get_layer_attributes(self,smu_id, attributes: list[str], fao_90_class: str, layer: str = "D1") -> dict | None:
        columns = ", ".join(attributes)
        self.cursor.execute(
            f"SELECT {columns} FROM HWSD2_LAYERS WHERE HWSD2_SMU_ID = ? AND LAYER = ? AND FAO90 = ?",
            (smu_id, layer, fao_90_class)
        )
        row = self.cursor.fetchone()
        return dict(zip(attributes, row)) if row else None
    
    
    def get_code_value(self, attribute, code):
        D_table_name = f"D_{attribute}"
        self.cursor.execute(
            f"SELECT VALUE FROM {D_table_name} WHERE CODE = ?", (code,))
        row = self.cursor.fetchone()
        return row[0] if row else None


    def get_SMU_attribute(self, attribute: str, fao_90_class:str):
        self.cursor.execute(
            f"SELECT {attribute} FROM HWSD2_SMU WHERE HWSD2_SMU_ID = ? AND FAO90 = ? ", (self.smu_id,fao_90_class)
        )
        row = self.cursor.fetchone()
        return row[attribute] if row else None
    
    
    def get_single_layer_attributes(
    self,
    columns: list,
    fao_90_class: str,
    layer: str,
    smu_id:str
    
    ) -> dict:
        cols_sql = ", ".join(columns)
        self.cursor.execute(
            f"SELECT {cols_sql} FROM HWSD2_LAYERS WHERE layer = ? AND FAO90 = ? AND HWSD2_SMU_ID = ?",
            (layer, fao_90_class, smu_id,),
        )
        row = self.cursor.fetchone()
        return dict(row) if row else {}
    
    def get_fao_90(self, smu_id):

        self.cursor.execute(
            """
            SELECT FAO90 FROM HWSD2_SMU
            WHERE HWSD2_SMU_ID = ?
            """,
            (smu_id,),
        )
        row = self.cursor.fetchone()
        return row["FAO90"].strip() if row else None
    
    def get_soter_texture_class(self, smu_id, fao_90 ):
        self.cursor.execute(
            """
            SELECT TEXTURE_SOTER FROM HWSD2_LAYERS
            WHERE HWSD2_SMU_ID = ? AND FAO90 = ? AND layer = ?
            """,
            (smu_id,fao_90,"D1",),
        )
        row = self.cursor.fetchone()
        return row["TEXTURE_SOTER"].strip() if row else None
    
    def debug_query(self, smu_id, fao_90_class, layer="D1"):
        # Check if the SMU ID exists at all
        self.cursor.execute("SELECT COUNT(*) FROM HWSD2_LAYERS WHERE HWSD2_SMU_ID = ?", (smu_id,))
        print("Rows with smu_id:", self.cursor.fetchone()[0])

        # Check if the layer exists
        self.cursor.execute("SELECT COUNT(*) FROM HWSD2_LAYERS WHERE HWSD2_SMU_ID = ? AND LAYER = ?", (smu_id, layer))
        print("Rows with smu_id + layer:", self.cursor.fetchone()[0])

        # Check if FAO90 matches
        self.cursor.execute("SELECT COUNT(*) FROM HWSD2_LAYERS WHERE HWSD2_SMU_ID = ? AND LAYER = ? AND FAO90 = ?", (smu_id, layer, fao_90_class))
        print("Rows with all 3 conditions:", self.cursor.fetchone()[0])

        # Show what FAO90 values actually exist for this smu_id
        self.cursor.execute("SELECT DISTINCT FAO90, LAYER FROM HWSD2_LAYERS WHERE HWSD2_SMU_ID = ?", (smu_id,))
        print("Actual FAO90/LAYER combos:", self.cursor.fetchall())