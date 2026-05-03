"""Suitability score models and convenience serializers for global crop evaluation."""
from dataclasses import dataclass, field
from typing import Optional

from engines.OCR_processing.models import InputLevel, WaterSupply
from engines.global_engines.constants import SUITABILITY_CLASSES_SIX


SUITABILITY_LAYERS = {
        "SXX": "RES05-SXX30AS",
        "SIX": "RES05-SIX30AS",
        "SX2": "RES05-SX2",
    }

@dataclass
class CropSuitabilityScore:
    """Suitability result for one crop at one location under one input level."""
    crop_code: str
    crop_name: str
    
    input_level: InputLevel
    water_supply: WaterSupply
    
    suitability_index: Optional[int] = None #RES05-SXX30AS: continuous suitability index (0-10000) → primary ranking metric
    suitability_class: Optional[int] = None #RES05-SIX30AS: suitability class index (1-9) → human-readable class label
    regional_share: Optional[int] = None #RES05-SX2:     share of VS+S+MS land (0-10000, 10km) → regional overview

    @property
    def suitability_label(self) -> str:
        if self.suitability_class and self.suitability_class in SUITABILITY_CLASSES_SIX:
            return SUITABILITY_CLASSES_SIX[self.suitability_class]["label"]
        return "Unknown"

    @property
    def suitability_description(self) -> str:
        if self.suitability_class and self.suitability_class in SUITABILITY_CLASSES_SIX:
            return SUITABILITY_CLASSES_SIX[self.suitability_class]["description"]
        return ""

    @property
    def is_suitable(self) -> bool:
        return self.suitability_class is not None and 1 <= self.suitability_class <= 7 #useful for displayin

    @property
    def suitability_index_percentage(self) -> float:
        if self.suitability_index is not None and self.suitability_index >= 0: #useful for ranking
            return self.suitability_index / 100.0
        return 0.0

    @property
    def regional_share_percentage(self) -> float:
        if self.regional_share is not None and self.regional_share >= 0: #useful for ranking
            return self.regional_share / 100.0
        return 0.0
    
    def to_dict(self) -> dict:
        """
    Serialized crop suitability score for one crop at one location.

    Fields:
        crop_code                  : FAO crop identifier code
        crop_name                  : human-readable crop name
        input_level                : farming input level (low / medium / high)
        water_supply               : irrigation type (rainfed / irrigated)
        suitability_index          : raw suitability score (0–10000)
        suitability_index_percentage: suitability_index scaled to 0–100
        suitability_class          : suitability class index (1–9)
        suitability_label          : human-readable class label (e.g. "Very Suitable")
        suitability_description    : longer description of the suitability class
        regional_share             : share of suitable land in 10km area (0–10000)
        regional_share_percentage  : regional_share scaled to 0–100
        is_suitable                : True if suitability_class is between 1 and 7
    """
        return {
            "crop_code": self.crop_code,
            "crop_name": self.crop_name,
            "input_level": self.input_level,
            "water_supply": self.water_supply,
            "suitability_index": self.suitability_index,
            "suitability_index_percentage": self.suitability_index_percentage,
            "suitability_class": self.suitability_class,
            "suitability_label": self.suitability_label,
            "suitability_description": self.suitability_description,
            "regional_share": self.regional_share,
            "regional_share_percentage": self.regional_share_percentage,
            "is_suitable": self.is_suitable,
        }

@dataclass
class LayerDicts:
    """Bundle of the three per-crop tiff path dicts used during scoring.
        this for each map code; you get all the tiff paths for each : crop / input level / supply     
    """
    sxx: dict #  - RES05-SXX30AS: continuous suitability index (0-10000) → primary ranking metric
    six: dict #  - RES05-SIX30AS: suitability class index (1-9) → human-readable class label
    sx2: dict #  - RES05-SX2:     share of VS+S+MS land (0-10000, 10km) → regional overview

    
@dataclass
class RankingSuitability:
    
    scores: list[CropSuitabilityScore] = field(default_factory=list)

    def scores_to_dict(self) -> list[dict]:
        return [score.to_dict() for score in self.scores]

    @property
    def ranks_by_suitability(self) -> list:
        """All suitable crops sorted by suitability index descending."""
        suitable = [s for s in self.scores if s.is_suitable and s.suitability_index is not None]
        return sorted(suitable, key=lambda s: s.suitability_index, reverse=True)
    
    @property
    def ranks_by_region(self) -> list:
        """All suitable crops sorted by regional share (sx2) descending.

        Same suitability filter as `ranked`, but ordered by how widespread
        the crop's suitable land is in the surrounding 10km area rather
        than by the per-pixel suitability index. Crops without sx2 data
        are excluded.
        """
        
        suitable = [
            s for s in self.scores
            if s.is_suitable and s.regional_share is not None
        ]
        return sorted(suitable, key=lambda s: s.regional_share, reverse=True)

    def top_n(self, n: int = 10) -> list:
        """
        Return top N suitable crops.
        If n exceeds the number of suitable crops, return all suitable crops.
        """
        ranked = self.ranks_by_suitability
        return ranked[:min(n, len(ranked))]

    def to_dict(self) -> dict:
        """
        Serialized ranking result containing all suitable crops.

        Fields:
            ranks_by_suitability : crops sorted by suitability_index descending (best pixel-level fit first)
            ranks_by_region      : crops sorted by regional_share descending (most widespread first)

        Note:
            Frontend is responsible for limiting the number of displayed crops.
            Use ranks_by_suitability for precision-based recommendations.
            Use ranks_by_region for area-level overview.
        """
        return {
            "ranks_by_suitability": [s.to_dict() for s in self.ranks_by_suitability],
            "ranks_by_region": [s.to_dict() for s in self.ranks_by_region],
        }
