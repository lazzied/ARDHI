import logging
import os
import sqlite3

from ardhi_db import close_connection, get_connection, insert_layer
from data_scripts.gaez_scripts.TIFFpipeline import Downloader
from data_scripts.gaez_scripts.tiff_layer import from_url

logger = logging.getLogger(__name__)

URLS    = "gaez_data/links/filtered_tiff_files.txt"
DB_PATH = "ardhi.db"

with open(URLS) as f:
    conn     = None
    errors   = 0
    warnings = 0
    inserted = 0

    try:
        for url in f:
            layer = from_url(url)
            layer.local_path = f"D:/ARDHI/TIFF/clipped/{Downloader.get_filename(url)}"

            issues = layer.validate()
            if issues:
                logger.warning(f"Validation: {layer.filename} — {issues}")
                warnings += 1

            conn = get_connection(DB_PATH)
            insert_layer(conn, layer)
            conn.commit()
            inserted += 1

    except sqlite3.OperationalError as e:
        logger.error(f"Insert failed: {os.path.basename(layer.local_path)} — {e}")
        if conn:
            conn.rollback()
        errors += 1

    except Exception as e:
        logger.error(f"Insert failed: {os.path.basename(layer.local_path)} — {e}")
        errors += 1

    finally:
        if conn:
            close_connection(conn)