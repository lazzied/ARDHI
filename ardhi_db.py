import sqlite3
import json
from gaez_scripts.tiff_layer import TiffLayer


def get_connection(db_path: str = "ardhi.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def create_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tiff_files (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path       TEXT NOT NULL UNIQUE,
            source          TEXT NOT NULL DEFAULT 'gaez',
            category        TEXT,
            map_code        TEXT NOT NULL,

            -- GAEZ dimensions (NULL when not applicable)
            crop_code       TEXT,
            period          TEXT,
            climate_model   TEXT,
            ssp             TEXT,
            input_level     TEXT,
            water_content   TEXT,
            water_supply    TEXT,
            management      TEXT,
            sq_factor       TEXT,
            lc_class        TEXT,

            -- Shared
            data_version    INTEGER DEFAULT 1,
            metadata        TEXT
        )
    """)
    conn.commit()


def insert_layer(conn: sqlite3.Connection, layer: TiffLayer) -> int:
    """
    Insert a TiffLayer into tiff_files.
    Returns the new row id.
    Silently skips if file_path already exists (INSERT OR IGNORE).
    """
    category = layer.metadata.get("category", {}).get("name") if layer.metadata else None

    row = (
        layer.local_path,
        layer.source,
        category,
        layer.map_code,
        layer.crop_code,
        layer.period,
        layer.climate_model,
        layer.ssp,
        layer.input_level,
        layer.water_content,
        layer.water_supply,
        layer.management,
        layer.sq_factor,
        layer.lc_class,
        json.dumps(layer.metadata),
    )

    cur = conn.execute("""
        INSERT OR IGNORE INTO tiff_files (
            file_path, source, category, map_code,
            crop_code, period, climate_model, ssp, input_level,
            water_content, water_supply, management, sq_factor, lc_class,
            metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, row)
    conn.commit()
    return cur.lastrowid


def close_connection(conn: sqlite3.Connection) -> None:
    conn.close()