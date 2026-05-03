"""Report-based yield calculation pipeline built on PyAEZ soil constraints."""
import difflib
import logging
import numpy as np
from pyaez import SoilConstraints
from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.connections import close_connection, get_ardhi_connection, get_hwsd_connection
from ardhi.db.hwsd import HwsdRepository
from engines.OCR_processing.models import (
    DRIP_IRRIGATED_CROPS, GRAVITY_IRRIGATED_CROPS, INPUT_LEVEL_TO_PYAEZ, 
    RAINFED_SPRINKLER_CROPS, InputLevel, IrrigationType, ScenarioConfig, SiteContext, 
    Texture, WaterSupply, WaterSupplyIndex, get_crop_code, pH_level
)
from engines.soil_properties_builder.hwsd2_prop.hwsd_prop_generator import HWSDPropGenerator
from engines.soil_properties_builder.report_augmentation.processing import ReportOperations, ReportPropGenerator
from raster.tiff_operations import get_smu_id_value, read_tiff_pixel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper Logic
# ---------------------------------------------------------------------------

def normalize(name: str) -> str:
    return name.strip().lower()

def suggest(name: str, choices: set[str], n: int = 3) -> list[str]:
    return difflib.get_close_matches(name, choices, n=n, cutoff=0.5)

def validate_crop_name(
    crop_name: str,
    water_supply: WaterSupply,
    irrigation_type: IrrigationType | None = None,
) -> str:
    name = normalize(crop_name)
    if water_supply == WaterSupply.RAINFED:
        valid_crops, context = RAINFED_SPRINKLER_CROPS, "rainfed/sprinkler"
    elif water_supply == WaterSupply.IRRIGATED:
        if irrigation_type == IrrigationType.GRAVITY:
            valid_crops, context = GRAVITY_IRRIGATED_CROPS, "gravity irrigation"
        elif irrigation_type == IrrigationType.SPRINKLER:
            valid_crops, context = RAINFED_SPRINKLER_CROPS, "sprinkler irrigation"
        elif irrigation_type == IrrigationType.DRIP:
            valid_crops, context = DRIP_IRRIGATED_CROPS, "drip irrigation"
        else:
            raise ValueError(f"Invalid irrigation type: {irrigation_type}")
    else:
        raise ValueError(f"Invalid water supply: {water_supply}")

    if name not in valid_crops:
        suggestions = suggest(name, valid_crops)
        msg = f"Invalid crop '{crop_name}' for {context}."
        if suggestions:
            msg += f" Did you mean: {', '.join(suggestions)}?"
        raise ValueError(msg)
    return name

# ---------------------------------------------------------------------------
# Yield Repository (Data Access)
# ---------------------------------------------------------------------------

class YieldRepository:
    def __init__(self, ardhi_repo: ArdhiRepository, scenario: ScenarioConfig, site: SiteContext):
        self.ardhi_repo = ardhi_repo
        self.scenario = scenario
        self.site = site

    def _get_yield_from_map(self, crop_code_res: str, map_code: str) -> float:
        crop_code = get_crop_code(self.scenario.crop_name, crop_code_res)
        tiff_path = self.ardhi_repo.query_tiff_path(
            input_level=self.scenario.input_level,
            water_supply=self.scenario.water_supply,
            crop_code=crop_code,
            map_code=map_code,
        )
        return read_tiff_pixel(tiff_path, self.site.coordinates)

    def get_agroclimatic_yield(self) -> float:
        return self._get_yield_from_map("RES02", "RES02-YLD")

    def get_full_constraints_yield(self) -> float:
        crop_code = get_crop_code(self.scenario.crop_name, "RES02")
        logger.debug(
            "Fetching full-constraints yield crop_code=%s input_level=%s water_supply=%s",
            crop_code,
            self.scenario.input_level.value,
            self.scenario.water_supply.value,
        )
        return self._get_yield_from_map("RES05", "RES05-YLX30AS")

    def get_edaphic_paths(self) -> tuple[str, str]:
        validated_name = validate_crop_name(
            self.scenario.crop_name, self.scenario.water_supply, self.scenario.irrigation_type
        )



        rainfed_path = self.ardhi_repo.query_edaphic_path(self.scenario,self.site.ph_level,self.site.texture_class)
        

        if self.scenario.water_supply == WaterSupply.RAINFED:
            return rainfed_path, rainfed_path

        irrigated_path = self.ardhi_repo.query_edaphic_path(self.scenario,self.site.ph_level,self.site.texture_class)
        return rainfed_path, irrigated_path

# ---------------------------------------------------------------------------
# Yield Calculator (Logic)
# ---------------------------------------------------------------------------

