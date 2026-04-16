import rasterio
from pyproj import Transformer
from owslib.wcs import WebCoverageService
from dataclasses import dataclass
from pathlib import Path
from soil_grid_scripts.dicts import CRS, DATA_DIR, DEPTHS, SCALE_FACTORS, SOIL_PROPERTIES, TUNISIA_SUBSETS
import matplotlib.pyplot as plt
from rasterio import plot
import rasterio
from pyproj import Transformer

def plt_wcs_coverage(path, wgs_coords=None, title="title", annotate=True):
    with rasterio.open(path) as coverage:
        fig, ax = plt.subplots()
        plot.show(coverage, ax=ax, title=title, cmap='gist_ncar')

        if wgs_coords:
            lat, lon = wgs_coords  # your current call passes (lat, lon)
            # Reproject to the raster's CRS
            transformer = Transformer.from_crs("EPSG:4326", coverage.crs, always_xy=True)
            x, y = transformer.transform(lon, lat)  # note: always_xy means (lon, lat) → (x, y)
            
            ax.plot(x, y, marker='+', markersize=15, markeredgewidth=2, color='red')

            if annotate:
                value = list(coverage.sample([(x, y)]))[0][0]
                ax.text(x, y, f"{value:.2f}", fontsize=10, color='white',
                        bbox=dict(facecolor='black', alpha=0.5, pad=2))

        plt.show()
        
@dataclass
class SoilPoint:
    """Soil properties at a single geographic point, across all depths."""
    lat: float
    lon: float
    properties: dict  # { "phh2o_0-5cm": 6.8, "clay_0-5cm": 22.3, ... }

    def __str__(self):
        lines = [f"Soil properties at ({self.lat}, {self.lon}):"]
        for key, value in self.properties.items():
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)




class SoilGridsDownloader:
    """Downloads SoilGrids rasters for a given region and saves them locally."""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def download_property(self, prop_name: str, depths: list = DEPTHS):
        """Download all depth layers for a single soil property."""
        url = SOIL_PROPERTIES.get(prop_name)
        if not url:
            raise ValueError(f"Unknown property: {prop_name}. Choose from {list(SOIL_PROPERTIES.keys())}")

        print(f"\nConnecting to {prop_name}...")
        wcs = WebCoverageService(url, version='2.0.1')

        for depth in depths:
            cov_id = f"{prop_name}_{depth}_mean"
            out_path = self.data_dir / f"{cov_id}.tif"

            if out_path.exists():
                print(f"  Already exists: {cov_id} — skipping")
                continue

            if cov_id not in wcs.contents:
                print(f"  Not found: {cov_id} — skipping")
                continue

            print(f"  Downloading {cov_id}...")
            try:
                cov = wcs.contents[cov_id]
                response = wcs.getCoverage(
                    identifier=cov_id,
                    crs=CRS,
                    subsets=TUNISIA_SUBSETS,
                    resx=250, resy=250,
                    format=cov.supportedFormats[0]
                )
                with open(out_path, 'wb') as f:
                    f.write(response.read())
                print(f"  Saved: {out_path}")
            except Exception as e:
                print(f"  Failed {cov_id}: {e}")

    def download_all(self):
        """Download all soil properties and depths."""
        for prop_name in SOIL_PROPERTIES:
            self.download_property(prop_name)
        print("\nAll downloads complete.")


class SoilQuery:
    """Query soil properties from locally stored rasters."""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.transformer = Transformer.from_crs("EPSG:4326", "ESRI:54052", always_xy=True)

    def _to_xy(self, lat, lon):
        return self.transformer.transform(lon, lat)

    def _sample(self, raster_path, projected_coords):
        coverage = rasterio.open(raster_path)
        proj_x, proj_y = projected_coords
        value = list(coverage.sample([(proj_x, proj_y)]))[0][0]
        coverage.close()
        return value

    def query(self,wgs_coords, properties=None, depths=None, scale_factors=None):
        """Query soil properties at a given lat/lon."""
        lat, lon = wgs_coords
        if properties is None:
            properties = list(SOIL_PROPERTIES.keys())
        if depths is None:
            depths = DEPTHS
        if scale_factors is None:
            scale_factors = SCALE_FACTORS

        proj_x, proj_y = self._to_xy(lat, lon)
        result = {}

        for prop in properties:
            scale = scale_factors.get(prop, 1)
            for depth in depths:
                name = f"{prop}_{depth}_mean"
                path = self.data_dir / f"{name}.tif"
                val = self._sample(path, (proj_x, proj_y))
                result[name] = round(val / scale, 2) if val else None

        return SoilPoint(lat=lat, lon=lon, properties=result)


if __name__ == "__main__":
    # STEP 1 — Run once to download rasters
    #downloader = SoilGridsDownloader()
    #downloader.download_all()  # Uncomment to download everything
    #downloader.download_property("ocs")  # Or just one property

    # STEP 2 — Query a point
    query = SoilQuery(DATA_DIR)
    lat = 36.702269
    lon = 9.134415

    point = query.query(wgs_coords=(lat, lon))
    print(point)

    """
        plt_wcs_coverage(DATA_DIR / "phh2o_0-5cm_mean.tif",
                    wgs_coords=(lat, lon),
                    title="Mean pH between 0 and 5 cm deep in Tunisia",
                    )
    
    """
