from typing import Any, Optional

from pydantic import BaseModel, Field

from engines.OCR_processing.models import InputLevel, IrrigationType, Texture, WaterSupply, pH_level
from engines.global_engines.models import InputManagement


class OnboardingChoice(BaseModel):
    user_id: str = Field(description="Frontend-generated unique user/session identifier.")
    lab_report_exists: bool = Field(description="Whether the user already has a lab soil report to upload.")


class LabReport(BaseModel):
    user_id: str = Field(description="Frontend-generated unique user/session identifier.")
    lab_report: dict = Field(description="Structured lab report payload captured by the frontend or OCR flow.")


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
    lab_report_exists: bool = Field(default=False, description="Whether a lab report is available for this user.")
    lab_report: Optional[dict] = Field(default=None, description="Optional stored lab report payload.")
    smu_id: Optional[int] = Field(default=None, description="Resolved automatically from coord; not required from frontend.")
    fao_90_class: Optional[str] = Field(
        default=None,
        description="Resolved automatically from the FAO decision flow; not required from frontend.",
    )

    @property
    def input_management(self) -> InputManagement:
        return InputManagement.HIGH if self.input_level == InputLevel.HIGH else InputManagement.LOW


class CropsNeedsRequest(BaseModel):
    user_input: UserInput = Field(description="Base user context used to fetch crop needs.")
    ph_level: pH_level = Field(description="Soil pH class selection.")
    texture_class: Texture = Field(description="Soil texture class selection.")


class AugmentedSoilRequest(BaseModel):
    user_input: UserInput = Field(description="Base user context for report augmentation.")
    report: str | list[dict[str, Any]] | dict[str, Any] = Field(
        description="Lab report input as raw JSON string, list of attribute rows, or object payload.",
    )


class FaoDecisionRequest(BaseModel):
    user_id: str = Field(description="Frontend-generated unique user/session identifier.")
    coord: tuple[float, float] = Field(description="User location as [latitude, longitude].")
    answers: dict[str, str] = Field(
        default_factory=dict,
        description="Current FAO decision answers as {question_id: selected_option}.",
    )


class ApiResponse(BaseModel):
    status: str = Field(default="success", description="High-level request status.")
    data: Any | None = Field(default=None, description="Endpoint-specific payload.")
    output_path: str | None = Field(default=None, description="Generated file path when the endpoint creates an output file.")
