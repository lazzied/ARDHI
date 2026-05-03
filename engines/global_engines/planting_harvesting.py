"""Global crop-calendar engine built from planting-day and crop-cycle raster layers."""
# RES02-CBD: optimum starting day of crop growth cycle at ~10 km resolution.
# RES02-CYC: number of days from planting to harvest for maximum yield potential.
from datetime import date, timedelta
import logging

from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.connections import get_ardhi_connection
from data_scripts.gaez_scripts.metadata.gaez_metadata_templates import CROP_REGISTRY
from engines.OCR_processing.models import InputLevel, WaterSupply
from engines.global_engines.models import CropCalendarClass
from raster.tiff_operations import read_tiff_pixel


logger = logging.getLogger(__name__)


class CropCalendar:
    def __init__(self, repo: ArdhiRepository, coord: tuple, input_level: InputLevel, water_supply: WaterSupply):
        self.repo = repo
        self.coord = coord
        self.input_level = input_level
        self.water_supply = water_supply
        self.crop_names = self.build_crop_names()

    @staticmethod
    def build_crop_names() -> dict:
        names = {}
        for crop_key, crop in CROP_REGISTRY.items():
            caption = crop.get("caption", crop_key)
            res05_code = crop.get("codes", {}).get("RES02")
            if res05_code:
                names[res05_code] = caption
            for st_key, st in crop.get("subtypes", {}).items():
                st_code = st.get("codes", {}).get("RES02")
                if st_code:
                    names[st_code] = st.get("description", f"{caption} ({st_key})")
        return names

    def get_optimum_planting_day(self, crop_code: str) -> int:
        tiff_file_path = self.repo.calendar_query_tiff_path(crop_code, "RES02-CBD", self.water_supply, self.input_level)
        return read_tiff_pixel(tiff_file_path, self.coord)

    def get_growth_days(self, crop_code: str) -> int:
        tiff_file_path = self.repo.calendar_query_tiff_path(crop_code, "RES02-CYL", self.water_supply, self.input_level)
        return read_tiff_pixel(tiff_file_path, self.coord)

    def build_calendar_class(self, crop_code: str) -> CropCalendarClass | None:
        try:
            planting_day = self.get_optimum_planting_day(crop_code)
            growth_days = self.get_growth_days(crop_code)

            if planting_day is None or growth_days is None:
                logger.debug("Skipping %s due to missing raster value", crop_code)
                return None

            planting_day = int(planting_day)
            growth_days = int(growth_days)

            d_plant = date(2001, 1, 1) + timedelta(days=planting_day - 1)
            d_harvest = date(2001, 1, 1) + timedelta(days=planting_day - 1 + growth_days)

            logger.debug(
                "Calendar found for %s: planting=%s harvest=%s",
                crop_code,
                d_plant.strftime("%B %d"),
                d_harvest.strftime("%B %d"),
            )
            return CropCalendarClass(
                crop_code=crop_code,
                planting_day=planting_day,
                growth_days=growth_days,
                planting_date=d_plant.strftime("%B %d"),
                harvest_date=d_harvest.strftime("%B %d"),
            )
        except Exception as exc:
            logger.warning("Skipping %s while building crop calendar: %s", crop_code, exc)
            return None

    def crop_calendar_class_factory(self) -> list[CropCalendarClass]:
        crop_calendar_classes = []
        for crop_code in self.crop_names:
            calendar_class = self.build_calendar_class(crop_code)
            if calendar_class is not None:
                crop_calendar_classes.append(calendar_class)
        return crop_calendar_classes


if __name__ == "__main__":
    conn = get_ardhi_connection()
    ardhi_repo = ArdhiRepository(conn)

    input_level = InputLevel.HIGH
    water_supply = WaterSupply.RAINFED
    coord = (37.024050, 9.435166)

    calendar = CropCalendar(repo=ardhi_repo, coord=coord, input_level=input_level, water_supply=water_supply)
    results = calendar.crop_calendar_class_factory()

    for result in results:
        print(f"Crop          : {result.crop_code}")
        print(f"Planting day  : {result.planting_day}")
        print(f"Growth days   : {result.growth_days}")
        print(f"Planting date : {result.planting_date}")
        print(f"Harvest date  : {result.harvest_date}")
        print("---")
