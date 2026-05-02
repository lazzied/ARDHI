import numpy as np
import rasterio
from rasterio.transform import rowcol
import geopandas as gpd
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter

from data_scripts.gaez_scripts.TIFFpipeline import RasterData, RasterProcessor


class RasterSmoother:

    def __init__(self, sigma: float = 1.5):
        self.sigma = sigma

    def smooth(self, img: np.ma.MaskedArray) -> np.ma.MaskedArray:
        return gaussian_filter(img, sigma=self.sigma)

    def process(self, tiff_path: str, shapefile_path: str) -> RasterData:
        processor = RasterProcessor()
        data = processor.process(tiff_path, shapefile_path)
        data.img = self.smooth(data.img)
        return data


class RasterPlotter:

    def __init__(self, cmap: str = "viridis", figsize: tuple = (8, 10), dpi: int = 200):
        self.cmap = cmap
        self.figsize = figsize
        self.dpi = dpi

    def _base_figure(self):
        return plt.subplots(figsize=self.figsize, dpi=self.dpi)

    @staticmethod
    def _draw_boundary(ax, gdf: gpd.GeoDataFrame):
        gdf.boundary.plot(ax=ax, edgecolor="red", linewidth=0.8, antialiased=True)

    @staticmethod
    def _latlon_to_pixel(gdf: gpd.GeoDataFrame, img_shape, lat: float, lon: float):
        bounds = gdf.to_crs("EPSG:4326").total_bounds
        img_h, img_w = img_shape
        px = (lon - bounds[0]) / (bounds[2] - bounds[0]) * img_w
        py = (bounds[3] - lat) / (bounds[3] - bounds[1]) * img_h
        return px, py

    def plot(self, data: RasterData, title: str = "Raster"):
        fig, ax = self._base_figure()
        im = ax.imshow(data.img, cmap=self.cmap, interpolation="bilinear")
        self._draw_boundary(ax, data.gdf)
        plt.colorbar(im, ax=ax)
        plt.title(title)
        plt.axis("off")
        plt.show()

    def plot_with_marker(
        self,
        data: RasterData,
        lat: float,
        lon: float,
        value=None,
        title: str = "Raster",
    ):
        fig, ax = self._base_figure()
        im = ax.imshow(data.img, cmap=self.cmap, interpolation="bilinear")
        self._draw_boundary(ax, data.gdf)

        px, py = self._latlon_to_pixel(data.gdf, data.img.shape, lat, lon)
        ax.plot(px, py, marker="+", color="red", markersize=12, markeredgewidth=1.8)

        label = f"({lat:.3f}, {lon:.3f})"
        if value is not None:
            label += f"\nval={value:.4g}"
        ax.annotate(
            label, xy=(px, py), xytext=(px + 5, py - 5),
            color="white", fontsize=7.5,
            bbox=dict(boxstyle="round,pad=0.3", fc="black", alpha=0.6),
        )

        plt.colorbar(im, ax=ax)
        plt.title(title)
        plt.axis("off")
        plt.show()


class RasterInspector:

    @staticmethod
    def get_value_at_location(data: RasterData, lat: float, lon: float):
        point_gdf = gpd.GeoDataFrame(
            geometry=gpd.points_from_xy([lon], [lat]),
            crs="EPSG:4326"
        ).to_crs(data.gdf.crs)

        x, y = point_gdf.geometry.iloc[0].x, point_gdf.geometry.iloc[0].y
        row, col = rowcol(data.transform, x, y)
        h, w = data.img.shape

        if not (0 <= row < h and 0 <= col < w):
            raise ValueError(f"Location ({lat}, {lon}) is outside the raster bounds.")

        value = data.img[row, col]

        if np.ma.is_masked(value):
            print(f"Value at ({lat}, {lon}): outside region (masked)")
            return None

        print(f"Value at ({lat}, {lon}): {value}")
        return float(value)


if __name__ == "__main__":
    SHAPEFILE = "gaez_data/tunisia_Tunisia_Country_Boundary/tunisia_Tunisia_Country_Boundary.shp"
    TIFF_PATH = "D:/ARDHI/TIFF/GAEZ-V5.AEZ57.tif"
    LAT       = 36.8
    LON       = 10.18
    TITLE     = "Tunisia AEZ"

    smoother  = RasterSmoother(sigma=1.5)
    plotter   = RasterPlotter(cmap="viridis")
    inspector = RasterInspector()

    data  = smoother.process(TIFF_PATH, SHAPEFILE)
    value = inspector.get_value_at_location(data, LAT, LON)
    plotter.plot_with_marker(data, LAT, LON, value=value, title=TITLE)

    # plot without marker:
    # plotter.plot(data, title=TITLE)