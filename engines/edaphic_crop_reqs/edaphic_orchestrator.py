from __future__ import annotations

import pandas as pd
from collections import defaultdict
from typing import Dict, List

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
# Set needs_input_level=False for parsers that auto-detect the level from the CSV.
# Add or remove parsers here without touching any other code.
# ---------------------------------------------------------------------------
PARSER_REGISTRY = [
    (parser_1, "engines/edaphic_crop_reqs/appendixes/appendix6_3_1.csv", True),
    (parser_2, "engines/edaphic_crop_reqs/appendixes/appendix6_3_2.csv", True),
    (parser_3, "engines/edaphic_crop_reqs/appendixes/appendix6_3_3.csv", True),
    (parser_4, "engines/edaphic_crop_reqs/appendixes/appendix6_3_4.csv", False),
]

ALL_SQ_LABELS = [f"SQ{i}" for i in range(1, 8)]   # SQ1 … SQ7


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_aggregator(
    crop_id:              int,
    input_level:          InputLevel,
    ph_report:            float,
    texture_class_report: str,
    output_dir:           str = ".",
) -> Dict[str, pd.DataFrame]:
    """
    Run every registered parser pipeline, collect their per-SQ DataFrames,
    merge contributions for each SQ, and write one final CSV per SQ.

    Parameters
    ----------
    crop_id              : numeric crop identifier shared by all parsers
    input_level          : InputLevel enum value applied to every parser
    ph_report            : measured soil pH — passed to parser_1 to select
                           the correct acidic or basic pH curve
    texture_class_report : "fine" | "medium" | "coarse" — passed to parser_3
                           to select the correct drainage-class block
    output_dir           : directory where the merged SQ CSVs are written

    Returns
    -------
    dict mapping sq_label → merged DataFrame  (only SQs with data are included)
    """
    # Extra kwargs forwarded only to the parsers that need them
    EXTRA_KWARGS: Dict[str, dict] = {
        parser_1.__name__: {"ph_report": ph_report},
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
                output_dir   = output_dir,
                write_output = False,   # parsers never write intermediate files
            )
            if needs_input_level:
                kwargs["input_level"] = input_level
            kwargs.update(EXTRA_KWARGS.get(full_name, {}))

            partial: Dict[str, pd.DataFrame] = parser.run_pipeline(**kwargs)
        except Exception as exc:
            print(f"[Aggregator] WARNING — {parser_name} raised: {exc}")
            continue

        for sq_label, df in partial.items():
            sq_buckets[sq_label].append(df)
            print(f"[Aggregator]   collected {sq_label} ({len(df)} rows)")

    # Merge and write one final file per SQ
    result: Dict[str, pd.DataFrame] = {}

    print("\n[Aggregator] Merging SQ groups ...")
    for sq_label in ALL_SQ_LABELS:
        frames = sq_buckets.get(sq_label)

        if not frames:
            print(f"[Aggregator]   {sq_label}: no data — skipped")
            continue

        merged = pd.concat(frames, ignore_index=True)
        out_path = f"{output_dir}/{sq_label}_merged.csv"
        write_sq_df_to_csv(merged, out_path)

        result[sq_label] = merged
        print(f"[Aggregator]   {sq_label}: merged {len(frames)} source(s), "
              f"{len(merged)} rows → {out_path}")

    print(f"\n[Aggregator] Done. {len(result)} SQ file(s) written.")
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    results = run_aggregator(
        crop_id              = 4,
        input_level          = InputLevel.INTERMEDIATE,
        ph_report            = 6.0,
        texture_class_report = "fine",
        output_dir           = "engines/edaphic_crop_reqs/results",
    )

    # Spot-check: print the head of every merged SQ
    for sq_label, df in results.items():
        print(f"\n--- {sq_label} preview ({len(df)} rows) ---")
        print(df.head())