import os
import warnings
import logging
import rasterio
from rasterio.windows import Window

HWSD_SMU_TIFF = "hwsd_data/hwsd2_smu_tunisia.tif"
logger = logging.getLogger(__name__)

    
def get_smu_id_value(coord: tuple[float, float]) -> int | None:
    """
    Args:
        coord: (lat, lon)
    """
    lat, lon = coord
    with rasterio.open(HWSD_SMU_TIFF) as src:
        val = list(src.sample([(lon, lat)]))[0][0]
        if val == src.nodata:
            logger.debug("SMU lookup returned nodata for coord=%s", coord)
            return None
        val = int(val)
        logger.debug("Resolved SMU %s for coord=%s", val, coord)
        return val

def read_tiff_pixel(tiff_path: str, coordinates: tuple[float, float]) -> float:
    """
    Reads a single pixel value from a TIFF given Latitude and Longitude.
    Note: For Tunisia, lat is ~36.8 and lon is ~10.2.
    """
    lat = coordinates[0]
    lon= coordinates[1]
    
    try:
        # 1. Clean the path (removes trailing spaces/newlines)
        if not tiff_path:
            return 0.0
        clean_path = tiff_path.strip()

        # 2. Check if file actually exists before opening
        if not os.path.exists(clean_path):
            warnings.warn(f"File not found: {clean_path}")
            return 0.0

        with rasterio.open(clean_path) as src:
            # 3. Transform Lon/Lat to Pixel Row/Col
            # Rasterio index expects (x, y) which is (longitude, latitude)
            row, col = src.index(lon, lat)

            # 4. Bounds Check
            if row < 0 or col < 0 or row >= src.height or col >= src.width:
                warnings.warn(f"Out of Bounds: Lat {lat}, Lon {lon} is outside the image extent.")
                return 0.0

            # 5. Read the pixel
            window = Window(col, row, 1, 1)
            # Read first band
            val = src.read(1, window=window)[0, 0]

            # 6. NoData Handling
            if src.nodata is not None and val == src.nodata:
                return 0.0
            
            if val in [-9, -9999]: # Common GAEZ null values
                return 0.0

            return float(val)

    except Exception as e:
        warnings.warn(f"Error reading {tiff_path}: {str(e)}")
        return 0.0
