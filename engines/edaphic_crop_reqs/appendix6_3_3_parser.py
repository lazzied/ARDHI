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
    validate_and_get_row_idx,
    validate_and_get_row_idx,
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

ATTRIBUTE_NAME     = "DRG"   # unified output name after texture selection
ATTRIBUTE_PREFIX   = "DRG"   # base name used internally; suffixed with texture group
FIXED_SQ           = "SQ4"   # Appendix 6.3.3 always maps to SQ4

CROP_IDX_COL= 1

# Mapping from full drainage class label → short code used in _val output
DRG_CODE_MAP: Dict[str, str] = {
    "Very Poor":          "VP",
    "Poor":               "P",
    "Imperfectly":        "I",
    "Moderately well":    "MW",
    "Well":               "W",
    "Somewhat excessive": "SE",
    "Excessive":          "E",
}


# ---------------------------------------------------------------------------
# Block extraction
# ---------------------------------------------------------------------------

def extract_blocks(df: pd.DataFrame, crop_id: int,crops) -> List[SoilCharacteristicsBlock]:
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
    e.g. "Fine textures" → "DRG_Fine".  Drainage class labels are stored as
    full strings; short-code conversion happens at pipeline time.
    """
    if crop_id not in crops:
        raise ValueError(f"crop_id {crop_id} not found")

    crop_row_idx = validate_and_get_row_idx(df, CROP_IDX_COL, crop_id, crops)    

    blocks: List[SoilCharacteristicsBlock] = []
    total_cols = df.shape[1]

    col = BLOCK_START_COL
    while col + BLOCK_WIDTH <= total_cols:
        block_slice = df.iloc[:, col : col + BLOCK_WIDTH]

        input_level_text = " ".join(
            block_slice.iloc[INPUT_LEVEL_ROW].dropna().astype(str)
        )
        group_text = " ".join(
            block_slice.iloc[TEXTURAL_GROUP_ROW].dropna().astype(str)
        )

        if not group_text or not input_level_text:
            col += BLOCK_WIDTH
            continue

        # Internal attribute name retains texture suffix for filtering, e.g. "DRG_Fine"
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
# Texture selection + short-code conversion
# ---------------------------------------------------------------------------

def select_texture_block(
    blocks:               List[SoilCharacteristicsBlock],
    texture_class_report: str,
) -> SoilCharacteristicsBlock:
    """
    From the three textural blocks (Fine / Medium / Coarse) keep only the one
    matching texture_class_report (case-insensitive).
    Returns a copy of the matched block with:
      - attribute_name renamed to ATTRIBUTE_NAME ("DRG")
      - thresholds_row labels replaced with short codes via DRG_CODE_MAP
    """
    target = texture_class_report.strip().capitalize()  # e.g. "fine" -> "Fine"

    for block in blocks:
        # block.attribute_name is e.g. "DRG_Fine"
        suffix = block.attribute_name.split("_", 1)[-1]  # "Fine"
        if suffix == target:
            short_thresholds = [
                DRG_CODE_MAP.get(t, t) for t in block.thresholds_row
            ]
            return SoilCharacteristicsBlock(
                col_start      = block.col_start,
                col_end        = block.col_end,
                attribute_name = ATTRIBUTE_NAME,
                soil_qualities = block.soil_qualities,
                input_levels   = block.input_levels,
                penalties      = block.penalties,
                thresholds_row = short_thresholds,
            )

    available = [b.attribute_name.split("_", 1)[-1].lower() for b in blocks]
    raise ValueError(
        f"texture_class_report {texture_class_report!r} not found. "
        f"Available: {available}"
    )


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
    csv_path:             str,
    crop_id:              int,
    input_level:          InputLevel,
    texture_class_report: str,
    crops,
    output_dir:           str  = ".",
    write_output:         bool = False,
) -> Dict[str, pd.DataFrame]:
    """
    Full pipeline:
      1. Load CSV
      2. Extract all blocks for crop_id
      3. Filter blocks by input_level
      4. Select the single block matching texture_class_report and apply
         short drainage-class codes to its thresholds
      5. Group by SQ  (always SQ4 for this appendix)
      6. Build AttributePairs and DataFrames per SQ
      7. Optionally write one CSV per SQ (write_output=True)

    Parameters
    ----------
    texture_class_report : "fine" | "medium" | "coarse"  — selects the
                           drainage-class block for the measured soil texture.
                           Produces a single DRG attribute in the output.
    write_output         : write CSVs when True (default False so the
                           aggregator does not produce intermediate files)

    Returns a dict of {sq_label: DataFrame} for inspection.
    """
    df = pd.read_csv(csv_path, header=None)

    # Step 1: extract all blocks for this crop
    all_blocks = extract_blocks(df, crop_id,crops)

    # Step 2: filter by input level
    filtered_blocks = list(filter_blocks_by_input_level(all_blocks, input_level))

    # Step 3: select the matching texture block and apply short codes
    selected_block = select_texture_block(filtered_blocks, texture_class_report)

    # Step 4: group by SQ
    sq_groups: Dict[str, List[AttributePair]] = defaultdict(list)
    pair = build_attribute_pair(selected_block, crop_id)
    for sq in selected_block.soil_qualities:
        sq_groups[sq].append(pair)

    # Step 5: build one DataFrame per SQ and optionally write CSV
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
        csv_path             = "engines/edaphic_crop_reqs/appendixes/appendix6_3_3.csv",
        crop_id              = 4,
        input_level          = InputLevel.INTERMEDIATE,
        texture_class_report = "fine",
        crops                = CROPS_RAINFED_SPRINKLER,
        output_dir           = "engines/edaphic_crop_reqs/results",
        write_output         = True,
    )