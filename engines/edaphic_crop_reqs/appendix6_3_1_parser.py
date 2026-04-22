from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, Iterator, List

import pandas as pd

from engines.edaphic_crop_reqs.constants import ATTR_ABBREV_MAP, CROPS_RAINFED_SPRINKLER
from engines.edaphic_crop_reqs.models import AttributePair, InputLevel, RatingCurve, SoilCharacteristicsBlock
from engines.edaphic_crop_reqs.utils_functions import (
    attribute_pairs_to_df,
    generate_sq_df,
    validate_and_get_row_idx,
    parse_input_levels,
    parse_sq_labels,
    write_sq_df_to_csv,
)

# ---------------------------------------------------------------------------
# Sheet layout constants (0-based row / column indices)
# ---------------------------------------------------------------------------
ATTRIBUTE_ROW   = 2   # long attribute description
SQ_ROW          = 3   # SQ label
INPUT_LEVEL_ROW = 4   # input level text
CONSTRAINT_ROW  = 5   # short labels encoding attribute abbrev + penalty
DATA_START_ROW  = 7   # first crop data row

BLOCK_START_COL = 2  # first data column (0-based)
BLOCK_WIDTH     = 6   # columns per block

CROP_IDX_COL= 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_attribute_name(constraint_label: str) -> str:
    """Extract short attribute name from a constraint class label.
    e.g. 'I+L SOC 100' -> 'OC',  'H CECa 100' -> 'CECclay'
    """
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


def select_ph_curve(
    ph_report: float,
    ph_blocks: List[SoilCharacteristicsBlock],
) -> SoilCharacteristicsBlock:
    """
    Given two pH blocks for the same (SQ, input_level) — one acidic, one basic —
    return the one whose threshold range (excluding the 999 sentinel) contains
    ph_report.  If ph_report falls in neither range, the closer range is used.
    """
    def valid_range(block: SoilCharacteristicsBlock):
        values = [float(v) for v in block.thresholds_row if float(v) != 999]
        return min(values), max(values)

    for block in ph_blocks:
        lo, hi = valid_range(block)
        if lo <= ph_report <= hi:
            return block

    # Fallback: pick the range whose midpoint is nearest ph_report
    def midpoint(block):
        lo, hi = valid_range(block)
        return (lo + hi) / 2

    return min(ph_blocks, key=lambda b: abs(midpoint(b) - ph_report))


# ---------------------------------------------------------------------------
# Block extraction
# ---------------------------------------------------------------------------

def extract_blocks(df: pd.DataFrame, crop_id: int,CROPS) -> List[SoilCharacteristicsBlock]:
    """
    Parse all 6-column blocks from the Appendix 6.3.1 DataFrame.
    Attaches thresholds for the given crop_id.
    """
    if crop_id not in CROPS:
        raise ValueError(f"crop_id {crop_id} not found")

    crop_row_idx = validate_and_get_row_idx(df, CROP_IDX_COL, crop_id, CROPS)    
    
    blocks: List[SoilCharacteristicsBlock] = []
    total_cols = df.shape[1]

    col = BLOCK_START_COL
    while col + BLOCK_WIDTH <= total_cols:
        block_slice = df.iloc[:, col : col + BLOCK_WIDTH]

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


# ---------------------------------------------------------------------------
# pH deduplication
# ---------------------------------------------------------------------------

def resolve_ph_blocks(
    blocks:    List[SoilCharacteristicsBlock],
    ph_report: float,
) -> List[SoilCharacteristicsBlock]:
    """
    For each (SQ, input_level) group that contains more than one pH block
    (one acidic curve, one basic curve), keep only the curve whose range
    contains ph_report.  All non-pH blocks are returned unchanged.
    """
    non_ph = [b for b in blocks if b.attribute_name != "pH"]

    # Group pH blocks by (frozenset of soil_qualities, frozenset of input_levels)
    ph_groups: dict[tuple, List[SoilCharacteristicsBlock]] = defaultdict(list)
    for b in blocks:
        if b.attribute_name == "pH":
            key = (frozenset(b.soil_qualities), frozenset(b.input_levels))
            ph_groups[key].append(b)

    resolved_ph: List[SoilCharacteristicsBlock] = []
    for key, ph_blocks in ph_groups.items():
        if len(ph_blocks) == 1:
            resolved_ph.append(ph_blocks[0])
        else:
            resolved_ph.append(select_ph_curve(ph_report, ph_blocks))

    return non_ph + resolved_ph


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
    input_level:  InputLevel,
    ph_report:    float,
    crops,
    output_dir:   str  = ".",
    write_output: bool = False,
) -> Dict[str, pd.DataFrame]:
    """
    Full pipeline:
      1. Load CSV
      2. Extract all blocks for crop_id
      3. Filter blocks by input_level
      4. Resolve pH duplication: keep only the acidic or basic curve
         based on ph_report
      5. Group by SQ
      6. Build AttributePairs and DataFrames per SQ
      7. Optionally write one CSV per SQ (write_output=True)

    Parameters
    ----------
    ph_report    : measured soil pH used to select the correct pH curve
    write_output : write CSVs when True (default False so the aggregator
                   does not produce intermediate files)

    Returns a dict of {sq_label: DataFrame} for inspection.
    """
    df = pd.read_csv(csv_path, header=None)

    # Step 1: extract all blocks for this crop
    all_blocks = extract_blocks(df, crop_id,crops)

    # Step 2: filter by input level
    filtered_blocks = list(filter_blocks_by_input_level(all_blocks, input_level))

    # Step 3: resolve pH duplication
    filtered_blocks = resolve_ph_blocks(filtered_blocks, ph_report)

    # Step 4: group by SQ
    sq_groups: Dict[str, List[AttributePair]] = defaultdict(list)
    for block in filtered_blocks:
        pair = build_attribute_pair(block, crop_id)
        for sq in block.soil_qualities:
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
        csv_path     = "engines/edaphic_crop_reqs/appendixes/rainfed_sprinkler_appendix/csv_sheets/A6-3.1.csv",
        crop_id      = 1,
        crops        = CROPS_RAINFED_SPRINKLER,
        input_level  = InputLevel.INTERMEDIATE,
        ph_report    = 6.0,
        output_dir   = "engines/edaphic_crop_reqs/results",
        write_output = True,
    )

    print("\n--- SQ1 preview ---")
    print(results.get("SQ1", "not found"))