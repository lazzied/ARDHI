import rasterio
from rasterio.mask import mask
import geopandas as gpd
import rasterio
import numpy as np

SHAPEFILE = "gaez_data/tunisia_Tunisia_Country_Boundary/tunisia_Tunisia_Country_Boundary.shp"
INPUT = "hwsd_data/HWSD2.bil"
OUTPUT = "hwsd_data/hwsd2_smu_tunisia.tif"

def clip_to_tunisia():
    gdf = gpd.read_file(SHAPEFILE)

    with rasterio.open(INPUT) as src:
        gdf = gdf.to_crs(src.crs)
        out_image, out_transform = mask(src, gdf.geometry, crop=True)

        profile = src.profile.copy()
        profile.update(
            driver="GTiff",
            compress="lzw",
            height=out_image.shape[1],
            width=out_image.shape[2],
            transform=out_transform,
        )

        with rasterio.open(OUTPUT, "w", **profile) as dst:
            dst.write(out_image)

    print(f"Done: {OUTPUT}")

def filter_SMU(file_path):
    with rasterio.open(file_path) as src:  # your clipped file
        data = src.read(1)
        nodata = src.nodata or 65535
        smu_ids = sorted(set(int(v) for v in np.unique(data) if v != nodata and v > 0))

    print(f"Found {len(smu_ids)} unique SMU IDs in Tunisia")
    print(smu_ids)
    
if __name__ == "__main__":
    CLIPPED_TUNISIA= "hwsd_data/hwsd2_smu_tunisia.tif"
    filter_SMU(CLIPPED_TUNISIA)