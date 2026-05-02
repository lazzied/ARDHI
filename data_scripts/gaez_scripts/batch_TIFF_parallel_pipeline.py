

import os
import time
import sqlite3
import logging
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed

from data_scripts.gaez_scripts.tiff_layer import from_url, TiffLayer
from ardhi_db import get_connection, close_connection, insert_layer
from data_scripts.gaez_scripts.TIFFpipeline import Downloader, RasterProcessor


SHAPEFILE       = "gaez_data/tunisia_Tunisia_Country_Boundary/tunisia_Tunisia_Country_Boundary.shp"
RAW_FOLDER      = "D:/ARDHI/TIFF/raw"         # downloads land here
CLIPPED_FOLDER  = "D:/ARDHI/TIFF/clipped"      # clipped files go here
TIFF_URLS       = "gaez_data/links/missing_tiff_files.txt"
DB_PATH         = "ardhi.db"

DOWNLOAD_WORKERS = 12      # threads — tune to your bandwidth
CLIP_WORKERS     = None    # processes — defaults to os.cpu_count()
MAX_RETRIES      = 3
RETRY_DELAY      = 5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def download_one(url: str) -> tuple[str, str | None, str | None]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            path = Downloader.download_url(url, RAW_FOLDER)
            if not os.path.exists(path):
                raise FileNotFoundError(f"Missing after download: {path}")
            return (url, path, None)
        except Exception as e:
            if attempt < MAX_RETRIES:
                log.warning(f"Attempt {attempt}/{MAX_RETRIES} failed for "
                           f"{Downloader.get_filename(url)}: {e} — retrying in {RETRY_DELAY}s")
                time.sleep(RETRY_DELAY)
            else:
                return (url, None, str(e))


def stage_download(urls: list[str]) -> dict[str, str]:
    """Download all URLs. Returns {url: local_path} for successes."""
    log.info(f"Stage 1: Downloading {len(urls)} files with {DOWNLOAD_WORKERS} threads")
    downloaded = {}
    failed = []

    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        futures = {pool.submit(download_one, url): url for url in urls}
        for future in as_completed(futures):
            url, path, error = future.result()
            if error:
                log.error(f"Download failed: {Downloader.get_filename(url)} — {error}")
                failed.append(url)
            else:
                downloaded[url] = path

    log.info(f"Stage 1 done: {len(downloaded)} downloaded, {len(failed)} failed")
    return downloaded



def clip_one(args: tuple[str, str, str, str]) -> tuple[str, str | None, str | None]:
    """
    Clip a single tiff to shapefile bounds.
    Runs in a separate process — no shared state.
    Returns (url, clipped_path, error).
    """
    url, raw_path, shapefile, output_folder = args
    try:
        os.makedirs(output_folder, exist_ok=True)
        filename = os.path.basename(raw_path)
        clipped_path = os.path.join(output_folder, filename)

        processor = RasterProcessor()
        raster_data = processor.process(raw_path, shapefile)
        processor.save(raster_data, clipped_path)

        return (url, clipped_path, None)
    except Exception as e:
        return (url, None, str(e))


def stage_clip(downloaded: dict[str, str]) -> dict[str, str]:
    """Clip all downloaded files. Returns {url: clipped_path} for successes."""
    log.info(f"Stage 2: Clipping {len(downloaded)} files with {CLIP_WORKERS or os.cpu_count()} processes")
    clipped = {}
    failed = []

    tasks = [
        (url, raw_path, SHAPEFILE, CLIPPED_FOLDER)
        for url, raw_path in downloaded.items()
    ]

    with ProcessPoolExecutor(max_workers=CLIP_WORKERS) as pool:
        futures = {pool.submit(clip_one, task): task[0] for task in tasks}
        for future in as_completed(futures):
            url, path, error = future.result()
            if error:
                log.error(f"Clip failed: {os.path.basename(downloaded[url])} — {error}")
                failed.append(url)
            else:
                clipped[url] = path

    log.info(f"Stage 2 done: {len(clipped)} clipped, {len(failed)} failed")
    return clipped


def stage_insert(clipped: dict[str, str]) -> int:
    log.info(f"Stage 3: Inserting {len(clipped)} layers to DB")
    inserted = 0
    warnings = 0
    errors = 0

    for url, clipped_path in clipped.items():
        conn = None
        try:
            layer = from_url(url)
            layer.local_path = clipped_path

            issues = layer.validate()
            if issues:
                log.warning(f"Validation: {layer.filename} — {issues}")
                warnings += 1

            conn = get_connection(DB_PATH)   # ← open fresh per insert
            insert_layer(conn, layer)
            conn.commit()
            inserted += 1

        except sqlite3.OperationalError as e:
            log.error(f"Insert failed: {os.path.basename(clipped_path)} — {e}")
            if conn:
                conn.rollback()
            errors += 1

        except Exception as e:
            log.error(f"Insert failed: {os.path.basename(clipped_path)} — {e}")
            errors += 1

        finally:
            if conn:
                close_connection(conn)       # ← close immediately, no lingering lock

    log.info(f"Stage 3 done: {inserted} inserted, {warnings} warnings, {errors} errors")
    return inserted


def load_urls(path: str) -> list[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def main():
    t0 = time.time()

    urls = load_urls(TIFF_URLS)
    log.info(f"Loaded {len(urls)} URLs from {TIFF_URLS}")

    # Stage 1 → 2 → 3
    downloaded = stage_download(urls)
    clipped = stage_clip(downloaded)
    inserted = stage_insert(clipped)

    elapsed = time.time() - t0
    log.info(
        f"Pipeline complete: {inserted}/{len(urls)} layers in {elapsed:.0f}s "
        f"({elapsed/max(len(urls),1):.1f}s per file)"
    )


if __name__ == "__main__":
    main()