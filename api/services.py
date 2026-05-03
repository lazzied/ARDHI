"""Service-layer orchestration for API workflows, session updates, and engine calls."""
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException
import requests

from api.dependencies import Repositories
from api.models import UserInput
from api.session import user_sessions
from engines.OCR_processing.models import (
    InputLevel,
    IrrigationType,
    ScenarioConfig,
    Texture,
    WaterSupply,
    pH_level,
)
from engines.OCR_processing.suitability_service.suitability_rank import ReportCropSuitability
from engines.OCR_processing.yield_service.yield_rank import ReportCropYield
from engines.global_engines.crop_info_fetcher.crop_info import CropInfo
from engines.global_engines.crop_info_fetcher.crop_needs import build_crop_needs_report
from engines.global_engines.constants import STANDARD_UNITS, YIELD_UNIT_NOTE
from engines.global_engines.economics_engine import CropEconomicSuitability
from engines.global_engines.planting_harvesting import CropCalendar
from engines.global_engines.sq import GlobalSq, ReportSq
from engines.global_engines.suitability_service.suitability_engine import CropSuitability
from engines.global_engines.yield_service.yield_engine import CropYield
from engines.soil_FAO_decision import QUESTION_FLOW, classify_soil_dynamic
from engines.soil_properties_builder.hwsd2_prop.hwsd_prop_generator import (
    HWSDPropGenerator,
    augmented_layers_group_to_dict,
)
from engines.soil_properties_builder.report_augmentation.processing import ReportOperations, ReportPropGenerator
from raster.tiff_operations import get_smu_id_value


HWSD_SOIL_DIR = "engines/soil_properties_builder/output/results/hwsd_results"
HWSD_SOIL_FILENAME = "hwsd_soil"
REPORT_SOIL_DIR = "engines/soil_properties_builder/output/results/report_results"
REPORT_SOIL_FILENAME = "report_soil"
REPORT_INPUT_PATH = Path("engines/soil_properties_builder/report_augmentation/input/rapport_values.json")


@dataclass
class ExternalReportRequestContract:
    url: str
    method: str = "POST"
    headers: dict[str, str] = field(default_factory=dict)
    auth: tuple[str, str] | None = None
    json_payload: dict[str, Any] | None = None
    params: dict[str, Any] | None = None
    timeout_seconds: int = 30
    report_key: str | None = None


def _enum_options(enum_cls) -> list[dict]:
    return [{"value": member.value, "label": member.name.replace("_", " ").title()} for member in enum_cls]


def selection_catalog_units() -> dict:
    return {
        "user_input": {
            "input_level": "categorical",
            "water_supply": "categorical",
            "irrigation_type": "categorical",
        },
        "crop_needs": {
            "ph_level": "categorical",
            "texture_class": "categorical",
        },
        "fao_decision_questions": {
            "id": "identifier",
            "question": "text",
            "options": "categorical options",
        },
    }


def fao_decision_units() -> dict:
    return {
        "smu_id": "identifier",
        "selected_fao_90": "categorical",
        "candidates": {
            "fao_90": "categorical",
            "share": "% of SMU composition",
        },
        "question": {
            "id": "identifier",
            "question": "text",
            "options": "categorical options",
        },
        "surviving_candidates": {
            "probability": "0-1 score",
        },
    }


def crop_recommendation_units() -> dict:
    return {
        "suitability": {
            "crop_code": "identifier",
            "crop_name": "text",
            "input_level": "categorical",
            "water_supply": "categorical",
            "suitability_index": "0-10000 suitability index",
            "suitability_index_percentage": "%",
            "suitability_class": "class index (1-9)",
            "suitability_label": "categorical label",
            "suitability_description": "text",
            "regional_share": "0-10000 regional share index",
            "regional_share_percentage": "%",
            "is_suitable": "boolean",
        },
        "yield": {
            "crop_code": "identifier",
            "crop_name": "text",
            "input_level": "categorical",
            "water_supply": "categorical",
            "actual_yield": YIELD_UNIT_NOTE,
            "potential_regional_yield": YIELD_UNIT_NOTE,
            "yield_gap": YIELD_UNIT_NOTE,
            "yield_gap_pct": "%",
            "has_yield": "boolean",
        },
    }


