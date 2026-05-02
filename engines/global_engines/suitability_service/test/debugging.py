
import rasterio
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from rasterio.plot import show
from rasterio.transform import rowcol


def plot_tiff_with_cross(
    tiff_path: str,
    coordinates: list[tuple[float, float]],  # now expects (lat, lon)
    cross_size: int = 20,
    cross_color: str = "red",
    cross_linewidth: float = 2.0,
    figsize: tuple = (10, 8),
    title: str = None,
):
    """
    ...
    coordinates : list of (float, float)
        List of (latitude, longitude) pairs in WGS84 (EPSG:4326).
    ...
    """
    with rasterio.open(tiff_path) as src:
        fig, ax = plt.subplots(figsize=figsize)
        show(src, ax=ax)

        transform = src.transform

        for lat, lon in coordinates:  # ← unpack as lat, lon
            row, col = rowcol(transform, lon, lat)  # ← rowcol wants (x=lon, y=lat)
            x, y = rasterio.transform.xy(transform, row, col)

            pixel_size_x = abs(transform.a)
            pixel_size_y = abs(transform.e)
            arm_x = cross_size * pixel_size_x
            arm_y = cross_size * pixel_size_y

            ax.plot([x - arm_x, x + arm_x], [y, y], color=cross_color, linewidth=cross_linewidth)
            ax.plot([x, x], [y - arm_y, y + arm_y], color=cross_color, linewidth=cross_linewidth)

        ax.set_title(title or tiff_path.split("/")[-1])
        plt.tight_layout()
        plt.show()

        return fig, ax
    
    

plot_tiff_with_cross(
    tiff_path="D:/ARDHI/TIFF/clipped/GAEZ-V5.RES05-SXX30AS.HP0120.AGERA5.HIST.OLV.LILM.tif",
    coordinates=[(37.024050, 9.435166)],  # (lat, lon) → Tunis ✅
)
