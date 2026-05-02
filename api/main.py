from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.connections import get_ardhi_connection
from engines.OCR_processing.models import InputLevel, WaterSupply
from engines.global_engines.suitability_service.suitability_engine import CropSuitability
from engines.global_engines.yield_service.yield_engine import CropYield
from session import user_sessions

app = FastAPI(title="Backend API", version="1.0.0")

OTHER_SERVICE_URL = "http://localhost:9000"

#-------db connections -------------------------------------
ardhi_conn = get_ardhi_connection()
ardhi_repo = ArdhiRepository(ardhi_conn)

# ─── Models ───────────────────────────────────────────────
class OnboardingChoice(BaseModel):
    user_id: str
    lab_report_exists: bool

class LabReport(BaseModel):
    user_id: str
    lab_report: dict

class UserInput(BaseModel):
    user_id: str
    coords: tuple[float, float] #lat,lon
    input_level: InputLevel
    water_supply: WaterSupply
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


@app.get("/global-crop-recommendations/{user_id}")
def get_global_crop_recommendations(user_id: str):
    data = user_sessions.get(user_id)
    if not data:
        raise HTTPException(status_code=404, detail="No session data found")

    crop_suitability = CropSuitability(
        ardhi_repo,
        data["input_level"],
        data["water_supply"],
        data["coords"]
    )

    crop_yield = CropYield(
        ardhi_repo,
        input_level=data["input_level"],
        water_supply=data["water_supply"],
        coord=data["coords"],
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


@app.get("/report-crop-recommendations/{user_id}")
def get_report_crop_recommendations(user_id: str):
    data = user_sessions.get(user_id)
    if not data:
        raise HTTPException(status_code=404, detail="No session data found")
    
    # call your services with data
    pass
