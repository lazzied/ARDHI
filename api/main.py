from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.connections import get_ardhi_connection, get_hwsd_connection
from ardhi.db.hwsd import HwsdRepository
from engines.OCR_processing.models import InputLevel, IrrigationType, ScenarioConfig, WaterSupply
from engines.OCR_processing.suitability_service.suitability_rank import ReportCropSuitability
from engines.OCR_processing.yield_service.yield_rank import ReportCropYield
from engines.global_engines.planting_harvesting import CropCalendar
from engines.global_engines.sq import GlobalSq, ReportSq
from engines.global_engines.suitability_service.suitability_engine import CropSuitability
from engines.global_engines.yield_service.yield_engine import CropYield
from session import user_sessions

app = FastAPI(title="Backend API", version="1.0.0")

OTHER_SERVICE_URL = "http://localhost:9000"

#-------db connections -------------------------------------
ardhi_conn = get_ardhi_connection()
ardhi_repo = ArdhiRepository(ardhi_conn)

hwsd_conn = get_hwsd_connection()
hwsd_repo = HwsdRepository(hwsd_conn)

# ─── Models ───────────────────────────────────────────────
class OnboardingChoice(BaseModel):
    user_id: str
    lab_report_exists: bool

class LabReport(BaseModel):
    user_id: str
    lab_report: dict

class UserInput(BaseModel):
    user_id: str
    coord: tuple[float, float] #lat,lon
    input_level: InputLevel
    water_supply: WaterSupply
    irrigation_type:IrrigationType
    
    input_management = "HIM" if input_level == InputLevel.HIGH else "LIM"
    
    answers: dict[str, str]
    lab_report_exists: bool
    lab_report: Optional[dict] = None

# ─── Routes ───────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "running"}

@app.post("/onboarding")
def onboarding(data: OnboardingChoice):
    user_sessions[data.user_id] = {"lab_report_exists": data.lab_report_exists}
    return {"status": "stored"}

@app.post("/lab-report")
def receive_lab_report(data: LabReport):
    if data.user_id not in user_sessions:
        user_sessions[data.user_id] = {}
    user_sessions[data.user_id]["lab_report"] = data.lab_report
    user_sessions[data.user_id]["lab_report_exists"] = True
    return {"status": "stored"}

@app.post("/submit-input")
def submit_input(data: UserInput):
    if data.user_id not in user_sessions:
        user_sessions[data.user_id] = {}
    user_sessions[data.user_id].update(data.model_dump())
    return {"status": "stored"}


@app.get("/global/crop-recommendations/{user_id}")
def get_global_crop_recommendations(user_id: str):
    data = user_sessions.get(user_id)
    if not data:
        raise HTTPException(status_code=404, detail="No session data found")

    crop_suitability = CropSuitability(
        ardhi_repo,
        data["input_level"],
        data["water_supply"],
        data["coord"]
    )

    crop_yield = CropYield(
        ardhi_repo,
        input_level=data["input_level"],
        water_supply=data["water_supply"],
        coord=data["coord"],
    )

    ranking_yield = crop_yield.build_ranking_class()
    ranking_suitability = crop_suitability.build_ranking_class()
    return {
        "status": "success",
        "data": {
            "suitability": ranking_suitability.to_dict(),
            "yield": ranking_yield.to_dict()
        }
    }


@app.get("/report/crop-recommendations/{user_id}")
def get_report_crop_recommendations(user_id: str):
    data = user_sessions.get(user_id)
    if not data:
        raise HTTPException(status_code=404, detail="No session data found")
    
    report_crop_yield = ReportCropYield(
        hwsd_repo,
        ardhi_repo,
        data["input_level"],
        data["water_supply"],
        data["coord"]
    )
    report_ranking_yield = report_crop_yield.build_ranking_class()
    
    report_crop_suitability = ReportCropSuitability(report_ranking_yield)
    report_ranking_suitability = report_crop_suitability.build_ranking_class()
    
    return {
        "status": "success",
        "data": {
            "suitability": report_ranking_suitability.ratio_to_dict(),
            "yield": report_ranking_yield.to_dict()
        }
    }
    
#soil profile page
@app.get("/calendar")
def get_calendar_props(data: UserInput):
    calendar = CropCalendar(repo=ardhi_repo, coord=data.coord, input_level=data.input_level, water_supply=data.water_supply)
    return calendar.crop_calendar_class_factory()


@app.get("/global/soil-constraint-factor/")
def get_global_soil_qualities_factor(data: UserInput):
    
    global_sq = GlobalSq(ardhi_repo=ardhi_repo,
                         management=data.input_management,
                         coord=data.coord)
    
    results    = global_sq.build_sq_class()
    return results.to_dict()

    
  
@app.get("/report/soil-constraint-factor/{crop_name}")
def get_report_soil_qualities_factor(data: UserInput, crop_name):
    
    scenario = ScenarioConfig(crop_name, data.input_level, data.water_supply, data.irrigation_type)
    report_sq = ReportSq(data.coood,scenario,hwsd_repo,ardhi_repo)
    results = report_sq.build_sq_class()
    
    return results.to_dict()
    


#crops page  
@app.get("/crops-info")
def get_crops_info():
    # fetch from crop plant DB
    pass

#weather profile + my climate
@app.get()
def get_biome_weather_info():
    # quick search on GAEZ; or integrate API
    pass

#my soil page
@app.get("/")
def get_soil_needs(): # this is across the 7 SQ levels : two resources; GAEZ through edaphic tables and plantcrop
    # get speccif
    pass

#weather profile
@app.get()
def get_crop_climate_needs(crop): #this is from plant crop
    pass


#final: fix 

