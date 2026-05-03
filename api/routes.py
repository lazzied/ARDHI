"""HTTP routes for the WCS backend, kept thin and delegated to service helpers."""
from typing import Any

from fastapi import APIRouter, Depends

from api.dependencies import Repositories, get_repositories
from api.models import ApiResponse, AugmentedSoilRequest, CropsNeedsRequest, EconomicSuitabilityRequest, FaoDecisionRequest, LabReport, OnboardingChoice, UserInput
from api.services import (
    build_augmented_soil_report,
    build_calendar,
    build_crops_info,
    build_crops_needs,
    build_economic_suitability,
    build_fao_decision,
    build_global_crop_recommendations,
    build_global_soil_quality,
    build_hwsd_soil_report,
    calendar_units,
    crop_needs_units,
    crop_recommendation_units,
    crops_info_units,
    economic_units,
    fao_decision_units,
    lab_report_units,
    persist_lab_report,
    build_report_crop_recommendations,
    build_report_soil_quality,
    build_selection_catalog,
    selection_catalog_units,
    soil_property_units,
    soil_quality_units,
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
    return success(build_global_soil_quality(data, repos), units=soil_quality_units())


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
    return success(build_report_soil_quality(data, crop_name, repos), units=soil_quality_units())


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
    return success(build_crops_needs(data.user_input, data.ph_level, data.texture_class, repos), units=crop_needs_units())


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
    return success(report["soil_properties"], units=soil_property_units(), output_path=report["output_path"])


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
    return success(report["soil_properties"], units=soil_property_units(), output_path=report["output_path"])
