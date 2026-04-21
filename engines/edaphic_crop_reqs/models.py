
from dataclasses import dataclass, field
from enum import Enum
from typing import List



# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class InputLevel(Enum):
    LOW          = "low"
    INTERMEDIATE = "intermediate"
    HIGH         = "high"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RatingCurve:
    crop_id:    int
    penalties:  List[float]
    thresholds: List[float]


@dataclass
class AttributePair:
    attribute_name: str
    rating_curve:   RatingCurve


@dataclass
class SoilCharacteristicsBlock:
    """One 6-column slice of the appendix sheet."""
    col_start:      int             # 0-based
    col_end:        int             # 0-based exclusive
    attribute_name: str             # short name e.g. "OC"
    soil_qualities: List[str]       # e.g. ["SQ1"]
    input_levels:   List[InputLevel]
    penalties:      List[float]     # e.g. [100, 90, 70, 50, 30, 10]
    thresholds_row: List[float | str]     # raw crop values for the selected crop
    attribute_pairs: List[AttributePair] = field(default_factory=list)
