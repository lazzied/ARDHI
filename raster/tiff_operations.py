"""Raster utility functions for reading TIFF values and resolving SMU identifiers."""
import os
import warnings
import logging
import rasterio

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
    lat, lon = coordinates

    try:
        if not tiff_path:
            return 0.0

        clean_path = tiff_path.strip()

        if not os.path.exists(clean_path):
            warnings.warn(f"File not found: {clean_path}")
            return 0.0

        with rasterio.open(clean_path) as src:
            val = list(src.sample([(lon, lat)]))[0][0]

            if src.nodata is not None and val == src.nodata:
                return 0.0

            if val in [-9, -9999]:
                return 0.0

            return float(val)

    except Exception as e:
        warnings.warn(f"Error reading {tiff_path}: {str(e)}")
        return 0.0
    
    
if __name__ == "__main__":
    test_coord = (37.024050, 9.435166)
    tiff_path = "D:/ARDHI/TIFF/clipped/GAEZ-V5.RES02-YLD.HP0120.AGERA5.HIST.MAIZ.HRLM.tif"
    
    result = read_tiff_pixel(tiff_path, test_coord)
    print(f"read_tiff_pixel result: {result}")