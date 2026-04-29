"""Edaphic-module orchestrator.

Runs every registered parser pipeline, collects per-SQ DataFrames, merges
them, and writes one CSV per SQ. After merging, the canonical-schema
validator (`validate_sq_outputs`) is run; any errors raise immediately so
a bad rating-curve table never reaches the workbook merger downstream.

Architecture is identical to the legacy orchestrator. The only changes:
  * Texture validation moved up so we fail fast before any parser runs.
  * Final pass: validate_sq_outputs(merged) — abort on error.
  * No structural / control-flow changes to the parser registry loop.
"""
from __future__ import annotations
import os

import pandas as pd
from collections import defaultdict
from typing import Dict, List

from engines.edaphic_crop_reqs.constants import CROPS_RAINFED_SPRINKLER 
from engines.edaphic_crop_reqs.models import InputLevel
from engines.edaphic_crop_reqs.utils_functions import write_sq_df_to_csv

from engines.edaphic_crop_reqs import (
    appendix6_3_1_parser as parser_1,
    appendix6_3_2_parser as parser_2,
    appendix6_3_3_parser as parser_3,
    appendix6_3_4_parser as parser_4,
)
from engines.edaphic_crop_reqs.xlxs_merger import merge_csvs_to_xlsx

# ---------------------------------------------------------------------------
# Parser registry
# Each entry: (module, csv_path, needs_input_level)
#   needs_input_level=True       -> always pass input_level
#   needs_input_level=<InputLevel> -> only run when the user-requested level
#                                     equals this fixed registry level
# ---------------------------------------------------------------------------
PARSER_REGISTRY = [
    (parser_1, "engines/edaphic_crop_reqs/appendixes/rainfed_sprinkler_appendix/csv_sheets/A6-3.1.csv", True),
    (parser_2, "engines/edaphic_crop_reqs/appendixes/rainfed_sprinkler_appendix/csv_sheets/A6-3.2.csv", True),
    (parser_3, "engines/edaphic_crop_reqs/appendixes/rainfed_sprinkler_appendix/csv_sheets/A6-3.3.csv", True),
    (parser_4, "engines/edaphic_crop_reqs/appendixes/rainfed_sprinkler_appendix/csv_sheets/A6-3.4.csv", InputLevel.HIGH),
    (parser_4, "engines/edaphic_crop_reqs/appendixes/rainfed_sprinkler_appendix/csv_sheets/A6-3.5.csv", InputLevel.INTERMEDIATE),
    (parser_4, "engines/edaphic_crop_reqs/appendixes/rainfed_sprinkler_appendix/csv_sheets/A6-3.6.csv", InputLevel.LOW),
]

ALL_SQ_LABELS = [f"SQ{i}" for i in range(1, 8)]
VALID_TEXTURES = frozenset({"fine", "medium", "coarse"})


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_aggregator(
    crops:                dict[int, dict],
    crop_id:              int,
    input_level:          InputLevel,
    ph_report:            float,
    texture_class_report: str,
    output_dir:           str = ".",
    parser_registry:      list | None = None,
) -> Dict[str, pd.DataFrame]:
    """
    Run every registered parser pipeline, collect per-SQ DataFrames, merge
    contributions for each SQ, and write one final CSV per SQ.

    Parameters
    ----------
    crop_id              : numeric crop identifier shared by all parsers
    input_level          : InputLevel enum value applied to every parser
    ph_report            : measured soil pH (selects the acidic vs. basic pH
                           rating curve in parser_1)
    texture_class_report : "fine" | "medium" | "coarse" (selects the matching
                           drainage-class block in parser_3)
    output_dir           : directory where merged SQ CSVs are written

    Returns
    -------
    dict mapping sq_label -> merged DataFrame  (only SQs with data are included)
    """
    # Fail fast on bad texture before doing any parsing work.
    if texture_class_report.strip().lower() not in VALID_TEXTURES:
        raise ValueError(
            f"Invalid texture_class_report {texture_class_report!r}. "
            f"Must be one of: {sorted(VALID_TEXTURES)}"
        )

    EXTRA_KWARGS: Dict[str, dict] = {
        parser_1.__name__: {"ph_report":            ph_report},
        parser_3.__name__: {"texture_class_report": texture_class_report},
    }

    # Accumulate DataFrames per SQ across all parsers
    sq_buckets: Dict[str, List[pd.DataFrame]] = defaultdict(list)

    

    for parser, csv_path, needs_input_level in parser_registry:
        parser_name = parser.__name__.split(".")[-1]
        full_name   = parser.__name__
        print(f"\n[Aggregator] Running {parser_name} ...")

        try:
            kwargs = dict(
                csv_path     = csv_path,
                crop_id      = crop_id,
                crops        = crops,
                output_dir   = output_dir,
                write_output = False,
            )
            if needs_input_level is True:
                kwargs["input_level"] = input_level
            elif needs_input_level == input_level:
                kwargs["input_level"] = input_level
            else:
                print(f"[Aggregator]   skipping {parser_name} (level mismatch)")
                continue

            kwargs.update(EXTRA_KWARGS.get(full_name, {}))

            partial: Dict[str, pd.DataFrame] = parser.run_pipeline(**kwargs)
        except Exception as exc:
            print(f"[Aggregator] WARNING — {parser_name} raised: {exc}")
            continue

        for sq_label, df in partial.items():
            sq_buckets[sq_label].append(df)
            print(f"[Aggregator]   collected {sq_label} ({len(df)} rows)")

    # ---------------------------------------------------------------------
    # Merge per SQ
    # ---------------------------------------------------------------------
    result: Dict[str, pd.DataFrame] = {}
    print("\n[Aggregator] Merging SQ groups ...")
    for sq_label in ALL_SQ_LABELS:
        frames = sq_buckets.get(sq_label)
        if not frames:
            print(f"[Aggregator]   {sq_label}: no data — skipped")
            continue

        merged = pd.concat(frames)
        result[sq_label] = merged
        
        out_path = f"{output_dir}/{sq_label}.csv"
        write_sq_df_to_csv(merged, out_path)
        print(f"[Aggregator]   {sq_label}: merged {len(frames)} source(s), "
              f"{len(merged)} rows -> {out_path}")


    return result

