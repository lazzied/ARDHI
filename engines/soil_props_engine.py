import rasterio
import sqlite3

RASTER_PATH = "hwsd_data/hwsd2_smu_tunisia.tif"
DB_PATH= "hwsd.db"

class HWSDLookup:
    def __init__(self, raster_path: str, db_path: str):
        self.src = rasterio.open(raster_path)  # hwsd2.bil or hwsd2.tif
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def get_smu(self, lat: float, lon: float) -> int:
        """Raster pixel at (lat, lon) → SMU ID."""
        row, col = self.src.index(lon, lat)
        # Read just one pixel, not the whole raster
        window = rasterio.windows.Window(col, row, 1, 1)
        smu_id = self.src.read(1, window=window)[0, 0]
        return int(smu_id)

    def get_properties(self, smu_id: int) -> list[dict]:
        """All soil layers for this mapping unit."""
        rows = self.conn.execute(
            "SELECT * FROM HWSD2_LAYERS WHERE HWSD2_SMU_ID = ?",
            (smu_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_dominant_soil(self, smu_id: int) -> dict:
        """Just the dominant soil unit info."""
        row = self.conn.execute(
            "SELECT * FROM HWSD2_SMU WHERE HWSD2_SMU_ID = ?",
            (smu_id,)
        ).fetchone()
        return dict(row) if row else {}

    def lookup(self, lat: float, lon: float) -> dict:
        """Full lookup: coordinate → SMU → all properties."""
        smu_id = self.get_smu(lat, lon)
        return {
            "smu_id": smu_id,
            "dominant": self.get_dominant_soil(smu_id),
            "layers": self.get_properties(smu_id),
        }

    def close(self):
        self.src.close()
        self.conn.close()