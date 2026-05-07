"""Parser for one appendix source used to build edaphic crop requirement tables."""

from __future__ import annotations
import re
from collections import defaultdict
from typing import Dict, Iterator, List
import pandas as pd

from data_scripts.edaphic_crop_reqs.constants import ATTR_ABBREV_MAP, CROPS_RAINFED_SPRINKLER
from data_scripts.edaphic_crop_reqs.models import AttributePair, RatingCurve, SoilCharacteristicsBlock
from data_scripts.edaphic_crop_reqs.utils_functions import attribute_pairs_to_df, generate_sq_df, parse_input_levels, parse_sq_labels, validate_and_get_row_idx, write_sq_df_to_csv
from engines.OCR_processing.models import InputLevel




# ---------------------------------------------------------------------------
# Sheet layout constants (0-based row / column indices)
# ---------------------------------------------------------------------------
ATTRIBUTE_ROW   = 2   # long attribute description
SQ_ROW          = 3   # SQ label
INPUT_LEVEL_ROW = 4   # input level text
PENALTIES_ROW  = 5   # short labels encoding attribute abbrev + penalty
DATA_START_ROW  = 7   # first crop data row
BLOCK_START_COL = 2   # first data column (0-based)
BLOCK_WIDTH     = 6   # columns per block
CROP_IDX_COL    = 0

# RSD sentinel (GAEZ "no data" marker). Kept as-is; only real numeric
# depths are unit-converted cm -> mm below.
_SENTINEL = 999.0


# ---------------------------------------------------------------------------
# normalize_input_level
# ---------------------------------------------------------------------------

def normalize_input_level(
    input_level_text:      str,
    SQ_list: List[str],
) -> Dict[InputLevel, List[str]]:
    text = input_level_text.strip()

    level_pattern = "|".join(re.escape(lvl.value) for lvl in InputLevel)

    level_starts = [
        (m.start(), m.group(0).lower())
        for m in re.finditer(rf"\b({level_pattern})\b", text, flags=re.IGNORECASE)
    ]
    if not level_starts:
        return {}

    segments: List[tuple[InputLevel, str]] = []
    for i, (start, matched_level) in enumerate(level_starts):
        end          = level_starts[i + 1][0] if i + 1 < len(level_starts) else len(text)
        segment_text = text[start:end]
        try:
            level = InputLevel(matched_level)
        except ValueError:
            continue
        segments.append((level, segment_text))

    def _normalise_sq(raw: str) -> str:
        return re.sub(r"\s+", "", raw.strip().upper())

    result: Dict[InputLevel, List[str]] = {}
    for level, segment in segments:
        paren_match = re.search(r"\(([^)]+)\)", segment)
        if paren_match:
            raw_sqs    = re.findall(r"\bSQ\s*\d+\b", paren_match.group(1), flags=re.IGNORECASE)
            restricted = [_normalise_sq(sq) for sq in raw_sqs]
            allowed    = [sq for sq in restricted if sq in SQ_list]
            result[level] = allowed if allowed else list(SQ_list)
        else:
            result[level] = list(SQ_list)
    return result


def parse_attribute_name(penalties_label: str) -> list[str] | None:
    """Extract the canonical attribute name from a penalties-class label.

    e.g. 'I+L SOC 100' -> 'OC',   'H CECa 100' -> 'CECclay'.

    Returns None when the abbreviation is not in ATTR_ABBREV_MAP, or the
    mapped name is not in CANONICAL_ATTRIBUTES. Both cases cause the block
    to be dropped upstream (e.g. Gelic blocks on Tunisia profiles).
    """
    match = re.search(r"[A-Za-z+]+\s+([A-Za-z]+)\s+\d+", penalties_label.strip())
    if not match:
        return None
    abbrev = match.group(1)
    abbv = ATTR_ABBREV_MAP.get(abbrev)
    return abbv if abbv else None


def parse_penalties_from_PENALTIES_ROW(labels: List[str]) -> List[float]:
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
    """Pick the acidic or basic pH curve whose range contains ph_report,
    falling back to the nearest mid-point when ph_report lies outside both."""
    def valid_range(block: SoilCharacteristicsBlock):
        values = [float(v) for v in block.thresholds_row if float(v) != _SENTINEL]
        return min(values), max(values)

    for block in ph_blocks:
        lo, hi = valid_range(block)
        if lo <= ph_report <= hi:
            return block

    def midpoint(block):
        lo, hi = valid_range(block)
        return (lo + hi) / 2

    return min(ph_blocks, key=lambda b: abs(midpoint(b) - ph_report))


# ---------------------------------------------------------------------------
# RSD unit conversion — cm -> mm  (matches augmentation module's canonical)
# ---------------------------------------------------------------------------

