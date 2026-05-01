from dataclasses import dataclass, field
from typing import Optional

from engines.OCR_processing.models import InputLevel, WaterSupply
from engines.global_engines.constants import SUITABILITY_CLASSES_SIX


@dataclass
class CropScore:
    """Suitability result for one crop at one location under one input level."""
    crop_code: str
    crop_name: str
    input_level: InputLevel
    water_supply: WaterSupply
    sxx_index: Optional[int] = None
    six_class: Optional[int] = None
    sx2_share: Optional[int] = None

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
        return self.six_class is not None and 1 <= self.six_class <= 7

    @property
    def sxx_percentage(self) -> float:
        if self.sxx_index is not None and self.sxx_index >= 0:
            return self.sxx_index / 100.0
        return 0.0

    @property
    def sx2_percentage(self) -> float:
        if self.sx2_share is not None and self.sx2_share >= 0:
            return self.sx2_share / 100.0
        return 0.0


@dataclass
class Recommendation:
    """Complete recommendation result for a location."""
    lat: float
    lon: float
    input_level: str
    input_level_label: str
    scores: list[CropScore] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ranked(self) -> list[CropScore]:
        """All suitable crops sorted by suitability index descending."""
        suitable = [s for s in self.scores if s.is_suitable and s.sxx_index is not None]
        return sorted(suitable, key=lambda s: s.sxx_index, reverse=True)
    
    @property
    def ranked_by_region(self) -> list[CropScore]:
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

    def top_n(self, n: int = 10) -> list[CropScore]:
        """
        Return top N suitable crops.
        If n exceeds the number of suitable crops, return all suitable crops.
        """
        ranked = self.ranked
        return ranked[:min(n, len(ranked))]

    @property
    def not_suitable(self) -> list[CropScore]:
        return [s for s in self.scores if not s.is_suitable]

@dataclass
class CropYield:
    """Yield result for one crop at one location under one input level."""
    crop_code: str
    crop_name: str
    input_level: str
    ylx_yield: Optional[float] = None    # kg(DW)/ha, 1km, primary metric
    yxx_yield: Optional[float] = None    # kg(DW)/ha, 10km, regional ceiling

    @property
    def has_yield(self) -> bool:
        """True if primary yield data exists and is positive."""
        return self.ylx_yield is not None and self.ylx_yield > 0

    @property
    def yield_gap(self) -> Optional[float]:
        """
        Difference between regional ceiling and local yield.
        Positive means there is untapped potential in the area.
        None if either layer is missing.
        """
        if self.ylx_yield is not None and self.yxx_yield is not None:
            return self.yxx_yield - self.ylx_yield
        return None

    @property
    def yield_gap_pct(self) -> Optional[float]:
        """Yield gap as a percentage of the regional ceiling."""
        if self.yield_gap is not None and self.yxx_yield and self.yxx_yield > 0:
            return (self.yield_gap / self.yxx_yield) * 100.0
        return None


@dataclass
class YieldResult:
    """Complete yield result for a location under one input level."""
    lat: float
    lon: float
    input_level: str
    input_level_label: str
    yields: list[CropYield] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ranked(self) -> list[CropYield]:
        """All crops with yield data sorted by primary yield descending."""
        with_yield = [y for y in self.yields if y.has_yield]
        return sorted(with_yield, key=lambda y: y.ylx_yield, reverse=True)

    def top_n(self, n: int = 10) -> list[CropYield]:
        """
        Return top N crops by yield.
        If n exceeds available crops, returns all.
        """
        ranked = self.ranked
        return ranked[:min(n, len(ranked))]

    @property
    def no_yield(self) -> list[CropYield]:
        """Crops with no yield data at this location."""
        return [y for y in self.yields if not y.has_yield]