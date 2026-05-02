"""Shared helpers for the edaphic parsers and orchestrator."""
import re
from typing import Dict, List

import pandas as pd

from engines.edaphic_crop_reqs.models import AttributePair, InputLevel


# --------------------------------------------------------------------------
# DataFrame assembly
# --------------------------------------------------------------------------

def attribute_pairs_to_df(pairs: List[AttributePair]) -> pd.DataFrame:
    """
    One AttributePair -> two rows in the output DataFrame:
        "{attr}_val" holds thresholds
        "{attr}_fct" holds penalties
    Attribute names are passed through verbatim; callers are responsible for
    ensuring they match the canonical PyAEZ 2.2 contract.
    """
    rows, index = [], []
    for pair in pairs:
        attr  = pair.attribute_name
        curve = pair.rating_curve
        rows.append(curve.thresholds);  index.append(f"{attr}_val")
        rows.append(curve.penalties);   index.append(f"{attr}_fct")
    return pd.DataFrame(rows, index=index)


def generate_sq_df(dfs: List[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate per-attribute DataFrames into a single per-SQ DataFrame
    while preserving the "_val"/"_fct" index labels."""
    return pd.concat(dfs, axis=0)


def write_sq_df_to_csv(df: pd.DataFrame, path: str) -> None:
    df.to_csv(path, header=False)


def parse_sq_labels(text: str) -> List[str]:
    return [f"SQ{n}" for n in re.findall(r"SQ\s*(\d+)", text)]


def parse_input_levels(text: str) -> List[InputLevel]:
    lower = text.lower()
    return [lvl for lvl in InputLevel if lvl.value in lower]


# --------------------------------------------------------------------------
# Canonical label normalization
# --------------------------------------------------------------------------

def normalize_categorical_label(raw: str) -> str:
    """
    Lowercase + collapse internal whitespace.

    The appendix CSVs come in title case with occasional double spaces
    (e.g. 'Clay  (light)', 'Silty clay loam'); the canonical vocabulary
    in vocabulary.py is strictly lowercase with single spaces
    ('clay (light)', 'silty clay loam'). This helper bridges the gap so
    edaphic rating curves index-match the augmentation output.
    """
    if raw is None:
        return ""
    return re.sub(r"\s+", " ", str(raw).strip()).lower()


# --------------------------------------------------------------------------
# Crop validation
# --------------------------------------------------------------------------

def validate_and_get_row_idx(
    df:             pd.DataFrame,
    col:            str,
    crop_id:        int,
    crops_registry: Dict[int, Dict],
) -> int:
    """Validate crop_id against the DataFrame and registry; return the row index."""

    if crop_id not in crops_registry:
        raise ValueError(
            f"Crop ID {crop_id} not found in the reference CROPS dictionary."
        )

    expected_name = crops_registry[crop_id]["name"].strip().lower().replace("_", " ")

    mask    = df[col].astype(str) == str(crop_id)
    matches = df.index[mask].tolist()
    if not matches:
        raise ValueError(
            f"Crop ID {crop_id} not found in DataFrame column '{col}'."
        )
    if len(matches) > 1:
        raise ValueError(
            f"Multiple entries found for Crop ID {crop_id} (ambiguous data)."
        )

    row_idx = matches[0]
    col_idx_id   = df.columns.get_loc(col)
    col_idx_name = col_idx_id + 1
    if col_idx_name >= len(df.columns):
        raise IndexError(f"No column exists to the right of '{col}' to verify crop name.")

    df_crop_name = str(df.iloc[row_idx, col_idx_name]).strip().lower().replace("_", " ")
    if df_crop_name != expected_name:
        raise ValueError(
            f"Data mismatch for ID {crop_id}: "
            f"Registry says '{expected_name}', but DataFrame says '{df_crop_name}'."
        )

    return int(row_idx)