def calendar_units() -> dict:
    return {
        "crop_code": "identifier",
        "planting_day": "day of year",
        "growth_days": "days",
        "planting_date": "calendar date (Month Day)",
        "harvest_date": "calendar date (Month Day)",
    }


def soil_quality_units() -> dict:
    return {
        "most_limiting_factor": "categorical",
        "nutrient_availability": "soil quality factor index",
        "nutrient_retention_capacity": "soil quality factor index",
        "rooting_conditions": "soil quality factor index",
        "oxygen_availability": "soil quality factor index",
        "salinity_and_sodicity": "soil quality factor index",
        "lime_and_gypsum": "soil quality factor index",
        "workability": "soil quality factor index",
    }


def crops_info_units() -> dict:
    return {
        "id": "identifier",
        "common_name": "text",
        "scientific_name": "text",
        "life_form": "categorical",
        "physiology": "categorical",
        "habit": "categorical",
        "category": "categorical",
        "life_span": "categorical",
        "plant_attributes": "text",
        "notes": "text",
        "production_system": "categorical",
        "crop_cycle_min": "days",
        "crop_cycle_max": "days",
        "cropping_system": "categorical",
        "subsystem": "categorical",
        "companion_species": "text",
        "mechanization_level": "categorical",
        "labour_intensity": "categorical",
    }


def crop_needs_units() -> dict:
    return {
        "climate_needs": {
            "temperature": "degrees C",
            "rainfall": "mm",
            "light_intensity": "categorical/relative scale",
        },
        "terrain_needs": {
            "altitude": "m",
            "latitude": "decimal degrees",
        },
        "soil_needs": {
            "pH": "pH",
            "soil_texture": "categorical",
            "soil_depth": "cm",
            "soil_fertility": "categorical",
            "soil_drainage": "categorical",
            "soil_salinity": "categorical",
            "edaphic_attributes": STANDARD_UNITS,
        },
    }


def soil_property_units() -> dict:
    return {
        "smu_id": "identifier",
        "TXT": "categorical",
        "DRG": "categorical",
        "GYP": "%",
        "GRC": "%",
        "CEC_clay": "cmol(+)/kg",
        "CEC_soil": "cmol(+)/kg",
        "OC": "% weight",
        "pH": "pH",
        "EC": "dS/m",
        "CCB": "%",
        "TEB": "cmol(+)/kg",
        "BS": "%",
        "ESP": "%",
        "OSD": "boolean",
        "SPR": "boolean",
        "VSP": "boolean",
        "SPH": "categorical",
        "RSD": "cm",
    }


def economic_units() -> dict:
    return {
        "crop_name": "text",
        "crop_cost": "TND/ha",
        "crop_yield": "t/ha",
        "farm_price": "TND/kg",
        "gross_revenue": "TND/ha",
        "net_revenue": "TND/ha",
    }


def lab_report_units() -> dict:
    return {
        "lab_report_saved": "boolean",
        "lab_report_path": "filesystem path",
        "external_report_url": "url",
        "external_report_method": "HTTP method",
    }


def build_selection_catalog() -> dict:
    return {
        "user_input": {
            "input_level": _enum_options(InputLevel),
            "water_supply": _enum_options(WaterSupply),
            "irrigation_type": _enum_options(IrrigationType),
        },
        "crop_needs": {
            "ph_level": _enum_options(pH_level),
            "texture_class": _enum_options(Texture),
        },
        "fao_decision_questions": [
            {
                "id": question.id,
                "question": question.question,
                "options": list(question.options),
            }
            for question in QUESTION_FLOW
        ],
    }


def get_session_or_404(user_id: str) -> dict:
    data = user_sessions.get(user_id)
    if not data:
        raise HTTPException(status_code=404, detail="No session data found")
    return data


def get_user_input_from_session(user_id: str) -> UserInput:
    session = get_session_or_404(user_id)
    return UserInput.model_validate(session)


def _normalize_report_payload(report_payload):
    if isinstance(report_payload, str):
        return json.loads(report_payload)
    return report_payload