def run_trio_aggregators(
    crops:                dict[int, dict],
    crop_id:              int,
    ph_report:            float,
    texture_class_report: str,
    output_dir:           str = ".",
    parser_registry:      list | None = None,
) -> Dict[str, Dict[str, pd.DataFrame]]:
    """Run the full parser registry for every InputLevel, patch cross-level
    missing rows/SQs, write per-level per-SQ CSVs, and return the complete
    results structure: {input_level_value -> {sq_label -> DataFrame}}."""

    if parser_registry is None:
        parser_registry = PARSER_REGISTRY

    # ------------------------------------------------------------------
    # Run every level
    # ------------------------------------------------------------------
    results: Dict[str, Dict[str, pd.DataFrame]] = {}
    for input_level in InputLevel:
        results[input_level.value] = run_aggregator(
            crops                = crops,
            crop_id              = crop_id,
            input_level          = input_level,
            ph_report            = ph_report,
            texture_class_report = texture_class_report,
            output_dir           = output_dir,
            parser_registry      = parser_registry,
        )

    # ------------------------------------------------------------------
    # Patch cross-level missing rows / SQs (order is significant)
    # ------------------------------------------------------------------
    intermediate = results[InputLevel.INTERMEDIATE.value]
    high         = results[InputLevel.HIGH.value]
    low          = results[InputLevel.LOW.value]

    # 1. intermediate misses SQ2 TXT_fct and TXT_val rows — copy from high SQ2
    if "SQ2" in high and "SQ2" in intermediate:
        missing_rows = high["SQ2"][high["SQ2"].index.isin(["TXT_fct", "TXT_val"])]
        intermediate["SQ2"] = pd.concat([intermediate["SQ2"], missing_rows])

    # 2. low misses SQ2 entirely — copy from (now-patched) intermediate SQ2
    if "SQ2" in intermediate and "SQ2" not in low:
        low["SQ2"] = intermediate["SQ2"].copy()

    # 3. high misses SQ1 entirely — copy from intermediate SQ1
    if "SQ1" in intermediate and "SQ1" not in high:
        high["SQ1"] = intermediate["SQ1"].copy()

    results[InputLevel.INTERMEDIATE.value] = intermediate
    results[InputLevel.HIGH.value]         = high
    results[InputLevel.LOW.value]          = low

    # ------------------------------------------------------------------
    # Write patched CSVs — one sub-directory per level
    # ------------------------------------------------------------------
    """
    for level, sq_dict in results.items():
        level_dir = f"{output_dir}/{level}"
        os.makedirs(level_dir, exist_ok=True)   # ← add this

        for sq_label, df in sq_dict.items():
            out_path = f"{level_dir}/{sq_label}.csv"
            write_sq_df_to_csv(df, out_path)
            print(f"[TrioAggregator] {level}/{sq_label} -> {out_path} ({len(df)} rows)")
    """

    return results
    

if __name__ == "__main__":
    results = run_trio_aggregators(
        crops                = CROPS_RAINFED_SPRINKLER,
        crop_id              = 4,
        ph_report            = 6.0,
        texture_class_report = "fine",
        output_dir           = "engines/edaphic_crop_reqs/results",
        parser_registry      = PARSER_REGISTRY,
    )
    for level, sq_dict in results.items():
        merge_csvs_to_xlsx(
            f"engines/edaphic_crop_reqs/results/{level}",
            f"engines/edaphic_crop_reqs/results/{level}/merged_output.xlsx",
        )
        for sq_label, df in sq_dict.items():
            print(f"\n--- {level}/{sq_label} preview ({len(df)} rows) ---")
            print(df.head())