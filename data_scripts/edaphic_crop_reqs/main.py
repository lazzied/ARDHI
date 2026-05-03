"""
High-level entrypoint for building edaphic crop-requirement artifacts.

edaphic_pipeline.py
====================
Sequential pipeline built on top of `run_aggregator`.

For every valid combination of:
    water_system × crop × input_level × ph_level × texture_class
the orchestrator is called once. Its per-SQ DataFrames are merged into one
xlsx (one sheet per SQ). One row per output is recorded in `edaphic_outputs`.

The orchestrator writes intermediate per-SQ CSVs as a side effect; we point
it at a TemporaryDirectory so those CSVs are deleted automatically once the
xlsx is built.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List

import pandas as pd

from engines.edaphic_crop_reqs.constants import (
    CROPS_RAINFED_SPRINKLER,
    CROPS_DRIP_IRRIGATION,
    CROPS_GRAVITY_IRRIGATION,
)
from engines.edaphic_crop_reqs.models import InputLevel
from engines.edaphic_crop_reqs.edaphic_orchestrator import run_trio_aggregators

import engines.edaphic_crop_reqs.appendix6_3_1_parser as parser_1
import engines.edaphic_crop_reqs.appendix6_3_2_parser as parser_2
import engines.edaphic_crop_reqs.appendix6_3_3_parser as parser_3
import engines.edaphic_crop_reqs.appendix6_3_4_parser as parser_4
from engines.edaphic_crop_reqs.utils_functions import write_sq_df_to_csv


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OUTPUT_ROOT = "edaphic_crop_requirements_xlsx"
DB_PATH     = "ardhi.db"
LOG_PATH    = f"{OUTPUT_ROOT}/pipeline.log"

PH_ACIDIC = 5.5
PH_BASIC  = 8.0

TEXTURE_CLASSES = ["fine", "medium", "coarse"]
ALL_SQ_LABELS   = [f"SQ{i}" for i in range(1, 8)]

BASE = "engines/edaphic_crop_reqs/appendixes"


# ---------------------------------------------------------------------------
# Water management systems
#
# Each system carries the parser registry that `run_aggregator` will iterate.
# `valid_input_levels` enumerates which input levels actually have a
# corresponding parser_4 file (drip & gravity have no LOW).
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WaterSystem:
    name:               str
    folder:             str
    crops:              dict[int, dict]
    parser_registry:    list
    valid_input_levels: list[InputLevel]


WATER_SYSTEMS: List[WaterSystem] = [
    WaterSystem(
        name   = "rainfed_sprinkler",
        folder = "rainfed_sprinkler",
        crops  = CROPS_RAINFED_SPRINKLER,
        parser_registry = [
            (parser_1, f"{BASE}/rainfed_sprinkler_appendix/csv_sheets/A6-3.1.csv", True),
            (parser_2, f"{BASE}/rainfed_sprinkler_appendix/csv_sheets/A6-3.2.csv", True),
            (parser_3, f"{BASE}/rainfed_sprinkler_appendix/csv_sheets/A6-3.3.csv", True),
            (parser_4, f"{BASE}/rainfed_sprinkler_appendix/csv_sheets/A6-3.4.csv", InputLevel.HIGH),
            (parser_4, f"{BASE}/rainfed_sprinkler_appendix/csv_sheets/A6-3.5.csv", InputLevel.INTERMEDIATE),
            (parser_4, f"{BASE}/rainfed_sprinkler_appendix/csv_sheets/A6-3.6.csv", InputLevel.LOW),
        ],
        valid_input_levels = [InputLevel.HIGH, InputLevel.INTERMEDIATE, InputLevel.LOW],
    ),
    WaterSystem(
        name   = "irrigated_drip",
        folder = "irrigated_drip",
        crops  = CROPS_DRIP_IRRIGATION,
        parser_registry = [
            (parser_1, f"{BASE}/drip_irrigation_appendix/csv_sheets/A6-5.1.csv", True),
            (parser_2, f"{BASE}/drip_irrigation_appendix/csv_sheets/A6-5.2.csv", True),
            (parser_3, f"{BASE}/drip_irrigation_appendix/csv_sheets/A6-5.3.csv", True),
            (parser_4, f"{BASE}/drip_irrigation_appendix/csv_sheets/A6-5.4.csv", InputLevel.HIGH),
            (parser_4, f"{BASE}/drip_irrigation_appendix/csv_sheets/A6-5.5.csv", InputLevel.INTERMEDIATE),
        ],
        valid_input_levels = [InputLevel.HIGH, InputLevel.INTERMEDIATE],
    ),
    WaterSystem(
        name   = "irrigated_gravity",
        folder = "irrigated_gravity",
        crops  = CROPS_GRAVITY_IRRIGATION,
        parser_registry = [
            (parser_1, f"{BASE}/gravity_irrigation_appendix/csv_sheets/A6-4.1.csv", True),
            (parser_2, f"{BASE}/gravity_irrigation_appendix/csv_sheets/A6-4.2.csv", True),
            (parser_3, f"{BASE}/gravity_irrigation_appendix/csv_sheets/A6-4.3.csv", True),
            (parser_4, f"{BASE}/gravity_irrigation_appendix/csv_sheets/A6-4.4.csv", InputLevel.HIGH),
            (parser_4, f"{BASE}/gravity_irrigation_appendix/csv_sheets/A6-4.5.csv", InputLevel.INTERMEDIATE),
        ],
        valid_input_levels = [InputLevel.HIGH, InputLevel.INTERMEDIATE],
    ),
]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _setup_logging() -> logging.Logger:
    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    logger = logging.getLogger("edaphic_pipeline")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
    fh.setLevel(logging.DEBUG); fh.setFormatter(fmt); logger.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO);  ch.setFormatter(fmt); logger.addHandler(ch)
    return logger


logger = _setup_logging()


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def ensure_table() -> None:
    """Create edaphic_outputs if missing — never drops or alters existing data."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS edaphic_outputs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                crop_id          INTEGER NOT NULL,
                crop_name        TEXT    NOT NULL,
                water_supply TEXT    NOT NULL,
                input_level      TEXT    NOT NULL,
                ph_level          TEXT    NOT NULL,
                texture_class    TEXT    NOT NULL,
                file_path         TEXT    NOT NULL UNIQUE,
                generated_at     TEXT    NOT NULL,
                status           TEXT    NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_crop        ON edaphic_outputs(crop_id);
            CREATE INDEX IF NOT EXISTS idx_water_supply ON edaphic_outputs(water_supply);
            CREATE INDEX IF NOT EXISTS idx_input_level ON edaphic_outputs(input_level);
            CREATE INDEX IF NOT EXISTS idx_status      ON edaphic_outputs(status);
        """)


def insert_record(
    conn: sqlite3.Connection,
    *, crop_id: int, crop_name: str, wm_name: str, input_level: str,
    ph_level: str, texture_class: str, filepath: str, status: str,
) -> None:
    conn.execute(
        """
        INSERT INTO edaphic_outputs
            (crop_id, crop_name, water_supply, input_level,
             ph_level, texture_class, file_path, generated_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(file_path) DO UPDATE SET
            status       = excluded.status,
            generated_at = excluded.generated_at
        """,
        (crop_id, crop_name, wm_name, input_level,
         ph_level, texture_class, os.path.abspath(filepath),
         datetime.now(timezone.utc).isoformat(), status),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _safe_crop(name: str) -> str:
    return name.replace(" ", "_")


def _output_path(wm: WaterSystem, crop_name: str, input_level: InputLevel,
                 ph_level: str, texture_class: str) -> str:
    fname = (
        f"{_safe_crop(crop_name)}_{wm.name}"
        f"_{input_level.value.upper()}_{ph_level}_{texture_class}.xlsx"
    )
    return os.path.join(OUTPUT_ROOT, wm.folder, _safe_crop(crop_name), fname)


def _write_xlsx(sq_dict: Dict[str, pd.DataFrame], out_path: str) -> None:
    """Merge per-SQ DataFrames into one xlsx, one sheet per SQ."""
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for sq_label in ALL_SQ_LABELS:
            df = sq_dict.get(sq_label)
            if df is None or df.empty:
                continue
            df.to_excel(writer, sheet_name=sq_label, header=False)


# ---------------------------------------------------------------------------
# Single combination runner
# ---------------------------------------------------------------------------

def run_one(wm: WaterSystem, crop_id: int, crop_name: str,
            ph_level: str, ph_value: float,
            texture_class: str, conn: sqlite3.Connection) -> bool:

    with tempfile.TemporaryDirectory(prefix="edaphic_") as tmp:
        try:
            all_results = run_trio_aggregators(
                crops                = wm.crops,
                crop_id              = crop_id,
                ph_report            = ph_value,
                texture_class_report = texture_class,
                output_dir           = tmp,
                parser_registry      = wm.parser_registry,
            )
        except Exception as e:
            logger.error(f"FAIL [{crop_name}] orchestrator raised: {e}")
            for input_level in wm.valid_input_levels:
                out_path = _output_path(wm, crop_name, input_level, ph_level, texture_class)
                insert_record(conn, crop_id=crop_id, crop_name=crop_name,
                              wm_name=wm.name, input_level=input_level.value,
                              ph_level=ph_level, texture_class=texture_class,
                              filepath=out_path, status="failed")
            return False

        # Write CSVs per level into tmp subdirs, then merge into xlsx
        all_ok = True
        for input_level in wm.valid_input_levels:
            sq_dict  = all_results.get(input_level.value, {})
            out_path = _output_path(wm, crop_name, input_level, ph_level, texture_class)

            if os.path.exists(out_path):
                logger.debug(f"SKIP (exists): {out_path}")
                continue

            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            if not sq_dict:
                logger.error(f"NO DATA [{out_path}]")
                insert_record(conn, crop_id=crop_id, crop_name=crop_name,
                              wm_name=wm.name, input_level=input_level.value,
                              ph_level=ph_level, texture_class=texture_class,
                              filepath=out_path, status="failed")
                all_ok = False
                continue

            # Write CSVs for this level into its own subdir
            level_dir = os.path.join(tmp, input_level.value)
            os.makedirs(level_dir, exist_ok=True)
            for sq_label, df in sq_dict.items():
                write_sq_df_to_csv(df, os.path.join(level_dir, f"{sq_label}.csv"))

            try:
                _write_xlsx(sq_dict, out_path)
            except Exception as e:
                logger.error(f"WRITE FAILED [{out_path}]: {e}")
                if os.path.exists(out_path): os.remove(out_path)
                insert_record(conn, crop_id=crop_id, crop_name=crop_name,
                              wm_name=wm.name, input_level=input_level.value,
                              ph_level=ph_level, texture_class=texture_class,
                              filepath=out_path, status="failed")
                all_ok = False
                continue

            insert_record(conn, crop_id=crop_id, crop_name=crop_name,
                          wm_name=wm.name, input_level=input_level.value,
                          ph_level=ph_level, texture_class=texture_class,
                          filepath=out_path, status="success")
            logger.debug(f"OK: {out_path}")

    return all_ok


def run_full_pipeline() -> None:
    ensure_table()

    total = sum(
        len(wm.crops) * 2 * len(TEXTURE_CLASSES)   # one trio call per crop × ph × texture
        for wm in WATER_SYSTEMS
    )
    logger.info(f"Pipeline start — {total} trio jobs across {len(WATER_SYSTEMS)} water systems")

    succeeded = failed = done = 0

    with sqlite3.connect(DB_PATH) as conn:
        for wm in WATER_SYSTEMS:
            for crop_id, crop_info in sorted(wm.crops.items()):
                crop_name = crop_info["name"]
                for ph_level, ph_value in [("acidic", PH_ACIDIC), ("basic", PH_BASIC)]:
                    for texture_class in TEXTURE_CLASSES:
                        ok = run_one(wm, crop_id, crop_name,
                                     ph_level, ph_value,
                                     texture_class, conn)
                        done += 1
                        if ok: succeeded += 1
                        else:  failed += 1
                        if done % 100 == 0 or done == total:
                            logger.info(
                                f"Progress {done}/{total} | "
                                f"ok={succeeded} fail={failed}"
                            )

    logger.info(f"Done — {succeeded} succeeded, {failed} failed out of {total}")
    logger.info(f"DB  → {os.path.abspath(DB_PATH)}")
    logger.info(f"Log → {os.path.abspath(LOG_PATH)}")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_full_pipeline()
