from __future__ import annotations
import re
import pandas as pd
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterator, List
from engines.edaphic_crop_reqs.models import AttributePair, InputLevel, RatingCurve, SoilCharacteristicsBlock
from engines.edaphic_crop_reqs.utils_functions import (
    attribute_pairs_to_df,
    generate_sq_df,
    write_sq_df_to_csv,
)


# ---------------------------------------------------------------------------
# Sheet layout constants (0-based row / column indices)
# ---------------------------------------------------------------------------
# Note: input level has no fixed row — it is extracted from the table title
# by _parse_input_level(), which scans rows dynamically.
SHARE_ROW       = 3   # Excel row 4 — applicability share (%)
ATTRIBUTE_ROW   = 4   # Excel row 5 — soil phase names  (VAL row)
DATA_START_ROW  = 6   # Excel row 7 — first crop data row

ATTRIBUTE_NAME  = "SPH"

# Irregular column ranges per SQ (0-based, inclusive on both ends).
# Slicing uses df.iloc[:, start : end + 1], so end is the last included column.
SQ_COLUMN_RANGES: Dict[str, tuple[int, int]] = {
    "SQ3": (2,  28),
    "SQ4": (29, 44),
    "SQ5": (45, 47),
    "SQ6": (48, 49),
    "SQ7": (50, 76),
}


# ---------------------------------------------------------------------------
# Extended block model — carries the share metadata specific to Appendix 6.3.4
# ---------------------------------------------------------------------------

@dataclass
class SoilPhaseBlock(SoilCharacteristicsBlock):
    """SoilCharacteristicsBlock extended with per-phase applicability shares."""
    shares: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------



def _resolve_crop_row(df: pd.DataFrame, crop_id: int) -> int:
    """Return the 0-based row index for *crop_id*, handling float/string IDs."""
    id_col = pd.to_numeric(df.iloc[:, 0], errors="coerce")
    matches = df.index[id_col == crop_id].tolist()
    if not matches:
        raise ValueError(f"crop_id {crop_id} not found in appendix 6.3.4")
    return matches[0]


# ---------------------------------------------------------------------------
# Block extraction
# ---------------------------------------------------------------------------

def extract_blocks(df: pd.DataFrame, crop_id: int,input_level: InputLevel) -> List[SoilPhaseBlock]:
    """
    Parse one SoilPhaseBlock per SQ from the Appendix 6.3.4 DataFrame.

    Layout (irregular column ranges defined in SQ_COLUMN_RANGES)
    ------------------------------------------------------------
    Row INPUT_LEVEL_ROW : single sheet-level input level text
    Row SHARE_ROW       : applicability share (%) per soil phase
    Row ATTRIBUTE_ROW   : soil phase names → thresholds
    Row crop_row_idx    : penalty values for the requested crop

    The input level is the same for every block (sheet-wide constant).
    Columns with no soil phase name are silently dropped.
    """
    crop_row_idx = _resolve_crop_row(df, crop_id)

    blocks: List[SoilPhaseBlock] = []

    for sq_label, (start, end) in SQ_COLUMN_RANGES.items():
        if start >= df.shape[1]:
            continue
        actual_end = min(end, df.shape[1] - 1)

        block_slice = df.iloc[:, start : actual_end + 1]

        thresholds = block_slice.iloc[ATTRIBUTE_ROW].fillna("").astype(str).str.strip().tolist()
        shares     = block_slice.iloc[SHARE_ROW].fillna("").astype(str).str.strip().tolist()
        penalties  = (
            pd.to_numeric(df.iloc[crop_row_idx, start : actual_end + 1], errors="coerce")
            .fillna(100.0)
            .tolist()
        )

        # Drop columns where no soil phase name is present
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
# Filtering functions
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


# ---------------------------------------------------------------------------
# AttributePair builder
# ---------------------------------------------------------------------------

def build_attribute_pair(block: SoilPhaseBlock, crop_id: int) -> AttributePair:
    curve = RatingCurve(
        crop_id    = crop_id,
        penalties  = block.penalties,
        thresholds = block.thresholds_row,
    )
    return AttributePair(attribute_name=block.attribute_name, rating_curve=curve)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    csv_path:    str,
    crop_id:     int,
    input_level:InputLevel,
    output_dir:  str  = ".",
    write_output: bool = False,
) -> Dict[str, pd.DataFrame]:
    """
    Full pipeline:
      1. Load CSV
      2. Extract all blocks for crop_id  (input level auto-detected from title)
      3. Group by SQ
      4. Build AttributePairs and DataFrames per SQ
      5. Optionally write one CSV per SQ (write_output=True)

    The input level is deduced automatically from the table title embedded in
    the CSV (e.g. "High Input Farming" → InputLevel.HIGH).  It does not need
    to be supplied by the caller.

    Parameters
    ----------
    write_output : write CSVs when True (default False so the aggregator
                   does not produce intermediate files)

    Returns a dict of {sq_label: DataFrame} for inspection.

    Note on shares
    --------------
    The applicability share (%) for each soil phase is preserved inside each
    SoilPhaseBlock.shares list.  The standard two-row output (SPH_val / SPH_fct)
    remains unchanged; the share data is available for future weighted-penalty
    calculations without any parser changes.
    """
    df = pd.read_csv(csv_path, header=None)

    # Step 1: extract all blocks for this crop (input level auto-detected inside)
    all_blocks = extract_blocks(df, crop_id,input_level)

    # Step 2: group by SQ
    sq_groups: Dict[str, List[AttributePair]] = defaultdict(list)
    for block in all_blocks:
        pair = build_attribute_pair(block, crop_id)
        for sq in block.soil_qualities:
            sq_groups[sq].append(pair)

    # Step 4: build one DataFrame per SQ and write CSV
    result: Dict[str, pd.DataFrame] = {}
    for sq_label, pairs in sorted(sq_groups.items()):
        sq_df = generate_sq_df([attribute_pairs_to_df([p]) for p in pairs])
        if write_output:
            write_sq_df_to_csv(sq_df, f"{output_dir}/{sq_label}.csv")
            print(f"Written {sq_label}.csv  ({len(pairs)} attributes)")
        result[sq_label] = sq_df

    return result

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    results = run_pipeline(
        csv_path     = "engines/edaphic_crop_reqs/appendixes/appendix6_3_4.csv",
        crop_id      = 4,
        output_dir   = "engines/edaphic_crop_reqs/results",
        write_output = True,
    )