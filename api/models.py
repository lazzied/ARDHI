"""Request and response models used by the public API."""
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from engines.OCR_processing.models import InputLevel, IrrigationType, Texture, WaterSupply, pH_level
from engines.global_engines.models import InputManagement


class OnboardingChoice(BaseModel):
    user_id: str = Field(description="Frontend-generated unique user/session identifier.")
    lab_report_exists: bool = Field(description="Whether the user already has a lab soil report to upload.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "sim1",
                "lab_report_exists": False,
            }
        }
    }


class LabReport(BaseModel):
    user_id: str = Field(description="Frontend-generated unique user/session identifier.")
    lab_report: dict | list[dict[str, Any]] = Field(
        description="Structured lab report payload captured by the frontend or OCR flow."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "sim1",
                "lab_report": [
                    {
                        "attribute": "pH",
                        "iso_method": "NF EN ISO 10390 (2022)",
                        "unit": "---",
                        "value": 5,
                    }
                ],
            }
        }
    }


class SubmitInputRequest(BaseModel):
    user_id: str = Field(description="Frontend-generated unique user/session identifier.")
    coord: tuple[float, float] = Field(description="User location as [latitude, longitude].")
    input_level: InputLevel = Field(description="Management/input level selected by the user.")
    water_supply: WaterSupply = Field(description="Water supply mode selected by the user.")
    irrigation_type: Optional[IrrigationType] = Field(
        default=None,
        description="Irrigation method when water_supply is irrigated.",
    )

    @model_validator(mode="after")
    def normalize_irrigation_type(self):
        if self.water_supply == WaterSupply.RAINFED:
            self.irrigation_type = None
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "sim1",
                "coord": [36.858096, 9.962084],
                "input_level": "low",
                "water_supply": "rainfed",
                "irrigation_type": None,
            }
        }
    }


class UserInput(BaseModel):
    user_id: str = Field(description="Frontend-generated unique user/session identifier.")
    coord: tuple[float, float] = Field(description="User location as [latitude, longitude].")
    input_level: InputLevel = Field(description="Management/input level selected by the user.")
    water_supply: WaterSupply = Field(description="Water supply mode selected by the user.")
    irrigation_type: Optional[IrrigationType] = Field(
        default=None,
        description="Irrigation method when water_supply is irrigated.",
    )
    answers: dict[str, str] = Field(
        default_factory=dict,
        description="Answered FAO decision questions as {question_id: selected_option}.",
    )
    needs_report: bool = Field(
        default=False,
        description="Whether the user selected the report-based workflow and expects a lab report payload from the external service.",
    )
    lab_report_exists: bool = Field(default=False, description="Whether a lab report is available for this user.")
    lab_report: Optional[dict] = Field(default=None, description="Optional stored lab report payload.")
    ph_level: Optional[pH_level] = Field(
        default=None,
        description="Optional soil pH class selection stored in session for crop-needs and related flows.",
    )
    texture_class: Optional[Texture] = Field(
        default=None,
        description="Optional soil texture class selection stored in session for crop-needs and related flows.",
    )
    smu_id: Optional[int] = Field(default=None, description="Resolved automatically from coord; not required from frontend.")
    fao_90_class: Optional[str] = Field(
        default=None,
        description="Resolved automatically from the FAO decision flow; not required from frontend.",
    )

    @property
    def input_management(self) -> InputManagement:
        return InputManagement.HIGH if self.input_level == InputLevel.HIGH else InputManagement.LOW


class FaoDecisionRequest(BaseModel):
    user_id: str = Field(description="Frontend-generated unique user/session identifier.")
    coord: tuple[float, float] = Field(description="User location as [latitude, longitude].")
    answers: dict[str, str] = Field(
        default_factory=dict,
        description="Current FAO decision answers as {question_id: selected_option}.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "sim1",
                "coord": [36.858096, 9.962084],
                "answers": {
                    "question1": "answer",
                    "question2": "answer",
                },
            }
        }
    }


class FaoAnswersRequest(BaseModel):
    user_id: str = Field(description="Frontend-generated unique user/session identifier.")
    answers: dict[str, str] = Field(
        default_factory=dict,
        description="Submitted FAO decision answers as {question_id: selected_option}.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "sim1",
                "answers": {
                    "What's the water situation here?": "Wet most of the year, marshy or boggy",
                    "When you dig down, what do you find?": "A proper soil with clear separate layers",
                },
            }
        }
    }


class EconomicSuitabilityRequest(BaseModel):
    crop_name: str = Field(description="Crop name, for example maize or wheat.")
    crop_cost: float = Field(description="Production cost in TND/ha.")
    crop_yield: float = Field(description="Expected crop yield in t/ha.")
    farm_price: float = Field(description="Farm-gate price in TND/kg.")


class ApiResponse(BaseModel):
    status: str = Field(default="success", description="High-level request status.")
    data: Any | None = Field(default=None, description="Endpoint-specific payload.")
