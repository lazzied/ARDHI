

from __future__ import annotations
import re
from collections import defaultdict
from typing import Iterator, List
import pandas as pd
from engines.edaphic_crop_reqs.constants import ATTR_ABBREV_MAP, CROPS
from engines.edaphic_crop_reqs.models import AttributePair, InputLevel, RatingCurve, SoilCharacteristicsBlock
from engines.edaphic_crop_reqs.utils_functions import attribute_pairs_to_df, generate_sq_df, parse_input_levels, parse_sq_labels, write_sq_df_to_csv


# Sheet layout constants (1-based row numbers in the CSV)
ATTRIBUTE_ROW   = 2   # long attribute description
SQ_ROW          = 3   # SQ label
INPUT_LEVEL_ROW = 4   # input level text
CONSTRAINT_ROW  = 5   # short labels encoding attribute abbrev + penalty
DATA_START_ROW  = 7   # first crop data row (0-based index = 7, 1-based = 8)
BLOCK_START_COL = 2   # first data column (0-based)
BLOCK_WIDTH     = 6   # columns per block


def parse_attribute_name(constraint_label: str) -> str:
    """Extract short attribute name from a constraint class label.
    e.g. 'I+L SOC 100' -> 'OC',  'H CECa 100' -> 'CECclay'
    """
    # Pattern: optional level prefix, then attribute abbrev, then penalty number
    match = re.search(r"[A-Za-z+]+\s+([A-Za-z]+)\s+\d+", constraint_label.strip())
    if not match:
        return constraint_label.strip()
    abbrev = match.group(1)
    return ATTR_ABBREV_MAP.get(abbrev, abbrev)


def parse_penalties_from_constraint_row(labels: List[str]) -> List[float]:
    """Extract the penalty values from constraint class labels."""
    penalties = []
    for label in labels:
        m = re.search(r"(\d+)$", str(label).strip())
        if m:
            penalties.append(float(m.group(1)))
    return penalties


# ---------------------------------------------------------------------------
# Block extraction
# ---------------------------------------------------------------------------

def extract_blocks(df: pd.DataFrame, crop_id: int) -> List[SoilCharacteristicsBlock]:
    """
    Parse all 6-column blocks from the appendix DataFrame.
    Attaches thresholds for the given crop_id.
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
        sq_text          = " ".join(str(v) for v in block_slice.iloc[SQ_ROW]          if pd.notna(v))
        input_level_text = " ".join(str(v) for v in block_slice.iloc[INPUT_LEVEL_ROW] if pd.notna(v))
        constraint_vals  = [v for v in block_slice.iloc[CONSTRAINT_ROW]               if pd.notna(v)]
        crop_vals        = [v for v in block_slice.iloc[crop_row_idx]                  if pd.notna(v)]

        if not constraint_vals:
            col += BLOCK_WIDTH
            continue

        attr_name  = parse_attribute_name(str(constraint_vals[0]))
        penalties  = parse_penalties_from_constraint_row([str(v) for v in constraint_vals])
        thresholds = [float(v) for v in crop_vals]

        blocks.append(SoilCharacteristicsBlock(
            col_start      = col,
            col_end        = col + BLOCK_WIDTH,
            attribute_name = attr_name,
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

from typing import List

def select_ph_table(
    user_ph: float,
    ph_rating_curves: List["RatingCurve"]
) -> "RatingCurve":

    def get_valid_range(curve: "RatingCurve"):
        values = [v for v in curve.thresholds if v != 999]

        return min(values), max(values)

    for curve in ph_rating_curves:
        min_domain, max_domain = get_valid_range(curve)

        if min_domain <= user_ph <= max_domain:
            return curve

    raise ValueError(f"No valid pH rating curve for value: {user_ph}")

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
) -> dict[str, pd.DataFrame]:
    """
    Full pipeline:
      1. Load CSV
      2. Extract all blocks, filtered to crop_id
      3. Filter blocks by input_level
      4. Group by SQ
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
    sq_groups: dict[str, List[AttributePair]] = defaultdict(list)
    for block in filtered_blocks:
        pair = build_attribute_pair(block, crop_id)
        for sq in block.soil_qualities:
            sq_groups[sq].append(pair)

    # Step 4: build one DataFrame per SQ and write CSV
    result: dict[str, pd.DataFrame] = {}
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
        csv_path    = "engines/edaphic_crop_reqs/appendixes/appendix6_3_1.csv",
        crop_id     = 1,                    # maize
        input_level = InputLevel.INTERMEDIATE,
        output_dir  = "engines/edaphic_crop_reqs/results",
    )

    # Spot-check SQ1 output
    print("\n--- SQ1 preview ---")
    print(results.get("SQ1", "not found"))