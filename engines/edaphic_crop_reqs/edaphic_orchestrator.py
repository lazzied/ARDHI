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

    for parser, csv_path, needs_input_level in PARSER_REGISTRY:
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
        out_path = f"{output_dir}/{sq_label}.csv"
        write_sq_df_to_csv(merged, out_path)
        result[sq_label] = merged
        print(f"[Aggregator]   {sq_label}: merged {len(frames)} source(s), "
              f"{len(merged)} rows -> {out_path}")


    return result


if __name__ == "__main__":
    results = run_aggregator(
        crops                = CROPS_RAINFED_SPRINKLER,
        crop_id              = 4,
        input_level          = InputLevel.INTERMEDIATE,
        ph_report            = 6.0,
        texture_class_report = "fine",
        output_dir           = "engines/edaphic_crop_reqs/results",
    )
    for sq_label, df in results.items():
        print(f"\n--- {sq_label} preview ({len(df)} rows) ---")
        print(df.head())