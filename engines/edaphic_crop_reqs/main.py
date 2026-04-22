"""
edaphic_pipeline.py
====================
Full end-to-end production pipeline.

Generates one Excel workbook per valid combination of:
    crop × water_management × input_level × ph_mode × texture_class

Valid crop+water combinations are detected at runtime by scanning the
appendix CSVs — no hardcoded crop lists per water management system.

Parser 4 file mapping (each file encodes its input level in its title):
    .4.csv → HIGH
    .5.csv → INTERMEDIATE
    .6.csv → LOW  (optional — skipped if file does not exist)

Output tree
-----------
edaphic_crop_requirements_xlsx/
    rainfed_sprinkler/
        wheat/
            wheat_rainfed_sprinkler_HIGH_acidic_fine.xlsx
            ...
    irrigated_drip/
        ...
    irrigated_gravity/
        ...

Database
--------
Connects to the existing  edaphic.db  — does NOT recreate it.
Inserts one record per generated file.

Usage
-----
    python -m engines.edaphic_crop_reqs.edaphic_pipeline
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

import pandas as pd

from engines.edaphic_crop_reqs.constants import CROPS_DRIP_IRRIGATION, CROPS_GRAVITY_IRRIGATION, CROPS_RAINFED_SPRINKLER
from engines.edaphic_crop_reqs.models import InputLevel

import engines.edaphic_crop_reqs.appendix6_3_1_parser as parser_1
import engines.edaphic_crop_reqs.appendix6_3_2_parser as parser_2
import engines.edaphic_crop_reqs.appendix6_3_3_parser as parser_3
import engines.edaphic_crop_reqs.appendix6_3_4_parser as parser_4


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OUTPUT_ROOT = "edaphic_crop_requirements_xlsx"
DB_PATH     = "ardhi.db"          # existing DB — do NOT recreate
LOG_PATH    = "edaphic_crop_requirements_xlsx/pipeline.log"

PH_ACIDIC = 5.5
PH_BASIC  = 8.0

TEXTURE_CLASSES = ["fine", "medium", "coarse"]
ALL_SQ_LABELS   = [f"SQ{i}" for i in range(1, 8)]

BASE = "engines/edaphic_crop_reqs/appendixes"


# ---------------------------------------------------------------------------
# Water management configurations
#
# csv_p4_map: maps InputLevel → path of the .4/.5/.6 file for parser_4.
# If a path does not exist on disk the corresponding input level is skipped.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WaterManagementConfig:
    name:      str
    folder:    str
    crops:     dict[int, dict]
    csv_p1:    str          # parser_1 source (used for crop detection too)
    csv_p2:    str          # parser_2 source
    csv_p3:    str          # parser_3 source
    csv_p4_map: Dict[InputLevel, str] = field(default_factory=dict)
    # ^ maps InputLevel → .4/.5/.6 csv path for parser_4


WATER_CONFIGS: List[WaterManagementConfig] = [
    WaterManagementConfig(
        name   = "rainfed_sprinkler",
        folder = "rainfed_sprinkler",
        crops = CROPS_RAINFED_SPRINKLER,
        csv_p1 = f"{BASE}/rainfed_sprinkler_appendix/csv_sheets/A6-3.1.csv",
        csv_p2 = f"{BASE}/rainfed_sprinkler_appendix/csv_sheets/A6-3.2.csv",
        csv_p3 = f"{BASE}/rainfed_sprinkler_appendix/csv_sheets/A6-3.3.csv",
        csv_p4_map = {
            InputLevel.HIGH:         f"{BASE}/rainfed_sprinkler_appendix/csv_sheets/A6-3.4.csv",
            InputLevel.INTERMEDIATE: f"{BASE}/rainfed_sprinkler_appendix/csv_sheets/A6-3.5.csv",
            InputLevel.LOW:          f"{BASE}/rainfed_sprinkler_appendix/csv_sheets/A6-3.6.csv",
        },
    ),
    WaterManagementConfig(
        name   = "irrigated_drip",
        folder = "irrigated_drip",
        crops  = CROPS_DRIP_IRRIGATION,
        csv_p1 = f"{BASE}/drip_irrigation_appendix/csv_sheets/A6-5.1.csv",
        csv_p2 = f"{BASE}/drip_irrigation_appendix/csv_sheets/A6-5.2.csv",
        csv_p3 = f"{BASE}/drip_irrigation_appendix/csv_sheets/A6-5.3.csv",
        csv_p4_map = {
            InputLevel.HIGH:         f"{BASE}/drip_irrigation_appendix/csv_sheets/A6-5.4.csv",
            InputLevel.INTERMEDIATE: f"{BASE}/drip_irrigation_appendix/csv_sheets/A6-5.5.csv",
        },
    ),
    WaterManagementConfig(
        name   = "irrigated_gravity",
        folder = "irrigated_gravity",
        crops = CROPS_GRAVITY_IRRIGATION,
        csv_p1 = f"{BASE}/gravity_irrigation_appendix/csv_sheets/A6-4.1.csv",
        csv_p2 = f"{BASE}/gravity_irrigation_appendix/csv_sheets/A6-4.2.csv",
        csv_p3 = f"{BASE}/gravity_irrigation_appendix/csv_sheets/A6-4.3.csv",
        csv_p4_map = {
            InputLevel.HIGH:         f"{BASE}/gravity_irrigation_appendix/csv_sheets/A6-4.4.csv",
            InputLevel.INTERMEDIATE: f"{BASE}/gravity_irrigation_appendix/csv_sheets/A6-4.5.csv",
        },
    ),
]


# ---------------------------------------------------------------------------
# Job descriptor
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PipelineJob:
    crop_id:       int
    crop_name:     str
    wm:            WaterManagementConfig
    input_level:   InputLevel
    ph_mode:       str      # "acidic" | "basic"
    ph_value:      float
    texture_class: str      # "fine" | "medium" | "coarse"
    csv_p4:        str      # resolved .4/.5/.6 path for this input level

    @property
    def safe_crop_name(self) -> str:
        return self.crop_name.replace(" ", "_")

    @property
    def output_filename(self) -> str:
        return (
            f"{self.safe_crop_name}_{self.wm.name}"
            f"_{self.input_level.value.upper()}"
            f"_{self.ph_mode}_{self.texture_class}.xlsx"
        )

    @property
    def output_dir(self) -> str:
        return os.path.join(OUTPUT_ROOT, self.wm.folder, self.safe_crop_name)

    @property
    def output_path(self) -> str:
        return os.path.join(self.output_dir, self.output_filename)


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
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


logger = _setup_logging()


# ---------------------------------------------------------------------------
# Database  (connect to existing edaphic.db — never recreate)
# ---------------------------------------------------------------------------

_db_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """One connection per thread, WAL mode for safe concurrent writes."""
    if not hasattr(_db_local, "conn"):
        _db_local.conn = sqlite3.connect(DB_PATH)
        _db_local.conn.execute("PRAGMA journal_mode=WAL")
    return _db_local.conn


def ensure_table() -> None:
    """
    Create the outputs table if it does not already exist.
    Safe to call on an existing DB — will not drop or alter existing data.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS edaphic_outputs (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            crop_id          INTEGER NOT NULL,
            crop_name        TEXT    NOT NULL,
            water_management TEXT    NOT NULL,
            input_level      TEXT    NOT NULL,
            ph_mode          TEXT    NOT NULL,
            texture_class    TEXT    NOT NULL,
            filepath         TEXT    NOT NULL UNIQUE,
            generated_at     TEXT    NOT NULL,
            status           TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_crop
            ON edaphic_outputs(crop_id);
        CREATE INDEX IF NOT EXISTS idx_water_mgmt
            ON edaphic_outputs(water_management);
        CREATE INDEX IF NOT EXISTS idx_input_level
            ON edaphic_outputs(input_level);
        CREATE INDEX IF NOT EXISTS idx_status
            ON edaphic_outputs(status);
    """)
    conn.commit()
    conn.close()


def _insert_record(job: PipelineJob, status: str) -> None:
    """
    Insert one record per generated file.
    ON CONFLICT updates status + timestamp so re-runs stay idempotent.
    """
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO edaphic_outputs
            (crop_id, crop_name, water_management, input_level,
             ph_mode, texture_class, filepath, generated_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(filepath) DO UPDATE SET
            status       = excluded.status,
            generated_at = excluded.generated_at
        """,
        (
            job.crop_id,
            job.crop_name,
            job.wm.name,
            job.input_level.value,
            job.ph_mode,
            job.texture_class,
            os.path.abspath(job.output_path),
            datetime.now(timezone.utc).isoformat(),
            status,
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Crop detection
# ---------------------------------------------------------------------------

def detect_available_crops(csv_p1: str) -> Set[int]:
    """
    Scan a water management system's parser-1 CSV and return the set of
    crop IDs actually present. Checks column 0 first, then column 1.
    Returns an empty set (with a warning) if the file is missing.
    """
    if not os.path.exists(csv_p1):
        logger.warning(f"Crop detection: file not found — {csv_p1}")
        return set()
    try:
        df = pd.read_csv(csv_p1, header=None)
        for col_idx in (0, 1):
            id_col = pd.to_numeric(df.iloc[:, col_idx], errors="coerce")
            ids = {
                int(v) for v in id_col.dropna()
                if v == int(v) and 1 <= v <= 200
            }
            if ids:
                return ids
    except Exception as e:
        logger.warning(f"Crop detection failed for {csv_p1}: {e}")
    return set()


# ---------------------------------------------------------------------------
# Directory creation lock
# ---------------------------------------------------------------------------

_mkdir_lock = threading.Lock()


def _safe_makedirs(path: str) -> None:
    with _mkdir_lock:
        os.makedirs(path, exist_ok=True)


# ---------------------------------------------------------------------------
# Core job runner
# ---------------------------------------------------------------------------

def _run_job(job: PipelineJob) -> bool:
    """Run all parsers for one job, write xlsx, record in DB."""

    # Idempotent: skip already-generated files
    if os.path.exists(job.output_path):
        logger.debug(f"SKIP (exists): {job.output_filename}")
        return True

    _safe_makedirs(job.output_dir)

    sq_buckets: Dict[str, List[pd.DataFrame]] = {}

    def _collect(partial: Dict[str, pd.DataFrame]) -> None:
        for sq, df in partial.items():
            sq_buckets.setdefault(sq, []).append(df)

    # Parser 1 — chemical/physical attributes + pH curve selection
    try:
        _collect(parser_1.run_pipeline(
            csv_path     = job.wm.csv_p1,
            crop_id      = job.crop_id,
            input_level  = job.input_level,
            crops = job.wm.crops,
            ph_report    = job.ph_value,
            write_output = False,
        ))
    except Exception as e:
        logger.warning(f"parser_1 [{job.output_filename}]: {e}")

    # Parser 2 — soil texture classes
    try:
        _collect(parser_2.run_pipeline(
            csv_path     = job.wm.csv_p2,
            crop_id      = job.crop_id,
            input_level  = job.input_level,
            crops = job.wm.crops,
            write_output = False,
        ))
    except Exception as e:
        logger.warning(f"parser_2 [{job.output_filename}]: {e}")

    # Parser 3 — drainage classes (texture-filtered)
    try:
        _collect(parser_3.run_pipeline(
            csv_path             = job.wm.csv_p3,
            crop_id              = job.crop_id,
            input_level          = job.input_level,
            crops= job.wm.crops,
            texture_class_report = job.texture_class,
            write_output         = False,
        ))
    except Exception as e:
        logger.warning(f"parser_3 [{job.output_filename}]: {e}")

    # Parser 4 — soil phase (.4/.5/.6 file, input level is passed)
    try:
        _collect(parser_4.run_pipeline(
            csv_path     = job.csv_p4,
            crop_id      = job.crop_id,
            input_level  = job.input_level,
            write_output = False,
        ))
    except Exception as e:
        logger.warning(f"parser_4 [{job.output_filename}]: {e}")

    if not sq_buckets:
        logger.error(f"NO DATA [{job.output_filename}] — all parsers empty")
        _insert_record(job, "failed")
        return False

    # Merge and write xlsx — one sheet per SQ
    try:
        with pd.ExcelWriter(job.output_path, engine="openpyxl") as writer:
            for sq_label in ALL_SQ_LABELS:
                frames = sq_buckets.get(sq_label)
                if not frames:
                    continue
                # concat WITHOUT ignore_index preserves string index labels
                merged = pd.concat(frames)
                merged.to_excel(writer, sheet_name=sq_label, header=False)

        _insert_record(job, "success")
        logger.debug(f"OK: {job.output_path}")
        return True

    except Exception as e:
        logger.error(f"WRITE FAILED [{job.output_filename}]: {e}")
        if os.path.exists(job.output_path):
            os.remove(job.output_path)
        _insert_record(job, "failed")
        return False


# ---------------------------------------------------------------------------
# Job generator
# ---------------------------------------------------------------------------

def _generate_jobs() -> List[PipelineJob]:
    """
    Build the full job list.

    For each water management system:
      1. Detect which crop IDs are actually present in its CSV files
      2. For each available input level (only if the .4/.5/.6 file exists):
         - skip if no file on disk
         - generate jobs only for detected crops × pH modes × textures
    """
    jobs: List[PipelineJob] = []

    for wm in WATER_CONFIGS:
        # Detect available crops for this water management system
        available_crop_ids = detect_available_crops(wm.csv_p1)
        if not available_crop_ids:
            logger.warning(f"[{wm.name}] No crops detected — skipping entire system")
            continue

        logger.info(
            f"[{wm.name}] Detected {len(available_crop_ids)} crops "
            f"(IDs {min(available_crop_ids)}–{max(available_crop_ids)})"
        )

        for input_level, csv_p4_path in wm.csv_p4_map.items():
            # Skip this input level if the corresponding soil phase file is missing
            if not os.path.exists(csv_p4_path):
                logger.info(
                    f"[{wm.name}] {input_level.value} skipped "
                    f"— file not found: {csv_p4_path}"
                )
                continue

            for crop_id in sorted(available_crop_ids):
                crop_info = wm.crops.get(crop_id)
                if not crop_info:
                    continue   # crop ID exists in CSV but not in constants — skip
                
                crop_name = crop_info["name"]

                for ph_mode, ph_value in [("acidic", PH_ACIDIC), ("basic", PH_BASIC)]:
                    for texture_class in TEXTURE_CLASSES:
                        jobs.append(PipelineJob(
                            crop_id       = crop_id,
                            crop_name     = crop_name,
                            wm            = wm,
                            input_level   = input_level,
                            ph_mode       = ph_mode,
                            ph_value      = ph_value,
                            texture_class = texture_class,
                            csv_p4        = csv_p4_path,
                        ))

    return jobs


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_full_pipeline(max_workers: int = 8) -> None:
    """
    Generate all valid outputs in parallel and record results in edaphic.db.

    Parameters
    ----------
    max_workers : parallel threads (I/O-bound; 8–16 recommended)
    """
    ensure_table()   # safe on existing DB — CREATE IF NOT EXISTS only

    jobs  = _generate_jobs()
    total = len(jobs)

    logger.info(
        f"Pipeline starting — {total} jobs | "
        f"{len(WATER_CONFIGS)} water systems | workers={max_workers}"
    )

    if total == 0:
        logger.warning("No jobs generated — check that CSV files exist on disk.")
        return

    succeeded    = 0
    failed       = 0
    counter_lock = threading.Lock()

    def _tracked(job: PipelineJob) -> None:
        nonlocal succeeded, failed
        ok = _run_job(job)
        with counter_lock:
            if ok:
                succeeded += 1
            else:
                failed += 1
            done = succeeded + failed
            if done % 100 == 0 or done == total:
                logger.info(f"Progress {done}/{total} | ok={succeeded} fail={failed}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_tracked, job) for job in jobs]
        for _ in as_completed(futures):
            pass
        

    logger.info(f"Done — {succeeded} succeeded, {failed} failed out of {total}")
    logger.info(f"DB  → {os.path.abspath(DB_PATH)}")
    logger.info(f"Log → {os.path.abspath(LOG_PATH)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_full_pipeline(max_workers=8)