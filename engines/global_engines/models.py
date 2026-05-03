"""Generic dataclasses shared across global-engine outputs."""
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class InputManagement(Enum):
    HIGH = "HIM"
    LOW = "LIM"
    
@dataclass
class CropEcologicalRequirements:
    climate_needs: dict[str, dict[str, Any]] = field(default_factory=dict)
    terrain_needs: dict[str, dict[str, Any]] = field(default_factory=dict)
    soil_needs:    dict[str, dict[str, Any]] = field(default_factory=dict)  
    
@dataclass
class CropCalendarClass:
    crop_code: str
    planting_day: int
    growth_days: int
    planting_date: str
    harvest_date: str

    def to_dict(self) -> dict:
        return asdict(self)
        
class SoilQuality(Enum):
    NUTRIENT_AVAILABILITY       = "SQ1"
    NUTRIENT_RETENTION_CAPACITY = "SQ2"
    ROOTING_CONDITIONS          = "SQ3"
    OXYGEN_AVAILABILITY         = "SQ4"
    SALINITY_AND_SODICITY       = "SQ5"
    LIME_AND_GYPSUM             = "SQ6"
    WORKABILITY                 = "SQ7"
    
@dataclass
class SqClass:
    
    most_limiting_factor        : str
    nutrient_availability       : float
    nutrient_retention_capacity : float
    rooting_conditions          : float
    oxygen_availability         : float
    salinity_and_sodicity       : float
    lime_and_gypsum             : float
    workability                 : float
    
    def to_dict(self) -> dict:
        return asdict(self)
        