class YieldCalculator:
    def __init__(self, yield_repo: YieldRepository, soil_prop_path: str):
        self.repo = yield_repo
        self.soil_prop_path = soil_prop_path
        
        

    def calculate_fc4_yield(self, smu_id: int, yield_in: float) -> float:
        paths = self.repo.get_edaphic_paths()

        soil_constraints = SoilConstraints.SoilConstraints()
        soil_constraints.importSoilReductionSheet(paths[0], paths[1])

        ws_idx = WaterSupplyIndex[self.repo.scenario.water_supply.name].value
        il_idx = INPUT_LEVEL_TO_PYAEZ[self.repo.scenario.input_level]

        soil_constraints.calculateSoilQualities(ws_idx, self.soil_prop_path, self.soil_prop_path)
        soil_constraints.calculateSoilRatings(il_idx)

        yield_out = soil_constraints.applySoilConstraints(
            np.array([[smu_id]], dtype=np.int64), 
            np.array([[yield_in]], dtype=float)
        )
        return float(yield_out[0, 0])
    
    def get_soil_qualities(self):
        paths = self.repo.get_edaphic_paths()
        
        soil_constraints = SoilConstraints.SoilConstraints()
        soil_constraints.importSoilReductionSheet(paths[0], paths[1])

        ws_idx = WaterSupplyIndex[self.repo.scenario.water_supply.name].value

        soil_constraints.calculateSoilQualities(ws_idx, self.soil_prop_path, self.soil_prop_path)
        
        return soil_constraints.getSoilQualities()
        

    def orchestrate_fc4(self) -> float:
        smu_id = self.repo.site.smu_id or get_smu_id_value(self.repo.site.coordinates)
        if smu_id is None:
            raise ValueError(f"No SMU found at {self.repo.site.coordinates}")


        yield_in = self.repo.get_agroclimatic_yield()

        return self.calculate_fc4_yield(smu_id, yield_in)





# ---------------------------------------------------------------------------
# Orchestration and Main
# ---------------------------------------------------------------------------


class YieldCalcOrchestrator:
    def __init__(self, coord, scenario, hwsd_repo, ardhi_repo):
        self.scenario = scenario
        self.hwsd_repo = hwsd_repo
        self.ardhi_repo = ardhi_repo
        self.coord = coord

        self.paths = {
            "report_input": "engines/soil_properties_builder/report_augmentation/input/rapport_values.json",
            "hwsd_out": "engines/soil_properties_builder/output/results/hwsd_results",
            "report_out": "engines/soil_properties_builder/output/results/report_results"
        }

        # Step 1: get smu_id and fao_90 first
        smu_id = get_smu_id_value(coord)
        
        fao_90 = hwsd_repo.get_fao_90(smu_id)

        # Step 2: init hwsd_gen (needs smu_id and fao_90)
        self.hwsd_gen = HWSDPropGenerator(
            smu_id, fao_90, self.hwsd_repo,
            self.paths["hwsd_out"], "hwsd_soil"
        )

        # Step 3: now get texture and ph (needs hwsd_gen)
        texture_class, ph_level = self.get_texture_and_ph()

        # Step 4: build site with full info
        self.site = SiteContext(
            coordinates=coord,
            ph_level=ph_level,
            texture_class=texture_class,
            smu_id=smu_id
        )
        self.fao_90_class = fao_90
        
    def run_yield_pipeline(
        self,
        scenario: ScenarioConfig,
        site: SiteContext,
        report_soil_path: str,
        hwsd_soil_path: str
    ) -> float:
        repo = YieldRepository(self.ardhi_repo, scenario, site)

        calc = YieldCalculator(repo, soil_prop_path=report_soil_path)
        fc4_report = calc.orchestrate_fc4()

        calc.soil_prop_path = hwsd_soil_path
        fc4_hwsd = calc.orchestrate_fc4()

        final_gaez_yield = repo.get_full_constraints_yield()
        fc5 = final_gaez_yield / fc4_hwsd if fc4_hwsd else 0.0

        return fc4_report * fc5

    def run(self):
        hwsd_path, report_path = self._generate_soils()
        return self.run_yield_pipeline(
            scenario=self.scenario,
            site=self.site,
            report_soil_path=report_path,
            hwsd_soil_path=hwsd_path
        )
        
    def get_texture_and_ph(self):
        texture_class = self.hwsd_gen.get_soter_texture()
        ph_level = ReportOperations(self.paths["report_input"]).get_report_ph_class()
        return texture_class, ph_level
    
    def get_soil_qualities(self) -> list:
        hwsd_path, report_path = self._generate_soils()
        repo = YieldRepository(self.ardhi_repo, self.scenario, self.site)
        calc = YieldCalculator(repo, soil_prop_path=report_path)
        return calc.get_soil_qualities()

    def _generate_soils(self):

        hwsd_soil_path = self.hwsd_gen.layers_orchestrator()

        report_ops = ReportOperations(self.paths["report_input"])
        report_gen = ReportPropGenerator(
            smu_id=self.site.smu_id,
            fao_90_class=self.fao_90_class,
            report_ops=report_ops,
            hwsd_repo=self.hwsd_repo,
            hwsd_prop_generator=self.hwsd_gen,
            output_dir=self.paths["report_out"],
            filename="report_soil"
        )
        
        report_soil_path = report_gen.layers_orchestrator()

        return hwsd_soil_path, report_soil_path



if __name__ == "__main__":
    # 1. Setup Inputs
    coord = (36.858096, 9.962084)
    scenario = ScenarioConfig(
        crop_name="maize",
        input_level=InputLevel.HIGH,
        water_supply=WaterSupply.RAINFED
    )
    
    # 2. Open Connections
    conn_hwsd = get_hwsd_connection()
    conn_ardhi = get_ardhi_connection()

    try:
        # 3. Use the Orchestrator's internal helper to build context
        hwsd_repo = HwsdRepository(conn_hwsd)
        ardhi_repo = ArdhiRepository(conn_ardhi)
        
        # 4. Initialize and Run

        orchestrator = YieldCalcOrchestrator(
            coord= coord,
            scenario=scenario,
            hwsd_repo=hwsd_repo,
            ardhi_repo=ardhi_repo
        )
        
        qualities = orchestrator.get_soil_qualities()
        
        final_yield = orchestrator.run()
        print(f"\n{'='*30}\nFINAL CALCULATED YIELD: {final_yield}\n{'='*30}")

    finally:
        close_connection(conn_hwsd)
        close_connection(conn_ardhi)
