#RES02-CBD ; Optimum starting day of crop growth cycle provided as day of year at approximately 10 km resolution 
#RES02-CYC: Represents the number of days from planting to harvest for maximum yield potential.
from datetime import date, timedelta

from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.connections import get_ardhi_connection
from engines.OCR_processing.models import InputLevel, WaterSupply, get_crop_code
from raster.tiff_operations import sample_raster_at


class CropCalendar:
    def __init__(self, repo: ArdhiRepository, coord: tuple, input_level, water_supply):
        self.repo = repo
        self.coord = coord
        self.input_level = input_level
        self.water_supply = water_supply

    def get_optimum_planting_day(self, crop_code: str) -> float:
        tiff_file_path = self.repo.calendar_query_tiff_path(crop_code, "RES02-CBD", self.water_supply, self.input_level)
        return sample_raster_at(tiff_file_path, self.coord)

    def get_growth_days(self, crop_code: str) -> float:
        tiff_file_path = self.repo.calendar_query_tiff_path(crop_code, "RES02-CYL", self.water_supply, self.input_level)
        return sample_raster_at(tiff_file_path, self.coord)

    def get_planting_date(self, crop_code: str) -> str:
        """Convert optimum planting day-of-year to a month/day string."""
        day_of_year = int(self.get_optimum_planting_day(crop_code))
        d = date(2001, 1, 1) + timedelta(days=day_of_year - 1)
        return d.strftime("%B %d")

    def get_harvest_date(self, crop_code: str) -> str:
        """Calculate harvest month/day = planting day + growth cycle days."""
        day_of_year = int(self.get_optimum_planting_day(crop_code))
        growth_days = int(self.get_growth_days(crop_code))
        d = date(2001, 1, 1) + timedelta(days=day_of_year - 1 + growth_days)
        return d.strftime("%B %d")


if __name__ == "__main__":
    conn = get_ardhi_connection()
    ardhi_repo = ArdhiRepository(conn)

    input_level = InputLevel.HIGH
    water_supply = WaterSupply.RAINFED
    coord = (37.024050, 9.435166)
    crop_code = get_crop_code("maize", "RES02")

    print("crop_code", crop_code)

    calendar = CropCalendar(repo=ardhi_repo, coord=coord, input_level=input_level, water_supply=water_supply)

    planting_day  = calendar.get_optimum_planting_day(crop_code)
    growth_days   = calendar.get_growth_days(crop_code)
    planting_date = calendar.get_planting_date(crop_code)
    harvest_date  = calendar.get_harvest_date(crop_code)

    print(f"Crop          : {crop_code}")
    print(f"Coord         : {coord}")
    print(f"Planting day  : {planting_day} (day of year)")
    print(f"Growth days   : {growth_days}")
    print(f"Planting date : {planting_date}")   # ← already a string, no .strftime()
    print(f"Harvest date  : {harvest_date}")    # ← already a string, no .strftime()