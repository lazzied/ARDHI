"""Request and response models used by the public API."""
from typing import Any, List, Optional, Union

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
    lab_report: Union[dict, List[dict[str, Any]]] = Field(
        description="Structured lab report payload captured by the frontend or OCR flow."
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "sim1",
                    "lab_report": [
                        { "attribute": "pH", "iso_method": "NF EN ISO 10390 (2022)", "unit": "---", "value": 5 },
                        { "attribute": "Conductivité", "iso_method": "ISO 11265 (2025)", "unit": "mS/Cm", "value": 0.9 },
                        { "attribute": "Salinité", "iso_method": "ISO 11265 (2025)", "unit": "%", "value": 0.15 },
                        { "attribute": "Humidité", "iso_method": "MA ISO 11465 (2025)", "unit": "%", "value": 18.5 },
                        { "attribute": "Matière sèche", "iso_method": "MA ISO 11465 (2025)", "unit": "%", "value": 81.5 },
                        { "attribute": "Matière Organique", "iso_method": "RODIER (2009)", "unit": "%", "value": 2.4 },
                        { "attribute": "Azote total", "iso_method": "ISO 13878 (2020)", "unit": "%", "value": 0.18 },
                        { "attribute": "Rapport C/N", "iso_method": "RODIER (2009)", "unit": "---", "value": 11.5 },
                        { "attribute": "Souffre", "iso_method": "ISO 15178 (2000)", "unit": "%", "value": 0.02 },
                        { "attribute": "Taux de carbone", "iso_method": "ISO 10694 (2020)", "unit": "%", "value": 1.4 },
                        { "attribute": "Carbonates de Calcium", "iso_method": "ISO 10693 (2021)", "unit": "%", "value": 8.0 },
                        { "attribute": "Phosphore", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": 0.6 },
                        { "attribute": "Potassium", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": 1.8 },
                        { "attribute": "Magnésium", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": 0.9 },
                        { "attribute": "Calcium", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": 6.5 },
                        { "attribute": "Manganèse", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": 0.08 },
                        { "attribute": "Bore", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": 0.01 },
                        { "attribute": "Cuivre", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": 0.02 },
                        { "attribute": "Fer", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": 2.5 },
                        { "attribute": "Zinc", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": 0.03 },
                        { "attribute": "Molybdène", "iso_method": "ISO 11047 (2023)", "unit": "g/Kg MS", "value": 0.002 },
                        { "attribute": "Calcium échangeable", "iso_method": "ISO 11260 (2018)", "unit": "g/Kg MS", "value": 5.8 },
                        { "attribute": "Magnésium échangeable", "iso_method": "ISO 11260 (2018)", "unit": "g/Kg MS", "value": 1.1 },
                        { "attribute": "Potassium échangeable", "iso_method": "ISO 11260 (2018)", "unit": "g/Kg MS", "value": 0.35 },
                        { "attribute": "Phosphore échangeable", "iso_method": "ISO 11260 (2018)", "unit": "g/Kg MS", "value": 0.15 },
                        { "attribute": "Sodium échangeable", "iso_method": "ISO 11260 (2018)", "unit": "g/Kg MS", "value": 0.12 },
                        { "attribute": "Calcaire actif", "iso_method": "NF X 31-106 (2002)", "unit": "%", "value": 4.5 }
                    ]
                }
            ]
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
    
    lab_report: Optional[Union[dict, List[dict[str, Any]]]] = Field(
    default=None, 
    description="Optional stored lab report payload."
)
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