def persist_lab_report(user_id: str, report_payload) -> dict:
    normalized_report = _normalize_report_payload(report_payload)
    REPORT_INPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_INPUT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(normalized_report, handle, ensure_ascii=False, indent=2)

    session = user_sessions.get(user_id, {})
    session["lab_report"] = normalized_report
    session["lab_report_exists"] = True
    session["lab_report_path"] = str(REPORT_INPUT_PATH)
    user_sessions[user_id] = session
    return {
        "lab_report_path": str(REPORT_INPUT_PATH),
        "lab_report_saved": True,
    }


def fetch_external_report_payload(
    contract: ExternalReportRequestContract,
    request_overrides: dict[str, Any] | None = None,
) -> dict | list:
    request_kwargs: dict[str, Any] = {
        "method": contract.method.upper(),
        "url": contract.url,
        "headers": contract.headers or None,
        "auth": contract.auth,
        "params": contract.params,
        "json": contract.json_payload,
        "timeout": contract.timeout_seconds,
    }
    if request_overrides:
        request_kwargs.update(request_overrides)

    response = requests.request(**request_kwargs)
    response.raise_for_status()
    payload = response.json()

    if contract.report_key is not None:
        try:
            payload = payload[contract.report_key]
        except (KeyError, TypeError) as exc:
            raise ValueError(
                f"External report payload did not include report_key '{contract.report_key}'"
            ) from exc

    if not isinstance(payload, (dict, list)):
        raise ValueError("External report payload must resolve to a dict or list")

    return payload


def fetch_and_persist_external_lab_report(
    user_id: str,
    contract: ExternalReportRequestContract,
    request_overrides: dict[str, Any] | None = None,
) -> dict:
    report_payload = fetch_external_report_payload(contract, request_overrides=request_overrides)
    result = persist_lab_report(user_id, report_payload)
    result["external_report_url"] = contract.url
    result["external_report_method"] = contract.method.upper()
    return result


def resolve_smu_id(coord: tuple[float, float]) -> int:
    smu_id = get_smu_id_value(coord)
    if smu_id is None:
        raise ValueError(f"No SMU found for coordinates {coord}")
    return smu_id


def get_fao_candidates_for_coord(coord: tuple[float, float], repos: Repositories) -> dict:
    smu_id = resolve_smu_id(coord)
    candidates = repos.hwsd.get_fao_90_candidates(smu_id)
    if not candidates:
        raise ValueError(f"No FAO90 classes found for SMU {smu_id}")
    return {
        "smu_id": smu_id,
        "candidates": candidates,
    }


def _top_fao_class(candidates: list[dict]) -> str:
    if not candidates:
        raise ValueError("No FAO90 candidates available")
    return candidates[0]["fao_90"]


def resolve_user_input_context(data: UserInput, repos: Repositories) -> UserInput:
    smu_id = data.smu_id or resolve_smu_id(data.coord)
    fao_90_class = data.fao_90_class
    if fao_90_class is None:
        candidates = repos.hwsd.get_fao_90_candidates(smu_id)
        fao_90_class = _top_fao_class(candidates)
    return data.model_copy(update={"smu_id": smu_id, "fao_90_class": fao_90_class})


def store_user_input(data: UserInput, repos: Repositories) -> None:
    resolved = resolve_user_input_context(data, repos)
    session = user_sessions.get(resolved.user_id, {})
    session.update(resolved.model_dump())
    user_sessions[resolved.user_id] = session


def _store_fao_decision_state(
    user_id: str,
    coord: tuple[float, float],
    smu_id: int,
    candidates: list[dict],
    answers: dict[str, str],
    selected_fao_90: str | None = None,
) -> None:
    session = user_sessions.get(user_id, {})
    session.update(
        {
            "coord": coord,
            "smu_id": smu_id,
            "fao_90_candidates": candidates,
            "answers": answers,
        }
    )
    if selected_fao_90 is not None:
        session["fao_90_class"] = selected_fao_90
    user_sessions[user_id] = session


def build_global_crop_recommendations(user_id: str, repos: Repositories) -> dict:
    data = get_session_or_404(user_id)
    crop_suitability = CropSuitability(repos.ardhi, data["input_level"], data["water_supply"], data["coord"])
    crop_yield = CropYield(
        repos.ardhi,
        input_level=data["input_level"],
        water_supply=data["water_supply"],
        coord=data["coord"],
    )
    suitability_scores = crop_suitability.build_ranking_class()
    yield_scores = crop_yield.build_ranking_class()
    return {
        "suitability": suitability_scores.scores_to_dict(),
        "yield": yield_scores.scores_to_dict(),
    }


