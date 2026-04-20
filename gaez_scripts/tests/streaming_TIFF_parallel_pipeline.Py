"""
Streaming GAEZ ingestion pipeline.

All three stages run concurrently. A file flows through the pipeline
as soon as it completes the previous stage — no waiting for all
downloads to finish before clipping starts.

Architecture:
    [URLs] → [download queue] → threads → [clip queue] → processes → [DB queue] → writer
                                   ↓                        ↓                        ↓
                              raw tiff                 clipped tiff              DB row

Flow control:
    - Bounded queues apply backpressure — if clipping is slow,
      downloading pauses until the clip queue drains.
    - Disk usage stays bounded to (download_queue_size × avg_file_size).
    - Optional: delete raw file after clipping to halve peak disk usage.
"""

import os
import time
import queue
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

from gaez_scripts.tiff_layer import from_url, TiffLayer
from ardhi_db import get_connection, close_connection, insert_layer
from gaez_scripts.TIFFpipeline import Downloader, RasterProcessor


# ──────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────

SHAPEFILE      = "gaez_data/tunisia_Tunisia_Country_Boundary/tunisia_Tunisia_Country_Boundary.shp"
RAW_FOLDER     = "D:/ARDHI/TIFF/raw"
CLIPPED_FOLDER = "D:/ARDHI/TIFF/clipped"
TIFF_URLS      = "gaez_scripts/test_tiff_urls.txt"
DB_PATH        = "ardhi.db"

DOWNLOAD_WORKERS  = 12
CLIP_WORKERS      = None          # defaults to os.cpu_count()

# Bounded queues control backpressure and peak disk usage.
# If clips can't keep up, downloads slow down.
CLIP_QUEUE_SIZE   = 20            # how many downloaded files can wait to be clipped
INSERT_QUEUE_SIZE = 100           # how many clipped files can wait to be inserted

MAX_RETRIES       = 3
RETRY_DELAY       = 5
DELETE_RAW_AFTER_CLIP = True      # halves peak disk usage

