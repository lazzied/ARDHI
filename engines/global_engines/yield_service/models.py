"""Yield score models and serializers for global and report recommendation flows."""
from dataclasses import dataclass, field
from typing import Optional

from engines.OCR_processing.models import InputLevel, WaterSupply


@dataclass
class CropYieldScore:
    """Yield result for one crop at one location under one input level."""
    crop_code: str
    crop_name: str
    
    input_level: InputLevel
    water_supply: WaterSupply
    
    actual_yield: Optional[float] = None    # kg(DW)/ha, 1km, primary metric
    potential_regional_yield: Optional[float] = None    # kg(DW)/ha, 10km, regional ceiling

    @property
    def has_yield(self) -> bool:
        """True if primary yield data exists and is positive."""
        return self.actual_yield is not None and self.actual_yield > 0

    @property
    def yield_gap(self) -> Optional[float]:
        """
        Difference between regional ceiling and local yield.
        Positive means there is untapped potential in the area.
        None if either layer is missing.
        """
        if self.actual_yield is not None and self.potential_regional_yield is not None:
            return self.potential_regional_yield - self.actual_yield
        return None

    @property
    def yield_gap_pct(self) -> Optional[float]:
        """Yield gap as a percentage of the regional ceiling."""
        if self.yield_gap is not None and self.potential_regional_yield and self.potential_regional_yield > 0:
            return (self.yield_gap / self.potential_regional_yield) * 100.0
        return None

    def to_dict(self) -> dict:
        return {
            "crop_code": self.crop_code,
            "crop_name": self.crop_name,
            "input_level": self.input_level,
            "water_supply": self.water_supply,
            "actual_yield": self.actual_yield,
            "potential_regional_yield": self.potential_regional_yield,
            "yield_gap": self.yield_gap,
            "yield_gap_pct": self.yield_gap_pct,
            "has_yield": self.has_yield,
        }


@dataclass
class RankingYield:
    
    scores: list[CropYieldScore] = field(default_factory=list)

    def scores_to_dict(self) -> list[dict]:
        return [score.to_dict() for score in self.scores]


    @property
    def ranked(self) -> list[CropYieldScore]:
        with_yield = [y for y in self.scores if y.has_yield]  
        return sorted(with_yield, key=lambda y: y.actual_yield, reverse=True)
    
    @property
    def ranked_by_gap(self) -> list[CropYieldScore]:
        """Rank by yield gap ascending — crops closest to their regional ceiling first."""
        with_gap = [y for y in self.scores if y.yield_gap is not None]
        return sorted(with_gap, key=lambda y: y.yield_gap)  # ascending

    @property
    def ranked_by_gap_pct(self) -> list[CropYieldScore]:
        """Rank by yield gap percentage ascending — crops closest to their regional ceiling first."""
        with_gap_pct = [y for y in self.scores if y.yield_gap_pct is not None]
        return sorted(with_gap_pct, key=lambda y: y.yield_gap_pct)  # ascending
    
    def top_n(self, n: int = 10) -> list[CropYieldScore]:
        """
        Return top N crops by yield.
        If n exceeds available crops, returns all.
        """
        ranked = self.ranked
        return ranked[:min(n, len(ranked))]
    
    def to_dict(self) -> dict:
        """
        Returns all crops sorted by actual yield descending.
        Use this for the main crop recommendation list — best performing crops first.

        Fields:
            ranked: list of crops with their yield scores, highest yield at index 0.
        """
        return {"ranked": [s.to_dict() for s in self.ranked]}

    def ratio_to_dict(self) -> dict:
        """
        Returns crops ranked by how close they are to their regional yield ceiling.
        Use this to identify crops with the least room for improvement (most optimized)
        or to highlight underperforming crops with high potential.

        Fields:
            ranked_by_gap     : sorted by absolute yield gap ascending (kg/ha) — 
                                crops with the smallest gap to their regional max come first.
            ranked_by_gap_pct : sorted by yield gap percentage ascending — 
                                same logic but normalized, useful for comparing across crop types.
        """
        return {
            "ranked_by_gap": [s.to_dict() for s in self.ranked_by_gap],
            "ranked_by_gap_pct": [s.to_dict() for s in self.ranked_by_gap_pct],
        }

YIELD_LAYERS = {
    "YLX": "RES05-YLX30AS",   # primary yield, 1km
    "YXX": "RES05-YXX",       # regional ceiling, 10km
}

@dataclass
class LayerDicts:
    ylx: dict #  - RES05-SXX30AS: continuous suitability index (0-10000) → primary ranking metric
    yxx: dict #  - RES05-SIX30AS: suitability class index (1-9) → human-readable class label
    """
                Uses two yield layers:
        - RES05-YLX30AS: output density in kg(DW)/ha (~1km) → primary yield metric
        - RES05-YXX:     average yield of best suitability class (~10km) → regional ceiling
    """
    
