# see if all 
import rasterio
from rasterio.plot import show


tiff_path = "gaez_data/tiff_files/GAEZ-V5.RES05-YXX.HP0120.AGERA5.HIST.WHE.HILM.tif"

with rasterio.open(tiff_path) as src:
    show(src)