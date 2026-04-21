from __future__ import annotations

import pandas as pd
from typing import List, Dict, Iterator
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

from engines.edaphic_crop_reqs.constants import CROPS
from engines.edaphic_crop_reqs.models import AttributePair, InputLevel, RatingCurve, SoilCharacteristicsBlock
from engines.edaphic_crop_reqs.utils_functions import attribute_pairs_to_df, generate_sq_df, parse_input_levels, write_sq_df_to_csv


# ---------------------------------------------------------
# APPENDIX 3 CONFIG (0-BASED INDEXING)
# ---------------------------------------------------------
# Note: Offsets adjusted to match appendix6_3_3.csv layout
INPUT_LEVEL_ROW    = 3   # Excel Row 4
TEXTURAL_GROUP_ROW = 4   # Excel Row 5
ATTRIBUTE_ROW      = 5   # Excel Row 6 (Drainage Classes)
DATA_START_ROW     = 7   # Excel Row 8 (First Crop Data)

BLOCK_START_COL    = 2   # Column C (Excel)
BLOCK_WIDTH        = 7   # 7 Drainage classes per block

ATTRIBUTE_NAME     = "DRG"
FIXED_SQ           = "SQ4"

TEXTURAL_GROUPINGS = ["Fine textures", "Medium textures", "Coarse textures"]

# ---------------------------------------------------------
# BLOCK EXTRACTION
# ---------------------------------------------------------

def extract_blocks_v3(df: pd.DataFrame, crop_id: int) -> List[SoilCharacteristicsBlock]:
    """
    Appendix 3:
    - Row 4 = Input Levels
    - Row 5 = Textural Groupings (Fine, Medium, Coarse)
    - Row 6 = Drainage Classes (Very Poor ... Excessive)
    - Rows 8+ = Rating Matrix
    """
    blocks: List[SoilCharacteristicsBlock] = []
    total_cols = df.shape[1]
    
    # 0-based index for the crop
    crop_row_idx = CROPS[crop_id]["row"] - 1 

    col = BLOCK_START_COL
    while col + BLOCK_WIDTH <= total_cols:
        # Extract Textural Group (e.g., "Fine textures")
        group_raw = " ".join(df.iloc[TEXTURAL_GROUP_ROW, col : col + BLOCK_WIDTH].dropna().astype(str))
        
        # Extract Input Level text
        input_raw = " ".join(df.iloc[INPUT_LEVEL_ROW, col : col + BLOCK_WIDTH].dropna().astype(str))

        if not group_raw or not input_raw:
            col += BLOCK_WIDTH
            continue

        # Clean texture name for attribute (e.g., "Fine textures" -> "Fine")
        texture_name = group_raw.split()[0].capitalize()
        dynamic_attr_name = f"{ATTRIBUTE_NAME}_{texture_name}"

        # Get Drainage Classes (Headers for the _val row)
        drainage_classes = [str(v).strip() for v in df.iloc[ATTRIBUTE_ROW, col : col + BLOCK_WIDTH].tolist()]

        # Get Numeric Ratings (Penalties for the _fct row)
        ratings = df.iloc[crop_row_idx, col : col + BLOCK_WIDTH].astype(float).tolist()

        blocks.append(
            SoilCharacteristicsBlock(
                col_start=col,
                col_end=col + BLOCK_WIDTH,
                attribute_name=dynamic_attr_name,
                soil_qualities=[FIXED_SQ],
                input_levels=parse_input_levels(input_raw),
                penalties=ratings,
                thresholds_row=drainage_classes,
            )
        )
        col += BLOCK_WIDTH

    return blocks

# ---------------------------------------------------------
# PIPELINE
# ---------------------------------------------------------

def run_pipeline_v3(
    csv_path: str,
    crop_id: int,
    input_level: InputLevel,
    output_dir: str = ".",
) -> Dict[str, pd.DataFrame]:
    """
    Processes Appendix 6.3.3 for a specific crop and input level.
    Results are grouped into SQ4.csv.
    """
    df = pd.read_csv(csv_path, header=None)

    # 1. Extract all blocks
    all_blocks = extract_blocks_v3(df, crop_id)

    # 2. Filter by Input Level
    filtered_blocks = [b for b in all_blocks if input_level in b.input_levels]

    # 3. Format as AttributePairs
    pairs = []
    for block in filtered_blocks:
        curve = RatingCurve(
            crop_id=crop_id,
            penalties=block.penalties,
            thresholds=block.thresholds_row
        )
        pairs.append(AttributePair(attribute_name=block.attribute_name, rating_curve=curve))

    # 4. Generate Output (Fixed SQ4)
    if not pairs:
        print(f"[Appendix3] No data found for {input_level.value}")
        return {}

    sq_df = generate_sq_df([attribute_pairs_to_df([p]) for p in pairs])
    write_sq_df_to_csv(sq_df, f"{output_dir}/{FIXED_SQ}.csv")
    
    print(f"[Appendix3] Written {FIXED_SQ}.csv with {len(pairs)} textural attributes.")
    return {FIXED_SQ: sq_df}

# ---------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------

if __name__ == "__main__":
    run_pipeline_v3(
        csv_path="engines/edaphic_crop_reqs/appendixes/appendix6_3_3.csv",
        crop_id=4,  # Maize
        input_level=InputLevel.INTERMEDIATE,
        output_dir="engines/edaphic_crop_reqs/results",
    )