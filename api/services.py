from fastapi import HTTPException

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


def _enum_options(enum_cls) -> list[dict]:
    return [{"value": member.value, "label": member.name.replace("_", " ").title()} for member in enum_cls]


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
    return {
        "suitability": crop_suitability.build_ranking_class().to_dict(),
        "yield": crop_yield.build_ranking_class().to_dict(),
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
        "suitability": ranking_suitability.ratio_to_dict(),
        "yield": ranking_yield.to_dict(),
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


def build_report_soil_quality(data: UserInput, crop_name: str, repos: Repositories) -> dict:
    scenario = ScenarioConfig(crop_name, data.input_level, data.water_supply, data.irrigation_type)
    return ReportSq(data.coord, scenario, repos.hwsd, repos.ardhi).build_sq_class().to_dict()


def build_crops_info(repos: Repositories) -> dict:
    return CropInfo(repos.ecocrop).data


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


def build_augmented_soil_report(data: UserInput, report, repos: Repositories) -> dict:
    resolved = resolve_user_input_context(data, repos)
    report_ops = ReportOperations(report)
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
