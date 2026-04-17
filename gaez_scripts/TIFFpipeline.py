import os
import time
import numpy as np
import rasterio
from rasterio.mask import mask
import geopandas as gpd
import requests
import base64
import google_crc32c

from gaez_scripts.tiff_layer import TiffLayer, from_url

class Downloader:
    @staticmethod
    def gs_to_https(gs_url: str) -> str:
        return gs_url.strip().replace("gs://", "https://storage.googleapis.com/")

    @staticmethod
    def get_filename(url: str) -> str:
        return os.path.basename(url)

    @staticmethod
    def download_file(url: str, output_folder: str) -> str:
        os.makedirs(output_folder, exist_ok=True)
        filename = Downloader.get_filename(url)
        dest = os.path.join(output_folder, filename)
        temp_file = dest + ".part"

        headers = {}
        if os.path.exists(temp_file):
            os.remove(temp_file) # Standard requests-based CRC validation works best on full downloads

        print(f"Downloading {filename}...")
        
        with requests.get(url, stream=True, timeout=(10, 60)) as r:
            if r.status_code != 200:
                raise Exception(f"Download failed with status code {r.status_code}")

            # 1. Extract the CRC32C from Google's headers
            # Format is usually: crc32c=XXXXXX==,md5=YYYYYY==
            remote_hash_header = r.headers.get("x-goog-hash", "")
            expected_crc32c = None
            for part in remote_hash_header.split(","):
                if part.startswith("crc32c="):
                    expected_crc32c = part.replace("crc32c=", "")

            # 2. Initialize the hasher
            hasher = google_crc32c.Checksum()

            with open(temp_file, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        hasher.update(chunk) # Update hash as we write

            # 3. Final Validation
            if expected_crc32c:
                # GCS provides base64 encoded big-endian CRC32C
                actual_crc32c = base64.b64encode(hasher.digest()).decode("utf-8")
                
                if actual_crc32c != expected_crc32c:
                    os.remove(temp_file)
                    raise ValueError(f"Integrity check failed! Expected {expected_crc32c}, got {actual_crc32c}")
                print("Integrity check passed.")
            else:
                print("Warning: No CRC32C header found. Skipping validation.")

        os.rename(temp_file, dest)
        print(f"Saved to {dest}")
        return dest

    @classmethod
    def download_url(cls, gs_url: str, output_folder: str) -> str:
        https_url = cls.gs_to_https(gs_url)
        return cls.download_file(https_url, output_folder)
    
class RasterData:
    def __init__(self, img: np.ma.MaskedArray, transform, gdf: gpd.GeoDataFrame):
        self.img = img
        self.transform = transform
        self.gdf = gdf


class RasterProcessor:

    def __init__(self, sigma: float = 1.5):
        self.sigma = sigma

    @staticmethod
    def load_shapefile(path: str) -> gpd.GeoDataFrame:
        return gpd.read_file(path)

    @staticmethod
    def reproject_to_match(gdf: gpd.GeoDataFrame, crs) -> gpd.GeoDataFrame:
        return gdf.to_crs(crs)

    @staticmethod
    def clip_raster(tiff_path: str, gdf: gpd.GeoDataFrame):
        with rasterio.open(tiff_path) as src:
            gdf = RasterProcessor.reproject_to_match(gdf, src.crs)
            out_image, out_transform = mask(src, gdf.geometry, crop=True)
            nodata = src.nodata
        return out_image[0], out_transform, nodata, gdf

    @staticmethod
    def save(data: RasterData, output_path: str, nodata: float = None) -> None:
        # Pick a nodata value compatible with the raster's dtype
        dtype = data.img.dtype
        if nodata is None:
            if np.issubdtype(dtype, np.unsignedinteger):
                nodata = np.iinfo(dtype).max        # e.g. 255 for uint8, 65535 for uint16
            elif np.issubdtype(dtype, np.signedinteger):
                nodata = np.iinfo(dtype).min        # e.g. -128 for int8, -9999 fits int16+
            else:
                nodata = -9999.0                    # float types

        with rasterio.open(
            output_path, "w",
            driver="GTiff",
            height=data.img.shape[0],
            width=data.img.shape[1],
            count=1,
            dtype=dtype,
            crs=data.gdf.crs,
            transform=data.transform,
            nodata=nodata,
        ) as dst:
            dst.write(data.img.filled(nodata), 1)

    @staticmethod
    def mask_nodata(img: np.ndarray, nodata) -> np.ma.MaskedArray:
        if nodata is not None:
            return np.ma.masked_where(img == nodata, img)
        return np.ma.array(img, mask=False)  # ← wrap as masked array with no mask

    def process(self, tiff_path: str, shapefile_path: str) -> RasterData:
        gdf = self.load_shapefile(shapefile_path)
        img, transform, nodata, gdf = self.clip_raster(tiff_path, gdf)
        img = self.mask_nodata(img, nodata)
        return RasterData(img=img, transform=transform, gdf=gdf)

if __name__ == "__main__":
    from ardhi_db import close_connection, get_connection, insert_layer

    SHAPEFILE     = "gaez_data/tunisia_Tunisia_Country_Boundary/tunisia_Tunisia_Country_Boundary.shp"
    OUTPUT_FOLDER = "D:/ARDHI/TIFF/clipped"
    TIFF_URLS     = "failed_urls.txt"
    MAX_RETRIES   = 3
    RETRY_DELAY   = 5

    raster_processor = RasterProcessor()
    conn = get_connection("ardhi.db")

    try:
        with open(TIFF_URLS) as f:
            for raw_url in f:
                url = raw_url.strip()
                if not url:
                    continue

                filename = Downloader.get_filename(
                    Downloader.gs_to_https(url)
                )
                existing_path = os.path.join(OUTPUT_FOLDER, filename)

                # If already clipped on disk, skip download+clip, just insert
                if os.path.exists(existing_path):
                    print(f"⊘ Already exists: {filename} — skipping to insert")
                    try:
                        layer = from_url(url, source="gaez")
                        layer.local_path = existing_path
                        issues = layer.validate()
                        if issues:
                            print(f"  ⚠ Validation warnings: {issues}")
                        insert_layer(conn, layer)
                        print(f"✓ Inserted: {filename}")
                    except Exception as e:
                        print(f"✗ Insert failed for {filename}: {e}")
                    continue

                # Otherwise: download, clip, insert
                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        path = Downloader.download_url(url, OUTPUT_FOLDER)
                        if not os.path.exists(path):
                            raise FileNotFoundError(f"File not found after download: {path}")

                        raster_data = raster_processor.process(path, SHAPEFILE)
                        raster_processor.save(raster_data, path)

                        layer = from_url(url, source="gaez")
                        layer.local_path = path
                        issues = layer.validate()
                        if issues:
                            print(f"  ⚠ Validation warnings for {layer.filename}: {issues}")
                        else:
                            print(f"✓ Layer created: {layer.filename}, now inserting to DB...")
                        try:
                            insert_layer(conn, layer)
                        except Exception as e:
                            print(f"✗ DB insertion error for {layer.filename}: {e}")
                        break

                    except FileNotFoundError as e:
                        print(f"✗ File error on attempt {attempt}/{MAX_RETRIES} for {url}: {e}")
                        if attempt < MAX_RETRIES:
                            print(f"  Retrying in {RETRY_DELAY}s...")
                            time.sleep(RETRY_DELAY)
                        else:
                            print(f"  Giving up on {url}")

                    except Exception as e:
                        print(f"✗ Attempt {attempt}/{MAX_RETRIES} failed for {url}: {e}")
                        if attempt < MAX_RETRIES:
                            print(f"  Retrying in {RETRY_DELAY}s...")
                            time.sleep(RETRY_DELAY)
                        else:
                            print(f"  Giving up on {url}")

    except FileNotFoundError as e:
        print(f"✗ Could not open URLs file: {e}")

    except Exception as e:
        print(f"✗ Unexpected error in main: {e}")

    finally:
        close_connection(conn)
        print("DB connection closed.")