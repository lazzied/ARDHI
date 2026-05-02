import sqlite3
from engines.OCR_processing.models import InputLevel, Texture, pH_level, WaterSupply

class ArdhiRepository:
    def __init__(self, conn: sqlite3.Connection):
        conn.row_factory = sqlite3.Row  # ← add this

        self.conn = conn
        self.cursor = self.conn.cursor()

    def get_crops_tiff_paths(self, map_code: str, input_level: InputLevel, water_supply:WaterSupply ) -> dict[str, str]:
        rows = self.conn.execute(
            "SELECT crop_code, file_path FROM tiff_files "
            "WHERE map_code = ? AND input_level = ? AND water_supply = ?",
            (map_code, input_level.value, water_supply.value)
        ).fetchall()
        return {row["crop_code"]: row["file_path"] for row in rows}
    
    def query_tiff_path(
        self,
        input_level: InputLevel,
        water_supply: WaterSupply,
        crop_code: str,
        map_code: str,
            ) -> str | None:
        
        self.cursor.execute(
            """
            SELECT file_path FROM tiff_files
            WHERE input_level = ?
            AND water_supply = ?
            AND crop_code = ?
            AND map_code = ?
            """,
            (input_level.value, water_supply.value, crop_code, map_code),
        )
        row = self.cursor.fetchone()
        return row["file_path"].strip() if row else None
    
    def calendar_query_tiff_path(self, crop_code: str, map_code: str, water_supply, input_level) -> str | None:
        """Look up a tiff path in the `tiff_files` table."""
        self.cursor.execute(
            """
            SELECT file_path FROM tiff_files
            WHERE crop_code = ?
            AND map_code = ?
            AND water_supply= ?
            AND input_level = ?
            """,
            (crop_code, map_code,water_supply.value,input_level.value),
        )
        
        row = self.cursor.fetchone()
        return row["file_path"].strip() if row else None
    

    
    """
    def get_available_crops(self, input_level: InputLevel, water_supply: WaterSupply) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT crop_code FROM tiff_files "
            "WHERE map_code = ? AND input_level = ? AND crop_code IS NOT NULL",
            (self.SUITABILITY_LAYERS["SXX"], input_level)
        ).fetchall()
        return [row["crop_code"] for row in rows]
    """
    def query_edaphic_path(
        self,
        input_level: InputLevel,
        water_supply_str: str,
        crop_name: str,
        ph_level: pH_level,
        texture_class: Texture,
        
        
        ) -> str | None:
            self.cursor.execute(
                """
                SELECT file_path FROM edaphic_outputs
                WHERE input_level = ?
                AND water_supply = ?
                AND crop_name = ?
                AND ph_level = ?
                AND texture_class = ?
            
                """,
                (input_level.value, water_supply_str, crop_name,ph_level.value,texture_class.value),
            )
            row = self.cursor.fetchone()
            return row["file_path"].strip() if row else None