import sqlite3
import json
from gaez_scripts.tiff_layer import TiffLayer, GaezTiffLayer, SoilgridsTiffLayer


def get_connection(db_path: str = "ardhi.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # lets you access columns by name
    return conn


def create_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tiff_files (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path       TEXT NOT NULL UNIQUE,
            source          TEXT NOT NULL,
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

            -- SoilGrids dimensions (NULL for GAEZ)
            attribute_code  TEXT,
            depth           TEXT,
            quantile        TEXT,

            -- Shared
            data_version    INTEGER DEFAULT 1,
            metadata        TEXT,

            CHECK (source IN ('gaez', 'soilgrids'))
        )
    """)
    conn.commit()


def insert_layer(conn: sqlite3.Connection, layer: TiffLayer) -> int:
    """
    Insert a TiffLayer (Gaez or SoilGrids) into tiff_files.
    Returns the new row id.
    Silently skips if file_path already exists (INSERT OR IGNORE).
    """
    category = layer.metadata.get("category", {}).get("name") if layer.metadata else None

    if isinstance(layer, GaezTiffLayer):
        row = (
            layer.local_path,
            layer.source,
            category,
            layer.map_code,
            # GAEZ dims
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
            # SoilGrids dims — all NULL
            None, None, None,
            # metadata
            json.dumps(layer.metadata),
        )
    elif isinstance(layer, SoilgridsTiffLayer):
        row = (
            layer.local_path,
            layer.source,
            category,
            layer.map_code,
            # GAEZ dims — all NULL
            None, None, None, None, None, None, None, None, None, None,
            # SoilGrids dims
            layer.attribute,
            layer.depth,
            layer.quantile,
            # metadata
            json.dumps(layer.metadata),
        )
    else:
        raise TypeError(f"Unsupported layer type: {type(layer)}")

    cur = conn.execute("""
        INSERT OR IGNORE INTO tiff_files (
            file_path, source, category, map_code,
            crop_code, period, climate_model, ssp, input_level,
            water_content, water_supply, management, sq_factor, lc_class,
            attribute_code, depth, quantile,
            metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, row)
    conn.commit()
    return cur.lastrowid

def close_connection(conn: sqlite3.Connection) -> None:
    conn.close()
    
    
