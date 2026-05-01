#RES02-CBD ; Optimum starting day of crop growth cycle provided as day of year at approximately 10 km resolution 
#RES02-CYC: Represents the number of days from planting to harvest for maximum yield potential.

from ardhi.db.ardhi import ArdhiRepository
from engines.OCR_processing.yield_service.yield_calc import _sample_raster_at

class CropCalendar:
    def __init__(self, repo: ArdhiRepository):
        self.repo = repo
    
    def get_optimum_planting_day(self,crop_code: str, coords) -> float:
        tiff_file_path = self.repo.calendar_query_tiff_path(crop_code, "RES02-CBD")
        return _sample_raster_at(tiff_file_path, coords)


    def get_growth_days(self,crop_code: str, coords) -> float:
        tiff_file_path = self.repo.calendar_query_tiff_path(crop_code, "RES02-LGD")
        return _sample_raster_at(tiff_file_path, coords)




"""
RES02-ETA = moisture
description:
{"layer": {"map_code": "RES02-ETA",
"title": "Crop-specific actual evapotranspiration",
"description": "Crop-specific actual evapotranspiration provided in mm at approximately 10 km resolution. Represents the actual water lost through evaporation and plant transpiration during the crop growth cycle.
Modeled results for crop sub-types are available only via download from Google Cloud Storage.", "unit": "mm", "nodata": -9, "scale_factor": 1.0, "resolution": "10km", "category": "calendar", "dimension_profile": "historical+future", "license": "CC-BY-4.0"}, "category": {"name": "calendar", "description": "Crop-specific timing and resource use during the growth cycle. Generates actual planting and harvest dates, heat requirements, and per-crop water demand. Turns a recommendation into a farming plan."}, "crop": {"key": "sugar_beet", "caption": "Sugar beet", "source": "RES02"}, "period": {"code": "HP0120", "caption": "2001-2020", "type": "historical"}, "climate_model": {"code": "AGERA5", "caption": "AgERA5", "description": "Copernicus AgERA5 reanalysis. Used for historical periods (1981-2000, 2001-2020)."}, "ssp": {"code": "HIST", "caption": "Historical", "description": "No SSP \u2014 used with historical periods HP8100 and HP0120."}, "input_level": {"code": "low", "unresolved": true}, "water_supply": {"code": "irrigated", "unresolved": true}}

thermal = "RES02-TSC",
{"layer": {"map_code": "RES02-TSC",
"title": "Crop-specific accumulated temperature during growth cycle", 
"description": "Crop-specific accumulated temperature sums during the crop growth cycle at approximately 10 km resolution. Represents the total heat units accumulated during the growing season, used for matching crop heat requirements. Modeled results for crop sub-types are available only via download from Google Cloud Storage.",
"unit": "degC*days", "nodata": -9999, "scale_factor": 1.0, "resolution": "10km", "category": "calendar", "dimension_profile": "historical+future", "license": "CC-BY-4.0"}, "category": {"name": "calendar", "description": "Crop-specific timing and resource use during the growth cycle. Generates actual planting and harvest dates, heat requirements, and per-crop water demand. Turns a recommendation into a farming plan."}, "crop": {"key": "miscanthus", "caption": "Miscanthus", "source": "RES02"}, "period": {"code": "HP0120", "caption": "2001-2020", "type": "historical"}, "climate_model": {"code": "AGERA5", "caption": "AgERA5", "description": "Copernicus AgERA5 reanalysis. Used for historical periods (1981-2000, 2001-2020)."}, "ssp": {"code": "HIST", "caption": "Historical", "description": "No SSP \u2014 used with historical periods HP8100 and HP0120."}, "input_level": {"code": "low", "unresolved": true}, "water_supply": {"code": "irrigated", "unresolved": true}}

{"layer": {"map_code": "RES02-WDE", "title":
    "Crop water deficit", "description": 
        "Crop water deficit provided in mm at approximately 10 km resolution. Represents the difference between crop water requirement and actual water available during the growth cycle, indicating the amount of supplemental irrigation needed.", "unit": "mm", "nodata": -9, "scale_factor": 1.0, "resolution": "10km", "category": "calendar", "dimension_profile": "historical+future", "license": "CC-BY-4.0"}, "category": {"name": "calendar", "description": "Crop-specific timing and resource use during the growth cycle. Generates actual planting and harvest dates, heat requirements, and per-crop water demand. Turns a recommendation into a farming plan."}, "crop": {"key": "coconut", "subtype": "dwarf", "caption": "Dwarf coconut", "source": "RES02"}, "period": {"code": "HP0120", "caption": "2001-2020", "type": "historical"}, "climate_model": {"code": "AGERA5", "caption": "AgERA5", "description": "Copernicus AgERA5 reanalysis. Used for historical periods (1981-2000, 2001-2020)."}, "ssp": {"code": "HIST", "caption": "Historical", "description": "No SSP \u2014 used with historical periods HP8100 and HP0120."}, "input_level": {"code": "high", "unresolved": true}, "water_supply": {"code": "irrigated", "unresolved": true}}
"""