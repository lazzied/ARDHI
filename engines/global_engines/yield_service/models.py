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


@dataclass
class RankingYield:
    
    scores: list[CropYieldScore] = field(default_factory=list)


    @property
    def ranked(self) -> list[CropYieldScore]:
        with_yield = [y for y in self.scores if y.has_yield]  
        return sorted(with_yield, key=lambda y: y.actual_yield, reverse=True)

    def top_n(self, n: int = 10) -> list[CropYieldScore]:
        """
        Return top N crops by yield.
        If n exceeds available crops, returns all.
        """
        ranked = self.ranked
        return ranked[:min(n, len(ranked))]

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
    