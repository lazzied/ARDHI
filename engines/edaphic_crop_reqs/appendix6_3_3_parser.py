from __future__ import annotations

import pandas as pd
from collections import defaultdict
from typing import Dict, Iterator, List

from engines.edaphic_crop_reqs.constants import CROPS
from engines.edaphic_crop_reqs.models import AttributePair, InputLevel, RatingCurve, SoilCharacteristicsBlock
from engines.edaphic_crop_reqs.utils_functions import (
    attribute_pairs_to_df,
    generate_sq_df,
    parse_input_levels,
    write_sq_df_to_csv,
)

# ---------------------------------------------------------------------------
# Sheet layout constants (0-based row / column indices)
# ---------------------------------------------------------------------------
INPUT_LEVEL_ROW    = 3   # Excel row 4 — input level text
TEXTURAL_GROUP_ROW = 4   # Excel row 5 — textural grouping label
ATTRIBUTE_ROW      = 5   # Excel row 6 — drainage class names  (VAL row)
DATA_START_ROW     = 7   # Excel row 8 — first crop data row

BLOCK_START_COL    = 2   # first data column (0-based)
BLOCK_WIDTH        = 7   # columns per block (7 drainage classes)

ATTRIBUTE_PREFIX   = "DRG"   # base name; suffixed with texture group
FIXED_SQ           = "SQ4"   # Appendix 6.3.3 always maps to SQ4


# ---------------------------------------------------------------------------
# Block extraction
# ---------------------------------------------------------------------------

def extract_blocks(df: pd.DataFrame, crop_id: int) -> List[SoilCharacteristicsBlock]:
    """
    Parse all 7-column blocks from the Appendix 6.3.3 DataFrame.

    Layout per block
    ----------------
    Row INPUT_LEVEL_ROW    : input level text
    Row TEXTURAL_GROUP_ROW : textural grouping  (Fine / Medium / Coarse textures)
    Row ATTRIBUTE_ROW      : drainage class names → thresholds
    Rows DATA_START_ROW+   : crop rating rows; row matching crop_id → penalties

    All blocks belong to the fixed soil quality FIXED_SQ ("SQ4").
    The attribute name is derived dynamically from the textural group label,
    e.g. "Fine textures" → "DRG_Fine".
    """
    if crop_id not in CROPS:
        raise ValueError(f"crop_id {crop_id} not found")

    crop_row_idx = CROPS[crop_id]["row"] - 1   # convert 1-based Excel row to 0-based

    blocks: List[SoilCharacteristicsBlock] = []
    total_cols = df.shape[1]

    col = BLOCK_START_COL
    while col + BLOCK_WIDTH <= total_cols:
        block_slice = df.iloc[:, col : col + BLOCK_WIDTH]

        # Row values for this block
        input_level_text = " ".join(
            block_slice.iloc[INPUT_LEVEL_ROW].dropna().astype(str)
        )
        group_text = " ".join(
            block_slice.iloc[TEXTURAL_GROUP_ROW].dropna().astype(str)
        )

        if not group_text or not input_level_text:
            col += BLOCK_WIDTH
            continue

        # Derive attribute name from textural group, e.g. "DRG_Fine"
        texture_label  = group_text.split()[0].capitalize()
        attribute_name = f"{ATTRIBUTE_PREFIX}_{texture_label}"

        thresholds = [str(v).strip() for v in block_slice.iloc[ATTRIBUTE_ROW].tolist()]
        penalties  = block_slice.iloc[crop_row_idx].astype(float).tolist()

        blocks.append(SoilCharacteristicsBlock(
            col_start      = col,
            col_end        = col + BLOCK_WIDTH,
            attribute_name = attribute_name,
            soil_qualities = [FIXED_SQ],
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
    csv_path:    str,
    crop_id:     int,
    input_level: InputLevel,
    output_dir:  str = ".",
) -> Dict[str, pd.DataFrame]:
    """
    Full pipeline:
      1. Load CSV
      2. Extract all blocks for crop_id
      3. Filter blocks by input_level
      4. Group by SQ  (always SQ4 for this appendix)
      5. Build AttributePairs and DataFrames per SQ
      6. Write one CSV per SQ

    Returns a dict of {sq_label: DataFrame} for inspection.
    """
    df = pd.read_csv(csv_path, header=None)

    # Step 1: extract all blocks for this crop
    all_blocks = extract_blocks(df, crop_id)

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
        write_sq_df_to_csv(sq_df, f"{output_dir}/{sq_label}.csv")
        result[sq_label] = sq_df
        print(f"Written {sq_label}.csv  ({len(pairs)} attributes)")

    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    results = run_pipeline(
        csv_path    = "engines/edaphic_crop_reqs/appendixes/appendix6_3_3.csv",
        crop_id     = 4,
        input_level = InputLevel.INTERMEDIATE,
        output_dir  = "engines/edaphic_crop_reqs/results",
    )