# Sentinel marking end-of-stream
DONE = object()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s [%(threadName)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Stage workers — each runs in its own thread
# ──────────────────────────────────────────────────────────────────────

def download_worker(url: str, clip_queue: queue.Queue, stats: dict) -> None:
    """Download one file and push to clip queue."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            path = Downloader.download_url(url, RAW_FOLDER)
            if not os.path.exists(path):
                raise FileNotFoundError(f"Missing after download: {path}")
            clip_queue.put((url, path))
            stats["downloaded"] += 1
            return
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                log.error(f"Download failed after {MAX_RETRIES} attempts: {Downloader.get_filename(url)} — {e}")
                stats["download_failed"] += 1


def clip_task(args: tuple[str, str]) -> tuple[str, str | None, str | None]:
    """Runs in a process pool worker. Clips one tiff."""
    url, raw_path = args
    try:
        os.makedirs(CLIPPED_FOLDER, exist_ok=True)
        filename = os.path.basename(raw_path)
        clipped_path = os.path.join(CLIPPED_FOLDER, filename)

        processor = RasterProcessor()
        raster_data = processor.process(raw_path, SHAPEFILE)
        processor.save(raster_data, clipped_path)

        return (url, clipped_path, None)
    except Exception as e:
        return (url, None, str(e))


def clip_dispatcher(
    clip_queue: queue.Queue,
    insert_queue: queue.Queue,
    clip_pool: ProcessPoolExecutor,
    stats: dict,
) -> None:
    """
    Pulls (url, raw_path) from clip_queue, submits to process pool,
    pushes (url, clipped_path) to insert_queue as each completes.
    Runs in a single thread that coordinates the process pool.
    """
    pending = {}   # future -> (url, raw_path)

    while True:
        # Accept new work (non-blocking if we have capacity)
        try:
            item = clip_queue.get(timeout=0.1)
            if item is DONE:
                # No more downloads coming. Wait for pending clips to finish.
                break
            url, raw_path = item
            fut = clip_pool.submit(clip_task, (url, raw_path))
            pending[fut] = (url, raw_path)
        except queue.Empty:
            pass

        # Drain any completed clips without blocking
        done_futures = [f for f in pending if f.done()]
        for fut in done_futures:
            url, raw_path = pending.pop(fut)
            _, clipped_path, error = fut.result()
            if error:
                log.error(f"Clip failed: {os.path.basename(raw_path)} — {error}")
                stats["clip_failed"] += 1
            else:
                if DELETE_RAW_AFTER_CLIP:
                    try:
                        os.remove(raw_path)
                    except OSError:
                        pass
                insert_queue.put((url, clipped_path))
                stats["clipped"] += 1

    # Drain remaining pending clips
    for fut in pending:
        url, raw_path = pending[fut]
        try:
            _, clipped_path, error = fut.result()
            if error:
                log.error(f"Clip failed: {os.path.basename(raw_path)} — {error}")
                stats["clip_failed"] += 1
            else:
                if DELETE_RAW_AFTER_CLIP:
                    try:
                        os.remove(raw_path)
                    except OSError:
                        pass
                insert_queue.put((url, clipped_path))
                stats["clipped"] += 1
        except Exception as e:
            log.error(f"Clip future failed: {e}")
            stats["clip_failed"] += 1

    insert_queue.put(DONE)


def insert_worker(insert_queue: queue.Queue, stats: dict) -> None:
    """Consume clipped files and insert into DB. Single thread — SQLite."""
    conn = get_connection(DB_PATH)
    batch_size = 50
    batch = []

    def flush():
        if not batch:
            return
        try:
            for layer in batch:
                insert_layer(conn, layer)
            conn.commit()
            stats["inserted"] += len(batch)
        except Exception as e:
            log.error(f"Batch insert failed: {e}")
            stats["insert_failed"] += len(batch)
        batch.clear()

    try:
        while True:
            item = insert_queue.get()
            if item is DONE:
                break
            url, clipped_path = item
            try:
                layer = from_url(url)
                layer.local_path = clipped_path
                issues = layer.validate()
                if issues:
                    log.warning(f"Validation: {layer.filename} — {issues}")
                    stats["warnings"] += 1
                batch.append(layer)
                if len(batch) >= batch_size:
                    flush()
            except Exception as e:
                log.error(f"Enrich failed: {os.path.basename(clipped_path)} — {e}")
                stats["insert_failed"] += 1

        flush()
    finally:
        close_connection(conn)


# ──────────────────────────────────────────────────────────────────────
# Pipeline orchestrator
# ──────────────────────────────────────────────────────────────────────

def load_urls(path: str) -> list[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def run_streaming_pipeline(urls: list[str]) -> dict:
    """Run all three stages concurrently with bounded backpressure."""
    stats = {
        "total": len(urls),
        "downloaded": 0,
        "clipped": 0,
        "inserted": 0,
        "warnings": 0,
        "download_failed": 0,
        "clip_failed": 0,
        "insert_failed": 0,
    }

    clip_queue   = queue.Queue(maxsize=CLIP_QUEUE_SIZE)
    insert_queue = queue.Queue(maxsize=INSERT_QUEUE_SIZE)

    log.info(
        f"Starting streaming pipeline: {len(urls)} URLs, "
        f"{DOWNLOAD_WORKERS} download threads, "
        f"{CLIP_WORKERS or os.cpu_count()} clip processes"
    )

    # Start the DB writer thread
    writer_thread = threading.Thread(
        target=insert_worker,
        args=(insert_queue, stats),
        name="db-writer",
    )
    writer_thread.start()

    # Process pool for CPU-bound clips
    with ProcessPoolExecutor(max_workers=CLIP_WORKERS) as clip_pool:

        # Thread that coordinates the process pool
        clip_thread = threading.Thread(
            target=clip_dispatcher,
            args=(clip_queue, insert_queue, clip_pool, stats),
            name="clip-dispatcher",
        )
        clip_thread.start()

        # Download pool — many threads, each pushes to clip_queue
        with ThreadPoolExecutor(
            max_workers=DOWNLOAD_WORKERS,
            thread_name_prefix="downloader",
        ) as download_pool:
            futures = [
                download_pool.submit(download_worker, url, clip_queue, stats)
                for url in urls
            ]
            # Wait for all downloads to finish or fail
            for f in futures:
                f.result()

        # Signal end-of-stream to clip stage
        clip_queue.put(DONE)
        clip_thread.join()

    # Clip dispatcher already sent DONE to insert_queue
    writer_thread.join()

    return stats


def print_stats(stats: dict, elapsed: float):
    log.info("=" * 55)
    log.info(f"  Pipeline complete in {elapsed:.0f}s")
    log.info(f"  Total URLs:     {stats['total']:>5}")
    log.info(f"  Downloaded:     {stats['downloaded']:>5}  ({stats['download_failed']} failed)")
    log.info(f"  Clipped:        {stats['clipped']:>5}  ({stats['clip_failed']} failed)")
    log.info(f"  Inserted:       {stats['inserted']:>5}  ({stats['insert_failed']} failed)")
    log.info(f"  Warnings:       {stats['warnings']:>5}")
    log.info(f"  Throughput:     {stats['inserted'] / max(elapsed, 1):.2f} files/sec")
    log.info("=" * 55)


def main():
    t0 = time.time()
    urls = load_urls(TIFF_URLS)
    log.info(f"Loaded {len(urls)} URLs from {TIFF_URLS}")

    stats = run_streaming_pipeline(urls)

    elapsed = time.time() - t0
    print_stats(stats, elapsed)


if __name__ == "__main__":
    main()