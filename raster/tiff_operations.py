
from typing import Optional

import rasterio
from rasterio.transform import rowcol
from rasterio.windows import Window

HWSD_SMU_TIFF = "hwsd_data/hwsd2_smu_tunisia.tif"


def sample_raster_at(tiff_path: str, coordinates: tuple[float, float]) -> float:
    """Sample the value of `tiff_path` at (lat, lon)."""
    if not tiff_path:
        raise FileNotFoundError("No TIFF path resolved for the given parameters.")

    lat, lon = coordinates
    with rasterio.open(tiff_path) as src:
        r, c = rowcol(src.transform, lon, lat)  # rowcol wants (xs, ys) = (lon, lat)
        return src.read(1)[r, c]
    
def get_smu_id_value(coord: tuple[float, float]) -> int | None:
    """
    Args:
        coord: (lat, lon)
    """
    lat, lon = coord
    with rasterio.open(HWSD_SMU_TIFF) as src:
        val = list(src.sample([(lon, lat)]))[0][0]
        if val == src.nodata:
            print(f"[smu_value] coord={coord} -> nodata")
            return None
        val = int(val)
        print(f"[smu_value] coord={coord} -> {val}")
        return val

def read_tiff_pixel( tiff_path: str, lat: float, lon: float) -> Optional[float]:

        with rasterio.open(tiff_path) as src:
            row, col = src.index(lon, lat)

            if row < 0 or col < 0 or row >= src.height or col >= src.width:
                return None

            window = Window(col, row, 1, 1)
            val = src.read(1, window=window)[0, 0]

            if src.nodata is not None and val == src.nodata:
                return None
            if val == -9 or val == -9999:
                return None

            return float(val)
        return None