def _convert_rsd_to_mm(thresholds: List[float]) -> List[float]:
    """Multiply every non-sentinel threshold by 10 (cm -> mm).
    The GAEZ sentinel 999 is preserved unchanged so downstream lookups
    still match the 'no data' convention."""
    out: List[float] = []
    for v in thresholds:
        fv = float(v)
        out.append(fv if fv == _SENTINEL else round(fv * 10.0, 1))
    return out


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
        
        penalties_vals  = [v for v in block_slice.iloc[PENALTIES_ROW]               if pd.notna(v)]
        crop_vals        = [v for v in block_slice.iloc[crop_row_idx]                  if pd.notna(v)]

        raw_sq       = parse_sq_labels(sq_text)
        raw_levels   = parse_input_levels(input_level_text)
        level_sq_map = normalize_input_level(input_level_text, raw_sq)
        
        parsed = parse_attribute_name(str(penalties_vals[0]))
        
        penalties  = parse_penalties_from_PENALTIES_ROW([str(v) for v in penalties_vals])
        thresholds = [float(v) for v in crop_vals]
        
        if not parsed:
            print(f"Warning: Unrecognized attribute abbreviation in penalties label: {penalties_vals[0]}")
            col += BLOCK_WIDTH
            continue
        
        if len(parsed) == 1:
            attr_name = parsed[0]
        else:
            if raw_sq == ["SQ3"]:
                attr_name = "SPR"
            else:
                attr_name = "VSP"
            #if sql level == SQ3 then pick "SPR" else pick "VSP"
            
        # Canonical-unit adjustments.
        if attr_name == "RSD":
            thresholds = _convert_rsd_to_mm(thresholds)

        for level in raw_levels:
            effective_sqs = level_sq_map.get(level, raw_sq)
            blocks.append(SoilCharacteristicsBlock(
                col_start      = col,
                col_end        = col + BLOCK_WIDTH,
                attribute_name = attr_name,
                soil_qualities = effective_sqs,
                input_levels   = [level],
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


def resolve_ph_blocks(
    blocks:    List[SoilCharacteristicsBlock],
    ph_report: float,
) -> List[SoilCharacteristicsBlock]:
    """For each (SQ, input_level) group that contains >1 pH block (acidic +
    basic), keep only the curve whose range contains ph_report. Non-pH
    blocks are passed through unchanged."""
    non_ph = [b for b in blocks if b.attribute_name != "pH"]

    ph_groups: dict[tuple, List[SoilCharacteristicsBlock]] = defaultdict(list)
    for b in blocks:
        if b.attribute_name == "pH":
            key = (frozenset(b.soil_qualities), frozenset(b.input_levels))
            ph_groups[key].append(b)

    resolved_ph: List[SoilCharacteristicsBlock] = []
    for _key, ph_blocks in ph_groups.items():
        if len(ph_blocks) == 1:
            resolved_ph.append(ph_blocks[0])
        else:
            resolved_ph.append(select_ph_curve(ph_report, ph_blocks))

    return non_ph + resolved_ph


# ---------------------------------------------------------------------------
# AttributePair builder + pipeline
# ---------------------------------------------------------------------------

def build_attribute_pair(block: SoilCharacteristicsBlock, crop_id: int) -> AttributePair:
    if block.attribute_name in ["SPR", "VSP", "OSD"]:
        thresh_100 = block.thresholds_row[0]
        pair_100 = (100, 0 if thresh_100 == _SENTINEL else thresh_100)

        # Find the penalty where threshold == 1
        pair_1 = next((pen, 1) for pen, thresh in zip(block.penalties, block.thresholds_row) if thresh == 1)

        penalties   = [pair_100[0], pair_1[0]]
        thresholds  = [pair_100[1], pair_1[1]]
                        
        curve = RatingCurve(
            crop_id    = crop_id,
            penalties  = penalties,
            thresholds = thresholds,
        )
    else:
        curve = RatingCurve(
            crop_id    = crop_id,
            penalties  = block.penalties,
            thresholds = [0 if t == _SENTINEL else t for t in block.thresholds_row]
        )
    
    return AttributePair(attribute_name=block.attribute_name, rating_curve=curve)


def run_pipeline(
    csv_path:     str,
    crop_id:      int,
    crops:        dict[int, dict],
    input_level:  InputLevel,
    ph_report:    float,
    output_dir:   str  = ".",
    write_output: bool = False,
) -> Dict[str, pd.DataFrame]:
    df = pd.read_csv(csv_path, header=None)

    if not (2.0 <= ph_report <= 10.5):
        raise ValueError(
            f"ph_report {ph_report} is outside the valid range [2.0, 10.5]."
        )

    all_blocks      = extract_blocks(df, crop_id, crops)
    filtered_blocks = list(filter_blocks_by_input_level(all_blocks, input_level))
    filtered_blocks = resolve_ph_blocks(filtered_blocks, ph_report)

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
        csv_path     = "engines/edaphic_crop_reqs/appendixes/rainfed_sprinkler_appendix/csv_sheets/A6-3.1.csv",
        crop_id      = 4,
        crops        = CROPS_RAINFED_SPRINKLER,
        input_level  = InputLevel.INTERMEDIATE,
        ph_report    = 6.0,
        output_dir   = "engines/edaphic_crop_reqs/results",
        write_output = True,
    )
    print("\n--- SQ1 preview ---")
    print(results.get("SQ1", "not found"))
"""Parser for one appendix source used to build edaphic crop requirement tables."""
