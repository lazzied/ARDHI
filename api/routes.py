"""HTTP routes for the WCS backend, kept thin and delegated to service helpers."""
from typing import Any

from fastapi import APIRouter, Depends

from api.dependencies import Repositories, get_repositories
from api.models import ApiResponse, EconomicSuitabilityRequest, FaoAnswersRequest, FaoDecisionRequest, LabReport, OnboardingChoice, UserInput
from api.services import (
    build_calendar,
    build_crops_info,
    build_crops_needs_for_user,
    build_economic_suitability,
    build_fao_decision,
    build_fao_questions,
    build_global_crop_recommendations,
    build_global_soil_quality_for_user,
    build_hwsd_soil_report_for_user,
    calendar_units,
    crop_needs_units,
    crop_recommendation_units,
    crops_info_units,
    economic_units,
    fao_decision_units,
    lab_report_units,
    persist_lab_report,
    build_report_crop_recommendations,
    build_report_soil_quality_for_user,
    build_selection_catalog,
    selection_catalog_units,
    soil_property_units,
    soil_quality_units,
    store_user_input,
    build_augmented_soil_report_for_user,
    submit_fao_answers,
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
    return success(build_selection_catalog(), units=selection_catalog_units())


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
    description="Stores a structured lab report payload from the external report service, saves it to rapport_values.json, and records it in the user session for later report-based soil processing.",
)
def receive_lab_report(data: LabReport):
    return success(persist_lab_report(data.user_id, data.lab_report), units=lab_report_units())


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


@router.get(
    "/fao-decision/get-questions/{user_id}",
    response_model=ApiResponse,
    summary="Get the current FAO decision question",
    description="Uses the stored user session to return the next relevant FAO question and options, or the final selected FAO90 class if the decision is already complete.",
)
def get_fao_decision_questions(
    user_id: str,
    repos: Repositories = Depends(get_repositories),
):
    return success(build_fao_questions(user_id, repos), units=fao_decision_units())


@router.post(
    "/fao-decision/post-answers",
    response_model=ApiResponse,
    summary="Submit FAO decision answers",
    description="Stores new FAO decision answers for the current user session and returns either the next question or the final selected FAO90 class.",
)
def post_fao_decision_answers(
    data: FaoAnswersRequest,
    repos: Repositories = Depends(get_repositories),
):
    return success(submit_fao_answers(data.user_id, data.answers, repos), units=fao_decision_units())


@router.post("/soil/fao-decision", include_in_schema=False, response_model=ApiResponse)
def legacy_fao_decision(
    data: FaoDecisionRequest,
    repos: Repositories = Depends(get_repositories),
):
    return success(build_fao_decision(data.user_id, data.coord, data.answers, repos), units=fao_decision_units())


@router.get(
    "/global/crop-recommendations/{user_id}",
    response_model=ApiResponse,
    summary="Get global crop recommendations",
    description="Returns raw per-crop suitability and yield information from the global raster-based workflow using the stored user session. Ranking and sorting are expected to be handled by the frontend.",
)
def get_global_crop_recommendations(
    user_id: str,
    repos: Repositories = Depends(get_repositories),
):
    return success(build_global_crop_recommendations(user_id, repos), units=crop_recommendation_units())


@router.get(
    "/report/crop-recommendations/{user_id}",
    response_model=ApiResponse,
    summary="Get report-based crop recommendations",
    description="Returns raw per-crop suitability and yield information from the augmented report workflow using the stored user session. Ranking and sorting are expected to be handled by the frontend.",
)
def get_report_crop_recommendations(
    user_id: str,
    repos: Repositories = Depends(get_repositories),
):
    return success(build_report_crop_recommendations(user_id, repos), units=crop_recommendation_units())


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
    return success(build_calendar(data, repos), units=calendar_units())


@router.get(
    "/global/soil-constraint-factor/{user_id}",
    response_model=ApiResponse,
    summary="Get global soil constraint factors",
    description="Returns soil quality constraint factors from the global raster-based workflow using the stored user session.",
)
def get_global_soil_qualities_factor(
    user_id: str,
    repos: Repositories = Depends(get_repositories),
):
    return success(build_global_soil_quality_for_user(user_id, repos), units=soil_quality_units())


@router.get(
    "/report/soil-constraint-factor/{user_id}",
    response_model=ApiResponse,
    summary="Get report-based soil constraint factors",
    description="Returns report-augmented soil quality constraint factors for all crops using the stored user session.",
)
def get_report_soil_qualities_factor(
    user_id: str,
    repos: Repositories = Depends(get_repositories),
):
    return success(build_report_soil_quality_for_user(user_id, repos), units=soil_quality_units())


@router.get(
    "/crops-info",
    response_model=ApiResponse,
    summary="Get crop reference information",
    description="Returns EcoCrop-derived crop reference information used by the recommendation flows.",
)
def get_crops_info(repos: Repositories = Depends(get_repositories)):
    return success(build_crops_info(repos), units=crops_info_units())


@router.post(
    "/economics/suitability",
    response_model=ApiResponse,
    summary="Calculate crop economic suitability",
    description="Runs the PyAEZ-based economic suitability calculation from user-provided crop name, cost, yield, and farm-gate price.",
)
def get_economic_suitability(data: EconomicSuitabilityRequest):
    return success(
        build_economic_suitability(
            crop_name=data.crop_name,
            crop_cost=data.crop_cost,
            crop_yield=data.crop_yield,
            farm_price=data.farm_price,
        ),
        units=economic_units(),
    )


@router.get(
    "/crops-needs/{user_id}",
    response_model=ApiResponse,
    summary="Get crop ecological needs",
    description="Returns crop climate, terrain, and soil needs using the pH and texture classes already stored in the user session.",
)
def get_crop_needs(
    user_id: str,
    repos: Repositories = Depends(get_repositories),
):
    return success(build_crops_needs_for_user(user_id, repos), units=crop_needs_units())


@router.get(
    "/your-hwsd-soil-properties/{user_id}",
    response_model=ApiResponse,
    summary="Generate HWSD soil properties",
    description="Builds HWSD-based augmented soil layers from the stored user session and returns both JSON and the generated workbook path.",
)
def get_hwsd_soil_report(
    user_id: str,
    repos: Repositories = Depends(get_repositories),
):
    report = build_hwsd_soil_report_for_user(user_id, repos)
    return success(report["soil_properties"], units=soil_property_units(), output_path=report["output_path"])


@router.get(
    "/report/your-augmented-soil-properties/{user_id}",
    response_model=ApiResponse,
    summary="Generate report-augmented soil properties",
    description="Builds report-augmented soil layers using the stored user session and saved lab report, and returns both JSON and the generated workbook path.",
)
@router.get("/report/your-augmented_soil-properties/{user_id}", include_in_schema=False, response_model=ApiResponse)
def get_augmented_soil_report(
    user_id: str,
    repos: Repositories = Depends(get_repositories),
):
    report = build_augmented_soil_report_for_user(user_id, repos)
    return success(report["soil_properties"], units=soil_property_units(), output_path=report["output_path"])