def build_report_crop_recommendations(user_id: str, repos: Repositories) -> dict:
    data = get_session_or_404(user_id)
    ranking_yield = ReportCropYield(
        repos.hwsd,
        repos.ardhi,
        data["input_level"],
        data["water_supply"],
        data["coord"],
    ).build_ranking_class()
    ranking_suitability = ReportCropSuitability(ranking_yield).build_ranking_class()
    return {
        "suitability": ranking_suitability.scores_to_dict(),
        "yield": ranking_yield.scores_to_dict(),
    }


def build_calendar(data: UserInput, repos: Repositories) -> list[dict]:
    calendar = CropCalendar(
        repo=repos.ardhi,
        coord=data.coord,
        input_level=data.input_level,
        water_supply=data.water_supply,
    )
    return [item.to_dict() for item in calendar.crop_calendar_class_factory()]


def build_global_soil_quality(data: UserInput, repos: Repositories) -> dict:
    return GlobalSq(
        ardhi_repo=repos.ardhi,
        management=data.input_management,
        coord=data.coord,
    ).build_sq_class().to_dict()


def build_global_soil_quality_for_user(user_id: str, repos: Repositories) -> dict:
    return build_global_soil_quality(get_user_input_from_session(user_id), repos)


def build_report_soil_quality_for_user(user_id: str, repos: Repositories) -> dict:
    data = get_user_input_from_session(user_id)
    soil_quality_by_crop = {}
    for crop_name in ReportCropYield.build_crop_names().values():
        scenario = ScenarioConfig(crop_name.lower(), data.input_level, data.water_supply, data.irrigation_type)
        try:
            soil_quality_by_crop[crop_name] = ReportSq(data.coord, scenario, repos.hwsd, repos.ardhi).build_sq_class().to_dict()
        except ValueError:
            continue
        except FileNotFoundError:
            continue
    return soil_quality_by_crop


def build_crops_info(repos: Repositories) -> dict:
    return CropInfo(repos.ecocrop).data


def build_economic_suitability(
    crop_name: str,
    crop_cost: float,
    crop_yield: float,
    farm_price: float,
) -> dict:
    economics = CropEconomicSuitability(
        crop_name=crop_name,
        crop_cost=crop_cost,
        crop_yield=crop_yield,
        farm_price=farm_price,
    )
    gross_revenue = farm_price * 1000 * crop_yield
    return {
        "crop_name": crop_name,
        "crop_cost": crop_cost,
        "crop_yield": crop_yield,
        "farm_price": farm_price,
        "gross_revenue": gross_revenue,
        "net_revenue": economics.net_revenue,
        "units": {
            "crop_cost": "TND/ha",
            "crop_yield": "t/ha",
            "farm_price": "TND/kg",
            "gross_revenue": "TND/ha",
            "net_revenue": "TND/ha",
        },
    }


def build_crops_needs(
    data: UserInput,
    ph_level: pH_level,
    texture_class: Texture,
    repos: Repositories,
) -> dict:
    report = build_crop_needs_report(
        repos.ardhi,
        repos.ecocrop,
        data.input_level,
        data.water_supply,
        ph_level,
        texture_class,
    )
    return {
        crop_name: {
            "climate_needs": needs.climate_needs,
            "terrain_needs": needs.terrain_needs,
            "soil_needs": needs.soil_needs,
        }
        for crop_name, needs in report.items()
    }


def build_crops_needs_for_user(user_id: str, repos: Repositories) -> dict:
    data = get_user_input_from_session(user_id)
    if data.ph_level is None or data.texture_class is None:
        raise HTTPException(
            status_code=400,
            detail="ph_level and texture_class must be stored in the user session before requesting crops-needs",
        )
    return build_crops_needs(data, data.ph_level, data.texture_class, repos)


def build_hwsd_soil_report(data: UserInput, repos: Repositories) -> dict:
    resolved = resolve_user_input_context(data, repos)
    generator = HWSDPropGenerator(
        resolved.smu_id,
        resolved.fao_90_class,
        repos.hwsd,
        HWSD_SOIL_DIR,
        HWSD_SOIL_FILENAME,
    )
    group = generator.build_augmented_layers()
    output_path = generator.layers_orchestrator()
    return {
        "soil_properties": augmented_layers_group_to_dict(group),
        "output_path": output_path,
    }


