"""Appendix 6.3.2 parser — soil-texture class ratings.

Fixes applied versus the legacy parser
--------------------------------------
* TXT threshold labels are normalized to the canonical vocabulary:
  lowercase + single-space internal whitespace
  (e.g. 'Clay  (light)' -> 'clay (light)'). The augmentation module emits
  TXT in lowercase so edaphic thresholds MUST match exactly for the
  downstream rating-table join to work.
* Any threshold label that, after normalization, is not in the canonical
  TXT 13-class vocabulary is dropped with a warning.
* Attribute name is 'TXT' (already canonical).

Pipeline architecture unchanged.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterator, List

import pandas as pd

from engines.edaphic_crop_reqs.constants import (
    ATTR_ABBREV_MAP, CROPS_RAINFED_SPRINKLER,
)
from engines.edaphic_crop_reqs.models import (
    AttributePair, InputLevel, RatingCurve, SoilCharacteristicsBlock,
)
from engines.edaphic_crop_reqs.utils_functions import (
    attribute_pairs_to_df,
    generate_sq_df,
    normalize_categorical_label,
    parse_input_levels,
    parse_sq_labels,
    validate_and_get_row_idx,
    write_sq_df_to_csv,
)

INPUT_LEVEL_ROW = 2
SQ_ROW          = 3
ATTRIBUTE_ROW   = 4   # texture class labels  (VAL row)
DATA_START_ROW  = 6

BLOCK_START_COL = 2
BLOCK_WIDTH     = 13

ATTRIBUTE_NAME  = "TXT"
CROP_IDX_COL    = 0



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

        sq_text          = " ".join(str(v) for v in block_slice.iloc[SQ_ROW]          if pd.notna(v))
        input_level_text = " ".join(str(v) for v in block_slice.iloc[INPUT_LEVEL_ROW] if pd.notna(v))

        # Normalise texture labels and align penalties column-by-column.
        raw_thresholds = block_slice.iloc[ATTRIBUTE_ROW].tolist()
        fct_matrix     = block_slice.iloc[DATA_START_ROW:]
        raw_penalties  = fct_matrix.astype(float).values.tolist()[
            crop_row_idx - DATA_START_ROW
        ]

        thresholds: List[str]   = []
        penalties:  List[float] = []
        for raw_label, pen in zip(raw_thresholds, raw_penalties):
            if pd.isna(raw_label):
                continue
            label = normalize_categorical_label(raw_label)

            thresholds.append(label)
            penalties.append(float(pen))

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
# Filtering + pipeline
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


def build_attribute_pair(block: SoilCharacteristicsBlock, crop_id: int) -> AttributePair:
    curve = RatingCurve(
        crop_id    = crop_id,
        penalties  = block.penalties,
        thresholds = block.thresholds_row,
    )
    return AttributePair(attribute_name=block.attribute_name, rating_curve=curve)


def run_pipeline(
    csv_path:     str,
    crop_id:      int,
    crops:        dict[int, dict],
    input_level:  InputLevel,
    output_dir:   str  = ".",
    write_output: bool = False,
) -> Dict[str, pd.DataFrame]:
    df = pd.read_csv(csv_path, header=None)

    all_blocks      = extract_blocks(df, crop_id, crops)
    filtered_blocks = list(filter_blocks_by_input_level(all_blocks, input_level))

    sq_groups: Dict[str, List[AttributePair]] = defaultdict(list)
    for block in filtered_blocks:
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
        csv_path     = "engines/edaphic_crop_reqs/appendixes/rainfed_sprinkler_appendix/csv_sheets/A6-3.2.csv",
        crop_id      = 4,
        crops        = CROPS_RAINFED_SPRINKLER,
        input_level  = InputLevel.INTERMEDIATE,
        output_dir   = "engines/edaphic_crop_reqs/results",
        write_output = True,
    )