#getters / setters for tiff layers; db navigation; constants all of that;

import sqlite3
from contextlib import closing


ARDHI_DB ="ardhi.db"
class TiffDatabaseOperations:
    def __init__(self):
        
        pass
    
    def get_tiff_filepath():
        with closing(sqlite3.connect(ARDHI_DB)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
            """
            SELECT file_path FROM tiff_files
            WHERE input_level = ?
            AND water_supply = ?
            AND crop_code = ?
            AND map_code = ?
            """,
            (input_level.value, water_supply.value, crop_code, map_code),
        )
        row = cursor.fetchone()
        return row["file_path"].strip() if row else None