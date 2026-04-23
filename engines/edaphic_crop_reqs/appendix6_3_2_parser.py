from __future__ import annotations

import pandas as pd
from collections import defaultdict
from typing import Dict, Iterator, List

from engines.edaphic_crop_reqs.constants import CROPS_RAINFED_SPRINKLER
from engines.edaphic_crop_reqs.models import AttributePair, InputLevel, RatingCurve, SoilCharacteristicsBlock
from engines.edaphic_crop_reqs.utils_functions import (
    attribute_pairs_to_df,
    generate_sq_df,
    parse_input_levels,
    parse_sq_labels,
    validate_and_get_row_idx,
    write_sq_df_to_csv,
)

# ---------------------------------------------------------------------------
# Sheet layout constants (0-based row / column indices)
# ---------------------------------------------------------------------------
INPUT_LEVEL_ROW = 2   # Excel row 3 — input level text
SQ_ROW          = 3   # Excel row 4 — SQ label
ATTRIBUTE_ROW   = 4   # Excel row 5 — texture class labels  (VAL row)
DATA_START_ROW  = 6   # Excel row 7 — first crop data row   (FCT matrix)

BLOCK_START_COL = 2   # first data column (0-based)
BLOCK_WIDTH     = 13  # columns per block

ATTRIBUTE_NAME  = "TXT"

CROP_IDX_COL= 0

# ---------------------------------------------------------------------------
# Block extraction
# ---------------------------------------------------------------------------

def extract_blocks(df: pd.DataFrame, crop_id: int, crops) -> List[SoilCharacteristicsBlock]:
    """
    Parse all 13-column blocks from the Appendix 6.3.2 DataFrame.

    Layout per block
    ----------------
    Row INPUT_LEVEL_ROW : input level text
    Row SQ_ROW          : SQ label(s)
    Row ATTRIBUTE_ROW   : texture class names  → thresholds
    Rows DATA_START_ROW+: penalty matrix; the row matching crop_id → penalties
    """
    if crop_id not in crops:
        raise ValueError(f"crop_id {crop_id} not found")

    crop_row_idx = validate_and_get_row_idx(df, CROP_IDX_COL, crop_id, crops)    

    blocks: List[SoilCharacteristicsBlock] = []
    total_cols = df.shape[1]

    col = BLOCK_START_COL
    while col + BLOCK_WIDTH <= total_cols:
        block_slice = df.iloc[:, col : col + BLOCK_WIDTH]

        # Row values for this block
        sq_text          = " ".join(str(v) for v in block_slice.iloc[SQ_ROW]          if pd.notna(v))
        input_level_text = " ".join(str(v) for v in block_slice.iloc[INPUT_LEVEL_ROW] if pd.notna(v))
        thresholds       = [str(v).strip() for v in block_slice.iloc[ATTRIBUTE_ROW].tolist() if pd.notna(v)]

        # Crop-specific penalty row (relative index within the FCT matrix)
        fct_matrix        = block_slice.iloc[DATA_START_ROW:]
        penalties_matrix  = fct_matrix.astype(float).values.tolist()
        penalties         = penalties_matrix[crop_row_idx - DATA_START_ROW]

        if not thresholds:
            col += BLOCK_WIDTH
            continue

        blocks.append(SoilCharacteristicsBlock(
            col_start      = col,
            col_end        = col + BLOCK_WIDTH,
            attribute_name = ATTRIBUTE_NAME,
            soil_qualities = parse_sq_labels(sq_text),
            input_levels   = parse_input_levels(input_level_text),
            penalties      = penalties,
            thresholds_row = thresholds,
        ))

        col += BLOCK_WIDTH

    return blocks


# ---------------------------------------------------------------------------
# Filtering functions
# ---------------------------------------------------------------------------

def filter_blocks_by_input_level(
    blocks:      List[SoilCharacteristicsBlock],
    input_level: InputLevel,
) -> Iterator[SoilCharacteristicsBlock]:
    for block in blocks:
        if input_level in block.input_levels:
            yield block


def filter_blocks_by_sq(
    blocks: List[SoilCharacteristicsBlock],
    sq_id:  int,
) -> Iterator[SoilCharacteristicsBlock]:
    for block in blocks:
        if f"SQ{sq_id}" in block.soil_qualities:
            yield block


# ---------------------------------------------------------------------------
# AttributePair builder
# ---------------------------------------------------------------------------

def build_attribute_pair(block: SoilCharacteristicsBlock, crop_id: int) -> AttributePair:
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
    csv_path:     str,
    crop_id:      int,
    crops:       dict[int, dict],
    input_level:  InputLevel,
    output_dir:   str  = ".",
    write_output: bool = False,
) -> Dict[str, pd.DataFrame]:
    """
    Full pipeline:
      1. Load CSV
      2. Extract all blocks for crop_id
      3. Filter blocks by input_level
      4. Group by SQ
      5. Build AttributePairs and DataFrames per SQ
      6. Optionally write one CSV per SQ (write_output=True)

    Parameters
    ----------
    write_output : write CSVs when True (default False so the aggregator
                   does not produce intermediate files)

    Returns a dict of {sq_label: DataFrame} for inspection.
    """
    df = pd.read_csv(csv_path, header=None)

    # Step 1: extract all blocks for this crop
    all_blocks = extract_blocks(df, crop_id,crops)

    # Step 2: filter by input level
    filtered_blocks = list(filter_blocks_by_input_level(all_blocks, input_level))

    # Step 3: group by SQ
    sq_groups: Dict[str, List[AttributePair]] = defaultdict(list)
    for block in filtered_blocks:
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
        csv_path     = "engines/edaphic_crop_reqs/appendixes/rainfed_sprinkler_appendix/csv_sheets/A6-3.2.csv",
        crop_id      = 4,
        crops        = CROPS_RAINFED_SPRINKLER,
        input_level  = InputLevel.INTERMEDIATE,
        output_dir   = "engines/edaphic_crop_reqs/results",
        write_output = True,
    )