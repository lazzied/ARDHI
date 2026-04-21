from __future__ import annotations

import pandas as pd
from typing import List, Dict, Iterator
from collections import defaultdict

from engines.edaphic_crop_reqs.constants import CROPS
from engines.edaphic_crop_reqs.models import AttributePair, InputLevel, RatingCurve, SoilCharacteristicsBlock
from engines.edaphic_crop_reqs.utils_functions import attribute_pairs_to_df, generate_sq_df, parse_input_levels, parse_sq_labels, write_sq_df_to_csv

# ---------------------------------------------------------
# APPENDIX 2 CONFIG
# ---------------------------------------------------------

ATTRIBUTE_ROW   = 4   
SQ_ROW          = 3
INPUT_LEVEL_ROW = 2
DATA_START_ROW  = 6

BLOCK_START_COL = 2
BLOCK_WIDTH     = 13


# ---------------------------------------------------------
# BLOCK EXTRACTION (FIXED LOGIC)
# ---------------------------------------------------------

def extract_blocks_v2(df: pd.DataFrame, crop_id: int) -> List[SoilCharacteristicsBlock]:
    """
    Appendix 2:
    - Row 4 = TEXTURE CLASSES (VAL)
    - Rows 6+ = PENALTY MATRIX (FCT)
    """

    blocks: List[SoilCharacteristicsBlock] = []
    total_cols = df.shape[1]

    crop_row_idx = CROPS[crop_id]["row"] - 1  # convert to 0-based

    col = BLOCK_START_COL

    while col + BLOCK_WIDTH <= total_cols:
        block = df.iloc[:, col: col + BLOCK_WIDTH]

        # metadata rows
        sq_text = " ".join(str(v) for v in block.iloc[SQ_ROW] if pd.notna(v))
        input_text = " ".join(str(v) for v in block.iloc[INPUT_LEVEL_ROW] if pd.notna(v))

        # -----------------------------------------------------
        # FIX 1: VAL ROW = TEXTURE CLASSES
        # -----------------------------------------------------
        val_row = block.iloc[ATTRIBUTE_ROW]
        thresholds = [str(v).strip() for v in val_row.tolist() if pd.notna(v)]

        # -----------------------------------------------------
        # FIX 2: FCT MATRIX (ALL CROPS)
        # -----------------------------------------------------
        fct_matrix = block.iloc[DATA_START_ROW:]
        penalties_matrix = fct_matrix.astype(float).values.tolist()

        # crop-specific row selection
        crop_penalties = penalties_matrix[crop_row_idx - DATA_START_ROW]

        blocks.append(
            SoilCharacteristicsBlock(
                col_start=col,
                col_end=col + BLOCK_WIDTH,
                attribute_name="TXT",
                soil_qualities=parse_sq_labels(sq_text),
                input_levels=parse_input_levels(input_text),

                penalties=crop_penalties,     # FIXED: per crop row
                thresholds_row=thresholds,    # FIXED: texture classes
            )
        )

        col += BLOCK_WIDTH

    return blocks


# ---------------------------------------------------------
# ATTRIBUTE PAIR BUILDER (FIXED CONSISTENCY)
# ---------------------------------------------------------

def build_attribute_pair_v2(
    block: SoilCharacteristicsBlock,
    crop_id: int
) -> AttributePair:

    curve = RatingCurve(
        crop_id=crop_id,
        penalties=block.penalties,      # already crop-specific
        thresholds=block.thresholds_row
    )

    return AttributePair(
        attribute_name=block.attribute_name,
        rating_curve=curve,
    )


# ---------------------------------------------------------
# FILTERS (UNCHANGED LOGIC)
# ---------------------------------------------------------

def filter_blocks_by_input_level(
    blocks: List[SoilCharacteristicsBlock],
    input_level: InputLevel,
) -> Iterator[SoilCharacteristicsBlock]:

    for b in blocks:
        if input_level in b.input_levels:
            yield b


def filter_blocks_by_sq(
    blocks: List[SoilCharacteristicsBlock],
    sq_id: int,
) -> Iterator[SoilCharacteristicsBlock]:

    for b in blocks:
        if f"SQ{sq_id}" in b.soil_qualities:
            yield b


# ---------------------------------------------------------
# PIPELINE (UNCHANGED STRUCTURE)
# ---------------------------------------------------------

def run_pipeline_v2(
    csv_path: str,
    crop_id: int,
    input_level: InputLevel,
    output_dir: str = ".",
) -> Dict[str, pd.DataFrame]:

    df = pd.read_csv(csv_path, header=None)

    # 1. extract blocks
    blocks = extract_blocks_v2(df, crop_id)

    # 2. filter input level
    blocks = list(filter_blocks_by_input_level(blocks, input_level))

    # 3. group by SQ
    sq_groups = defaultdict(list)

    for block in blocks:
        pair = build_attribute_pair_v2(block, crop_id)

        for sq in block.soil_qualities:
            sq_groups[sq].append(pair)

    # 4. build output
    result: dict[str, pd.DataFrame] = {}
    for sq, pairs in sq_groups.items():
        dfs = [attribute_pairs_to_df([p]) for p in pairs]
        sq_df = generate_sq_df(dfs)

        write_sq_df_to_csv(sq_df, f"{output_dir}/{sq}.csv")

        result[sq] = sq_df
        print(f"[Appendix2] Written {sq}.csv")

    return result


# ---------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------

if __name__ == "__main__":
    run_pipeline_v2(
        csv_path="engines/edaphic_crop_reqs/appendixes/appendix6_3_2.csv",
        crop_id=4,
        input_level=InputLevel.INTERMEDIATE,
        output_dir="engines/edaphic_crop_reqs/results",
    )