from dataclasses import dataclass, field
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
        return {
            "crop_code": self.crop_code,
            "planting_day": self.planting_day,
            "growth_days": self.growth_days,
            "planting_date": self.planting_date,
            "harvest_date": self.harvest_date,
        }
        
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
        
        return {
            "most_limiting_factor"       : self.most_limiting_factor,
            "nutrient_availability"      : self.nutrient_availability,
            "nutrient_retention_capacity": self.nutrient_retention_capacity,
            "rooting_conditions"         : self.rooting_conditions,
            "oxygen_availability"        : self.oxygen_availability,
            "salinity_and_sodicity"      : self.salinity_and_sodicity,
            "lime_and_gypsum"            : self.lime_and_gypsum,
            "workability"                : self.workability,
        }
        

