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
        if self.six_class and self.six_class in SUITABILITY_CLASSES_SIX:
            return SUITABILITY_CLASSES_SIX[self.six_class]["label"]
        return "Unknown"

    @property
    def suitability_description(self) -> str:
        if self.six_class and self.six_class in SUITABILITY_CLASSES_SIX:
            return SUITABILITY_CLASSES_SIX[self.six_class]["description"]
        return ""

    @property
    def is_suitable(self) -> bool:
        return self.six_class is not None and 1 <= self.six_class <= 7 #useful for displayin

    @property
    def sxx_percentage(self) -> float:
        if self.sxx_index is not None and self.sxx_index >= 0: #useful for ranking
            return self.sxx_index / 100.0
        return 0.0

    @property
    def sx2_percentage(self) -> float:
        if self.sx2_share is not None and self.sx2_share >= 0: #useful for ranking
            return self.sx2_share / 100.0
        return 0.0

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

    @property
    def ranks_by_suitability(self) -> list[CropSuitabilityScore]:
        """All suitable crops sorted by suitability index descending."""
        suitable = [s for s in self.scores if s.is_suitable and s.sxx_index is not None]
        return sorted(suitable, key=lambda s: s.sxx_index, reverse=True)
    
    @property
    def ranks_by_region(self) -> list[CropSuitabilityScore]:
        """All suitable crops sorted by regional share (sx2) descending.

        Same suitability filter as `ranked`, but ordered by how widespread
        the crop's suitable land is in the surrounding 10km area rather
        than by the per-pixel suitability index. Crops without sx2 data
        are excluded.
        """
        suitable = [
            s for s in self.scores
            if s.is_suitable and s.sx2_share is not None
        ]
        return sorted(suitable, key=lambda s: s.sx2_share, reverse=True)

    def top_n(self, n: int = 10) -> list[CropSuitabilityScore]:
        """
        Return top N suitable crops.
        If n exceeds the number of suitable crops, return all suitable crops.
        """
        ranked = self.ranks_by_suitability
        return ranked[:min(n, len(ranked))]
