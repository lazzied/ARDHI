"""Parser for one appendix source used to build edaphic crop requirement tables."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterator, List

import pandas as pd

from engines.edaphic_crop_reqs.constants import (
    DRAINAGE_ABBREV_MAP, CROPS_RAINFED_SPRINKLER,
)
from engines.edaphic_crop_reqs.models import (
    AttributePair, InputLevel, RatingCurve, SoilCharacteristicsBlock,
)
from engines.edaphic_crop_reqs.utils_functions import (
    attribute_pairs_to_df,
    generate_sq_df,
    normalize_categorical_label,
    parse_input_levels,
    validate_and_get_row_idx,
    write_sq_df_to_csv,
)

# ---------------------------------------------------------------------------
# Sheet layout constants (0-based row / column indices)
# ---------------------------------------------------------------------------
INPUT_LEVEL_ROW    = 3
TEXTURAL_GROUP_ROW = 4
ATTRIBUTE_ROW      = 5   # drainage class names  (VAL row)
DATA_START_ROW     = 7

BLOCK_START_COL    = 2
BLOCK_WIDTH        = 7   # 7 drainage classes

ATTRIBUTE_NAME     = "DRG"
ATTRIBUTE_PREFIX   = "DRG"
FIXED_SQ           = "SQ4"

CROP_IDX_COL       = 0

# Canonical long-name -> short-code map, pulled from the augmentation contract.
# Legacy parser had its own private DRAINAGE_ABBREV_MAP; keeping a single source of
# truth prevents drift.


# ---------------------------------------------------------------------------
# Block extraction
# ---------------------------------------------------------------------------

def extract_blocks(
    df:      pd.DataFrame,
    crop_id: int,
    crops:   dict[int, dict],
) -> List[SoilCharacteristicsBlock]:
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

        texture_label  = group_text.split()[0].capitalize()        # "Fine" / "Medium" / "Coarse"
        attribute_name = f"{ATTRIBUTE_PREFIX}_{texture_label}"     # internal tag; replaced post-select

        # Full drainage labels from the sheet; normalize to canonical lowercase.
        thresholds = [
            normalize_categorical_label(v)
            for v in block_slice.iloc[ATTRIBUTE_ROW].tolist()
        ]
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
# Filtering
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
# Texture selection + canonical short-code conversion
# ---------------------------------------------------------------------------

def select_texture_block(
    blocks:               List[SoilCharacteristicsBlock],
    texture_class_report: str,
) -> SoilCharacteristicsBlock:
    """From the three textural sub-blocks (Fine/Medium/Coarse), keep only the
    one matching texture_class_report.  Thresholds are replaced with canonical
    DRG short codes (VP/P/I/MW/W/SE/E) and attribute_name is set to the
    canonical 'DRG'."""
    target = texture_class_report.strip().capitalize()

    for block in blocks:
        suffix = block.attribute_name.split("_", 1)[-1]
        if suffix == target:
            short_thresholds = [
                DRAINAGE_ABBREV_MAP.get(t, t) for t in block.thresholds_row
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


def build_attribute_pair(block: SoilCharacteristicsBlock, crop_id: int) -> AttributePair:
    curve = RatingCurve(
        crop_id    = crop_id,
        penalties  = block.penalties,
        thresholds = block.thresholds_row,
    )
    return AttributePair(attribute_name=block.attribute_name, rating_curve=curve)


def run_pipeline(
    csv_path:             str,
    crop_id:              int,
    input_level:          InputLevel,
    texture_class_report: str,
    crops,
    output_dir:           str  = ".",
    write_output:         bool = False,
) -> Dict[str, pd.DataFrame]:
    df = pd.read_csv(csv_path, header=None)

    all_blocks      = extract_blocks(df, crop_id, crops)
    filtered_blocks = list(filter_blocks_by_input_level(all_blocks, input_level))
    selected_block  = select_texture_block(filtered_blocks, texture_class_report)

    sq_groups: Dict[str, List[AttributePair]] = defaultdict(list)
    pair = build_attribute_pair(selected_block, crop_id)
    for sq in selected_block.soil_qualities:
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
        csv_path             = "engines/edaphic_crop_reqs/appendixes/appendix6_3_3.csv",
        crop_id              = 4,
        input_level          = InputLevel.INTERMEDIATE,
        texture_class_report = "fine",
        crops                = CROPS_RAINFED_SPRINKLER,
        output_dir           = "engines/edaphic_crop_reqs/results",
        write_output         = True,
    )
"""Parser for one appendix source used to build edaphic crop requirement tables."""
