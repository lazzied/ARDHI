"""Data models used across the edaphic parsers.

These models carry the raw block shape extracted from the appendix CSVs
(thresholds + penalties + metadata). They are framework-agnostic and
should not carry PyAEZ canonical names — those are applied at the parser
boundary through HEADER_TO_ATTRIBUTE / ATTR_ABBREV_MAP.
"""
from dataclasses import dataclass
from enum import Enum
from typing import List


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------

class InputLevel(Enum):
    LOW          = "low"
    INTERMEDIATE = "intermediate"
    HIGH         = "high"


# --------------------------------------------------------------------------
# Data models
# --------------------------------------------------------------------------

@dataclass
class RatingCurve:
    """A single crop-specific piecewise rating curve:
    thresholds[i] -> penalties[i]  (penalty is 0..100, 100 = no limitation).
    """
    crop_id:    int
    penalties:  List[float]
    thresholds: List[float]


@dataclass
class AttributePair:
    """Binds a canonical attribute name (e.g. 'OC', 'CECclay', 'SPH')
    to its rating curve for a specific crop."""
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
    thresholds_row: List            # raw crop values for the selected crop