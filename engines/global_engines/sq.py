"""Global and report-based soil-quality factor builders."""
import logging

from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.connections import get_ardhi_connection, get_hwsd_connection
from ardhi.db.hwsd import HwsdRepository
from engines.OCR_processing.models import InputLevel, ScenarioConfig, WaterSupply
from engines.OCR_processing.yield_service.yield_calc import YieldCalcOrchestrator
from engines.global_engines.models import InputManagement, SoilQuality, SqClass
from raster.tiff_operations import read_tiff_pixel


logger = logging.getLogger(__name__)


class GlobalSq:
    def __init__(self, ardhi_repo: ArdhiRepository, management: InputManagement, coord):
        self.ardhi_repo = ardhi_repo
        self.management = management
        self.coord = coord

    def build_sq_class(self) -> SqClass:
        sq_paths_dict = self.ardhi_repo.query_all_sq_file_paths(self.management)
        values = {
            sq.name.lower(): read_tiff_pixel(sq_paths_dict[sq.value], self.coord)
            for sq in SoilQuality
            if sq.value in sq_paths_dict
        }
        most_limiting_factor = min(values, key=lambda key: values[key] if values[key] is not None else float("inf"))

        return SqClass(
            most_limiting_factor=most_limiting_factor,
            nutrient_availability=values.get("nutrient_availability"),
            nutrient_retention_capacity=values.get("nutrient_retention_capacity"),
            rooting_conditions=values.get("rooting_conditions"),
            oxygen_availability=values.get("oxygen_availability"),
            salinity_and_sodicity=values.get("salinity_and_sodicity"),
            lime_and_gypsum=values.get("lime_and_gypsum"),
            workability=values.get("workability"),
        )


class ReportSq:
    def __init__(self, coord: tuple, scenario: ScenarioConfig, hwsd_repo: HwsdRepository, ardhi_repo: ArdhiRepository):
        self.scenario = scenario
        self.hwsd_repo = hwsd_repo
        self.ardhi_repo = ardhi_repo
        self.coord = coord

    def build_sq_class(self) -> SqClass:
        orchestrator = YieldCalcOrchestrator(
            coord=self.coord,
            scenario=self.scenario,
            hwsd_repo=self.hwsd_repo,
            ardhi_repo=self.ardhi_repo,
        )

        qualities = orchestrator.get_soil_qualities()
        logger.debug("Computed report soil qualities for %s", self.coord)

        row = qualities.iloc[0].drop("SMU").to_dict()
        sq_to_field = {
            "SQ1": "nutrient_availability",
            "SQ2": "nutrient_retention_capacity",
            "SQ3": "rooting_conditions",
            "SQ4": "oxygen_availability",
            "SQ5": "salinity_and_sodicity",
            "SQ6": "lime_and_gypsum",
            "SQ7": "workability",
        }
        values = {sq_to_field[key]: value for key, value in row.items()}
        most_limiting_factor = min(values, key=lambda key: values[key])

        return SqClass(
            most_limiting_factor=most_limiting_factor,
            nutrient_availability=values["nutrient_availability"],
            nutrient_retention_capacity=values["nutrient_retention_capacity"],
            rooting_conditions=values["rooting_conditions"],
            oxygen_availability=values["oxygen_availability"],
            salinity_and_sodicity=values["salinity_and_sodicity"],
            lime_and_gypsum=values["lime_and_gypsum"],
            workability=values["workability"],
        )


if __name__ == "__main__":
    coord = (36.858096, 9.962084)
    scenario = ScenarioConfig(
        crop_name="maize",
        input_level=InputLevel.HIGH,
        water_supply=WaterSupply.RAINFED,
    )

    conn_hwsd = get_hwsd_connection()
    hwsd_repo = HwsdRepository(conn_hwsd)
    ardhi_conn = get_ardhi_connection()
    ardhi_repo = ArdhiRepository(ardhi_conn)

    report_sq = ReportSq(coord, scenario, hwsd_repo, ardhi_repo)
    print(report_sq.build_sq_class())
