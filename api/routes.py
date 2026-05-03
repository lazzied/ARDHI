from typing import Any

from fastapi import APIRouter, Depends

from api.dependencies import Repositories, get_repositories
from api.models import ApiResponse, AugmentedSoilRequest, CropsNeedsRequest, FaoDecisionRequest, LabReport, OnboardingChoice, UserInput
from api.services import (
    build_augmented_soil_report,
    build_calendar,
    build_crops_info,
    build_crops_needs,
    build_fao_decision,
    build_global_crop_recommendations,
    build_global_soil_quality,
    build_hwsd_soil_report,
    build_report_crop_recommendations,
    build_report_soil_quality,
    build_selection_catalog,
    store_user_input,
)
from api.session import user_sessions


router = APIRouter()


def success(data: Any = None, **extra) -> dict:
    payload = {"status": "success"}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return payload


@router.get("/")
def root():
    return {"status": "running"}


@router.get(
    "/metadata/selections",
    response_model=ApiResponse,
    summary="Get selectable frontend options",
    description="Returns dropdown/select options for user inputs and the full FAO question bank used by the decision flow.",
)
def get_selection_catalog():
    return success(build_selection_catalog())


@router.post(
    "/onboarding",
    response_model=ApiResponse,
    summary="Start a user session",
    description="Stores the initial onboarding choice, especially whether the user already has a lab soil report.",
)
def onboarding(data: OnboardingChoice):
    user_sessions[data.user_id] = {"lab_report_exists": data.lab_report_exists}
    return success()


@router.post(
    "/lab-report",
    response_model=ApiResponse,
    summary="Store lab report data",
    description="Stores a structured lab report payload in the user session for later report-based soil processing.",
)
def receive_lab_report(data: LabReport):
    session = user_sessions.get(data.user_id, {})
    session["lab_report"] = data.lab_report
    session["lab_report_exists"] = True
    user_sessions[data.user_id] = session
    return success()


@router.post(
    "/submit-input",
    response_model=ApiResponse,
    summary="Store base user input",
    description="Stores the main user input. The backend resolves smu_id from coord and seeds the session with the best current FAO90 class.",
)
def submit_input(
    data: UserInput,
    repos: Repositories = Depends(get_repositories),
):
    store_user_input(data, repos)
    return success()


@router.post(
    "/soil/fao-decision",
    response_model=ApiResponse,
    summary="Advance or complete the FAO soil decision",
    description="Given user_id, coord, and current answers, returns the next relevant FAO question or the final selected FAO90 class. On completion, the selected FAO class is persisted in session for downstream models.",
)
def get_fao_decision(
    data: FaoDecisionRequest,
    repos: Repositories = Depends(get_repositories),
):
    return success(build_fao_decision(data.user_id, data.coord, data.answers, repos))


@router.get(
    "/global/crop-recommendations/{user_id}",
    response_model=ApiResponse,
    summary="Get global crop recommendations",
    description="Returns suitability and yield rankings from the global raster-based workflow using the stored user session.",
)
def get_global_crop_recommendations(
    user_id: str,
    repos: Repositories = Depends(get_repositories),
):
    return success(build_global_crop_recommendations(user_id, repos))


@router.get(
    "/report/crop-recommendations/{user_id}",
    response_model=ApiResponse,
    summary="Get report-based crop recommendations",
    description="Returns suitability and yield rankings from the augmented report workflow using the stored user session.",
)
def get_report_crop_recommendations(
    user_id: str,
    repos: Repositories = Depends(get_repositories),
):
    return success(build_report_crop_recommendations(user_id, repos))


@router.post(
    "/calendar",
    response_model=ApiResponse,
    summary="Get crop calendar",
    description="Returns planting and harvest timing for crops based on the provided user input.",
)
def get_calendar_props(
    data: UserInput,
    repos: Repositories = Depends(get_repositories),
):
    return success(build_calendar(data, repos))


@router.post(
    "/global/soil-constraint-factor",
    response_model=ApiResponse,
    summary="Get global soil constraint factors",
    description="Returns soil quality constraint factors from the global raster-based workflow.",
)
def get_global_soil_qualities_factor(
    data: UserInput,
    repos: Repositories = Depends(get_repositories),
):
    return success(build_global_soil_quality(data, repos))


@router.post(
    "/report/soil-constraint-factor/{crop_name}",
    response_model=ApiResponse,
    summary="Get report-based soil constraint factors",
    description="Returns soil quality constraint factors from the report-augmented workflow for a specific crop.",
)
def get_report_soil_qualities_factor(
    crop_name: str,
    data: UserInput,
    repos: Repositories = Depends(get_repositories),
):
    return success(build_report_soil_quality(data, crop_name, repos))


@router.get(
    "/crops-info",
    response_model=ApiResponse,
    summary="Get crop reference information",
    description="Returns EcoCrop-derived crop reference information used by the recommendation flows.",
)
def get_crops_info(repos: Repositories = Depends(get_repositories)):
    return success(build_crops_info(repos))


@router.post(
    "/crops-needs",
    response_model=ApiResponse,
    summary="Get crop ecological needs",
    description="Returns crop climate, terrain, and soil needs for the selected pH and texture classes.",
)
def get_crop_needs(
    data: CropsNeedsRequest,
    repos: Repositories = Depends(get_repositories),
):
    return success(build_crops_needs(data.user_input, data.ph_level, data.texture_class, repos))


@router.post(
    "/your-hwsd-soil-properties",
    response_model=ApiResponse,
    summary="Generate HWSD soil properties",
    description="Builds HWSD-based augmented soil layers for the provided user input and returns both JSON and the generated workbook path.",
)
def get_hwsd_soil_report(
    data: UserInput,
    repos: Repositories = Depends(get_repositories),
):
    report = build_hwsd_soil_report(data, repos)
    return success(report["soil_properties"], output_path=report["output_path"])


@router.post(
    "/report/your-augmented-soil-properties",
    response_model=ApiResponse,
    summary="Generate report-augmented soil properties",
    description="Builds report-augmented soil layers using the provided user input and lab report, and returns both JSON and the generated workbook path.",
)
@router.post("/report/your-augmented_soil-properties", include_in_schema=False, response_model=ApiResponse)
def get_augmented_soil_report(
    data: AugmentedSoilRequest,
    repos: Repositories = Depends(get_repositories),
):
    report = build_augmented_soil_report(data.user_input, data.report, repos)
    return success(report["soil_properties"], output_path=report["output_path"])
