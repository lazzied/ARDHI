"""Parser for one appendix source used to build edaphic crop requirement tables."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterator, List

import pandas as pd

from engines.edaphic_crop_reqs.constants import CROPS_RAINFED_SPRINKLER
from engines.edaphic_crop_reqs.models import (AttributePair, InputLevel, RatingCurve, SoilCharacteristicsBlock,)
from engines.edaphic_crop_reqs.utils_functions import (
    attribute_pairs_to_df,
    generate_sq_df,
    normalize_categorical_label,
    validate_and_get_row_idx,
    write_sq_df_to_csv,
)


# ---------------------------------------------------------------------------
# Sheet layout constants (0-based row / column indices)
# ---------------------------------------------------------------------------
SHARE_ROW       = 3   # applicability share (%)
ATTRIBUTE_ROW   = 4   # soil phase names  (VAL row)
DATA_START_ROW  = 6

ATTRIBUTE_NAME  = "SPH"
CROP_IDX_COL    = 0

# GAEZ "not applicable" sentinel that shows up in some columns of A6-3.4.
# It must NOT be treated as a real penalty; treated as 100 (no limitation).
SENTINEL_NOT_APPLICABLE = -999

# Irregular column ranges per SQ (0-based, inclusive on both ends).
SQ_COLUMN_RANGES: Dict[str, tuple[int, int]] = {
    "SQ3": (2,  28),
    "SQ4": (29, 44),
    "SQ5": (45, 47),
    "SQ6": (48, 49),
    "SQ7": (50, 76),
}


# ---------------------------------------------------------------------------
# Extended block model — carries per-phase applicability shares
# ---------------------------------------------------------------------------

@dataclass
class SoilPhaseBlock(SoilCharacteristicsBlock):
    shares: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Block extraction
# ---------------------------------------------------------------------------

def extract_blocks(
    df:          pd.DataFrame,
    crop_id:     int,
    input_level: InputLevel,
    crops:       dict[int, dict],
) -> List[SoilPhaseBlock]:
    """One SoilPhaseBlock per SQ. Phase-name labels are lowercased so the
    output indexes the augmentation module's canonical phase-token sets."""
    crop_row_idx = validate_and_get_row_idx(df, CROP_IDX_COL, crop_id, crops)

    blocks: List[SoilPhaseBlock] = []

    for sq_label, (start, end) in SQ_COLUMN_RANGES.items():
        if start >= df.shape[1]:
            continue
        actual_end  = min(end, df.shape[1] - 1)
        block_slice = df.iloc[:, start : actual_end + 1]

        thresholds = [
            normalize_categorical_label(v)
            for v in block_slice.iloc[ATTRIBUTE_ROW].fillna("").tolist()
        ]
        shares = (
            block_slice.iloc[SHARE_ROW]
            .fillna("").astype(str).str.strip().tolist()
        )
        penalties = (
            pd.to_numeric(df.iloc[crop_row_idx, start : actual_end + 1], errors="coerce")
            .fillna(100.0)
            .replace(SENTINEL_NOT_APPLICABLE, 100.0)
            .tolist()
        )

        # Drop columns where no phase name is present (after normalization).
        valid_thresholds, valid_penalties, valid_shares = [], [], []
        for t, p, s in zip(thresholds, penalties, shares):
            if t:
                valid_thresholds.append(t)
                valid_penalties.append(p)
                valid_shares.append(s)

        if not valid_thresholds:
            continue

        blocks.append(SoilPhaseBlock(
            col_start      = start,
            col_end        = actual_end,
            attribute_name = ATTRIBUTE_NAME,
            soil_qualities = [sq_label],
            input_levels   = [input_level],
            penalties      = valid_penalties,
            thresholds_row = valid_thresholds,
            shares         = valid_shares,
        ))

    return blocks


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def filter_blocks_by_input_level(
    blocks:      List[SoilPhaseBlock],
    input_level: InputLevel,
) -> Iterator[SoilPhaseBlock]:
    for block in blocks:
        if input_level in block.input_levels:
            yield block


def filter_blocks_by_sq(
    blocks: List[SoilPhaseBlock],
    sq_id:  int,
) -> Iterator[SoilPhaseBlock]:
    for block in blocks:
        if f"SQ{sq_id}" in block.soil_qualities:
            yield block


def build_attribute_pair(block: SoilPhaseBlock, crop_id: int) -> AttributePair:
    curve = RatingCurve(
        crop_id    = crop_id,
        penalties  = block.penalties,
        thresholds = block.thresholds_row,
    )
    return AttributePair(attribute_name=block.attribute_name, rating_curve=curve)


def run_pipeline(
    crops:        dict[int, dict],
    csv_path:     str,
    crop_id:      int,
    input_level:  InputLevel,
    output_dir:   str  = ".",
    write_output: bool = False,
) -> Dict[str, pd.DataFrame]:
    """SPH thresholds emitted in canonical lowercase. Per-phase applicability
    shares are preserved on each SoilPhaseBlock for downstream weighted-penalty
    calculations (no schema impact on the val/fct rows)."""
    df = pd.read_csv(csv_path, header=None)

    all_blocks = extract_blocks(df, crop_id, input_level, crops)

    sq_groups: Dict[str, List[AttributePair]] = defaultdict(list)
    for block in all_blocks:
        pair = build_attribute_pair(block, crop_id)
        for sq in block.soil_qualities:
            sq_groups[sq].append(pair)

    result: Dict[str, pd.DataFrame] = {}
    for sq_label, pairs in sorted(sq_groups.items()):
        sq_df = generate_sq_df([attribute_pairs_to_df([p]) for p in pairs])
        if write_output:
            write_sq_df_to_csv(sq_df, f"{output_dir}/{sq_label}.csv")
            print(f"Written {sq_label}.csv  ({len(pairs)} attributes)")
        result[sq_label] = sq_df

    return result


if __name__ == "__main__":
    results = run_pipeline(
        crops        = CROPS_RAINFED_SPRINKLER,
        csv_path     = "engines/edaphic_crop_reqs/appendixes/rainfed_sprinkler_appendix/csv_sheets/A6-3.4.csv",
        input_level  = InputLevel.HIGH,
        crop_id      = 4,
        output_dir   = "engines/edaphic_crop_reqs/results",
        write_output = True,
    )
"""Parser for one appendix source used to build edaphic crop requirement tables."""