def build_hwsd_soil_report_for_user(user_id: str, repos: Repositories) -> dict:
    return build_hwsd_soil_report(get_user_input_from_session(user_id), repos)


def build_augmented_soil_report(data: UserInput, report, repos: Repositories) -> dict:
    resolved = resolve_user_input_context(data, repos)
    report_input = report
    if report_input is None:
        session = user_sessions.get(resolved.user_id, {})
        report_input = session.get("lab_report_path", str(REPORT_INPUT_PATH))
    report_ops = ReportOperations(report_input)
    hwsd_generator = HWSDPropGenerator(
        resolved.smu_id,
        resolved.fao_90_class,
        repos.hwsd,
        REPORT_SOIL_DIR,
        REPORT_SOIL_FILENAME,
    )
    report_generator = ReportPropGenerator(
        smu_id=resolved.smu_id,
        fao_90_class=resolved.fao_90_class,
        report_ops=report_ops,
        hwsd_repo=repos.hwsd,
        hwsd_prop_generator=hwsd_generator,
        output_dir=REPORT_SOIL_DIR,
        filename=REPORT_SOIL_FILENAME,
    )
    group = report_generator.build_augmented_layers()
    output_path = report_generator.layers_orchestrator()
    return {
        "soil_properties": augmented_layers_group_to_dict(group),
        "output_path": output_path,
    }


def build_augmented_soil_report_for_user(user_id: str, repos: Repositories) -> dict:
    return build_augmented_soil_report(get_user_input_from_session(user_id), None, repos)


def prepare_external_report_contract(
    url: str,
    auth: tuple[str, str] | None = None,
    request_contract: dict[str, Any] | None = None,
) -> ExternalReportRequestContract:
    request_contract = request_contract or {}
    return ExternalReportRequestContract(
        url=url,
        method=request_contract.get("method", "POST"),
        headers=request_contract.get("headers", {}),
        auth=auth if auth is not None else request_contract.get("auth"),
        json_payload=request_contract.get("json_payload"),
        params=request_contract.get("params"),
        timeout_seconds=request_contract.get("timeout_seconds", 30),
        report_key=request_contract.get("report_key"),
    )


def build_fao_decision(user_id: str, coord: tuple[float, float], answers: dict[str, str], repos: Repositories) -> dict:
    fao_context = get_fao_candidates_for_coord(coord, repos)
    smu_id = fao_context["smu_id"]
    candidates = fao_context["candidates"]

    if len(candidates) == 1:
        selected_fao_90 = candidates[0]["fao_90"]
        _store_fao_decision_state(user_id, coord, smu_id, candidates, answers, selected_fao_90)
        return {
            "status": "complete",
            "smu_id": smu_id,
            "selected_fao_90": selected_fao_90,
            "candidates": candidates,
            "decision": {
                "reason": "Only one FAO90 class is present for this SMU.",
            },
        }

    smu_input = {item["fao_90"]: item["share"] / 100.0 for item in candidates}
    result = classify_soil_dynamic(smu_input, answers)
    result["smu_id"] = smu_id
    result["candidates"] = candidates

    if result["status"] == "complete":
        result["selected_fao_90"] = result.pop("selected_soil", None)
        _store_fao_decision_state(
            user_id,
            coord,
            smu_id,
            candidates,
            answers,
            result["selected_fao_90"],
        )
    else:
        _store_fao_decision_state(user_id, coord, smu_id, candidates, answers)

    return result


def build_fao_questions(user_id: str, repos: Repositories) -> dict:
    data = get_user_input_from_session(user_id)
    session = get_session_or_404(user_id)
    answers = session.get("answers", {})
    return build_fao_decision(user_id, data.coord, answers, repos)


def submit_fao_answers(user_id: str, answers: dict[str, str], repos: Repositories) -> dict:
    data = get_user_input_from_session(user_id)
    session = get_session_or_404(user_id)
    merged_answers = dict(session.get("answers", {}))
    merged_answers.update(answers)
    return build_fao_decision(user_id, data.coord, merged_answers, repos)
