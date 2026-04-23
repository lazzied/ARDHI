import re
from typing import Dict, List, Union

import pandas as pd

from engines.edaphic_crop_reqs.models import AttributePair, InputLevel


def attribute_pairs_to_df(pairs: List[AttributePair]) -> pd.DataFrame:
    rows, index = [], []
    for pair in pairs:
        attr  = pair.attribute_name
        curve = pair.rating_curve
        rows.append(curve.thresholds);  index.append(f"{attr}_val")
        rows.append(curve.penalties);   index.append(f"{attr}_fct")
    return pd.DataFrame(rows, index=index)

def generate_sq_df(dfs: List[pd.DataFrame]) -> pd.DataFrame:
    return pd.concat(dfs, axis=0)

def write_sq_df_to_csv(df: pd.DataFrame, path: str) -> None:
    df.to_csv(path, header=False)
    
def parse_sq_labels(text: str) -> List[str]:
    return [f"SQ{n}" for n in re.findall(r"SQ\s*(\d+)", text)]

def parse_input_levels(text: str) -> List[InputLevel]:
    lower = text.lower()
    return [lvl for lvl in InputLevel if lvl.value in lower]


def validate_and_get_row_idx(
    df: pd.DataFrame, 
    col: str, 
    crop_id: int, 
    crops_registry: Dict[int, Dict]
) -> int:
    """
    Validates crop_id against a DataFrame and a registry, 
    ensuring names match across both sources.
    """
    
    # 1. Validate ID exists in the reference dictionary
    if crop_id not in crops_registry:
        raise ValueError(f"Crop ID {crop_id} not found in the reference CROPS dictionary.")
    
    expected_name = crops_registry[crop_id]["name"].strip().lower().replace("_", " ")

    # 2. Find matches in the DataFrame
    # Note: Using astype(str) to ensure comparison works regardless of dtypes
    mask = df[col].astype(str) == str(crop_id)
    matches = df.index[mask].tolist()

    if len(matches) == 0:
        raise ValueError(f"Crop ID {crop_id} not found in DataFrame column '{col}'.")
    
    if len(matches) > 1:
        raise ValueError(f"Multiple entries found for Crop ID {crop_id} (ambiguous data).")

    # 3. Retrieve row data
    # row_idx is the 0-based integer position relative to the DataFrame
    row_idx = matches[0] 
    
    # Identify the column index for ID and the one immediately to the right (+1)
    col_idx_id = df.columns.get_loc(col)
    col_idx_name = col_idx_id + 1
    
    if col_idx_name >= len(df.columns):
        raise IndexError(f"No column exists to the right of '{col}' to verify crop name.")

    df_crop_name = str(df.iloc[row_idx, col_idx_name]).strip().lower().replace("_", " ")

    # 4. Validate name matching (case-insensitive)
    if df_crop_name != expected_name:
        raise ValueError(
            f"Data mismatch for ID {crop_id}: "
            f"Registry says '{expected_name}', but DataFrame says '{df_crop_name}'."
        )

    # Return the 0-based index
    return int(row_idx)