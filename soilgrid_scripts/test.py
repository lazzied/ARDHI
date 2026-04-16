from owslib.wcs import WebCoverageService
import rasterio
from rasterio import plot
import matplotlib.pyplot as plt
from pyproj import Transformer

wcs = WebCoverageService('http://maps.isric.org/mapserv?map=/map/phh2o.map',
                         version='2.0.1') # the http endpoint specifies the soil characteristic (phh2o) and the map file


cov_id = 'phh2o_0-5cm_mean'
ph_0_5 = wcs.contents[cov_id]

print("operations",[op.name for op in wcs.operations])

print("supported formats:", ph_0_5.supportedFormats)

print("wcs contents:",list(wcs.contents))

names = [k for k in wcs.contents.keys() if k.startswith("phh2o_0-5cm")]
print(names) 

""" ['phh2o_0-5cm_Q0.05', 'phh2o_0-5cm_Q0.5', 'phh2o_0-5cm_Q0.95', 'phh2o_0-5cm_mean', 'phh2o_0-5cm_uncertainty'] """
""""""

tunisia_subsets = [('X', 1174846, 1714576), ('Y', 3361849, 4174481)]

crs = "http://www.opengis.net/def/crs/EPSG/0/152160" #coordinate reference system for Tunisia

response = wcs.getCoverage(
    identifier=cov_id,
    crs=crs,
    subsets=[('X', 1174846, 1714576), ('Y', 3361849, 4174481)],
    resx=250, resy=250,
    format=ph_0_5.supportedFormats[0]
)

with open('cfvo_15-30cm_mean.tif', 'wb') as f:
    f.write(response.read())
    
# Open raster
ph = rasterio.open("soil_data/cfvo_15-30cm_mean.tif")

# Create transformer
transformer = Transformer.from_crs("EPSG:4326", "ESRI:54052", always_xy=True)

# beja (WGS84)
lat = 36.702269
lon = 9.134415

# Convert to raster CRS
x, y = transformer.transform(lon, lat)
print("Projected coords:", x, y)

# ✅ Get raster value at that point
value = list(ph.sample([(x, y)]))[0][0]
print("pH value:", value)

# ✅ Plot raster
fig, ax = plt.subplots()
plot.show(ph, ax=ax, title='Mean pH between 0 and 5 cm deep in Tunisia', cmap='gist_ncar')

# ✅ Plot cross (marker)
ax.plot(x, y, marker='+', markersize=15, markeredgewidth=2)

# Optional: annotate value
ax.text(x, y, f"{value:.2f}", fontsize=10)

plt.show()

"""
from owslib.wcs import WebCoverageService
wcs = WebCoverageService("http://maps.isric.org/mapserv?map=/map/wrb.map", version='2.0.1')
print("soil classification",list(wcs.contents))
"""
