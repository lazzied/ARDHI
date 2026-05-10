"""
import rasterio
paths = [
    "D:/ARDHI/TIFF/clipped/GAEZ-V5.RES02-YLD.HP0120.AGERA5.HIST.MAIZ.HRLM.tif",
    "D:/ARDHI/TIFF/clipped/GAEZ-V5.RES05-YLX30AS.HP0120.AGERA5.HIST.MZE.HRLM.tif",
]
coord = (37.024050, 9.435166)  # (lat, lon) — check order!

for path in paths:
    with rasterio.open(path) as src:
        print("CRS:", src.crs)
        print("Bounds:", src.bounds)
        print("Nodata:", src.nodata)
        # Sample the pixel — rasterio expects (lon, lat)
        val = list(src.sample([(coord[1], coord[0])]))[0]
        print("Pixel value (lon,lat order):", val)
        print()
 """       
import rasterio
coord = (37.024050, 9.435166)  # your current coord
lat, lon = coord

with rasterio.open("D:/ARDHI/TIFF/clipped/GAEZ-V5.RES02-YLD.HP0120.AGERA5.HIST.MAIZ.HRLM.tif") as src:
    print("Bounds:", src.bounds)
    print("Nodata:", src.nodata)
    val = list(src.sample([(lon, lat)]))[0][0]
    print("Value:", val)