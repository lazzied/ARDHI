"""
Audit helpers for checking GAEZ preprocessing outputs.

Post-run audit.

Compares the original URL list against:
  1. What's on disk in raw/ and clipped/
  2. What's in the database

Reports:
  - URLs that failed to download (not in raw/)
  - URLs that downloaded but failed to clip (in raw/, not in clipped/)
  - URLs that clipped but failed to insert (in clipped/, not in DB)
  - Validation warnings (in DB with unresolved metadata)
"""

import os
import sqlite3
import sys


TIFF_URLS      = "gaez_data/links/filtered_tiff_files.txt"
RAW_FOLDER     = "D:/ARDHI/TIFF/raw"
CLIPPED_FOLDER = "D:/ARDHI/TIFF/clipped"
DB_PATH        = "ardhi.db"


def load_urls(path: str) -> list[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def url_to_filename(url: str) -> str:
    return url.rsplit("/", 1)[-1]


def audit():
    # 1. Load all expected URLs
    urls = load_urls(TIFF_URLS)
    expected = {url_to_filename(u): u for u in urls}
    print(f"Expected: {len(expected)} files from {TIFF_URLS}\n")

    # 2. Check raw folder
    raw_files = set(os.listdir(RAW_FOLDER)) if os.path.isdir(RAW_FOLDER) else set()
    raw_tifs = {f for f in raw_files if f.endswith(".tif")}

    # 3. Check clipped folder
    clipped_files = set(os.listdir(CLIPPED_FOLDER)) if os.path.isdir(CLIPPED_FOLDER) else set()
    clipped_tifs = {f for f in clipped_files if f.endswith(".tif")}

    # 4. Check database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT file_path FROM tiff_files")
    db_paths = {os.path.basename(row[0]) for row in cursor.fetchall()}
    conn.close()

    # ── Report ────────────────────────────────────────────────────────

    # Failed downloads: expected but not in raw/
    failed_download = []
    for filename, url in expected.items():
        if filename not in raw_tifs and filename not in clipped_tifs:
            # Not in raw AND not in clipped (might have been deleted after clip)
            # Check if it made it to DB
            if filename not in db_paths:
                failed_download.append((filename, url))

    print(f"{'='*60}")
    print(f"  Failed downloads: {len(failed_download)}")
    print(f"{'='*60}")
    for filename, url in failed_download:
        print(f"  {filename}")
        print(f"    {url}")
    print()

    # Failed clips: in raw/ but not in clipped/ and not in DB
    failed_clip = []
    for filename in raw_tifs:
        if filename not in clipped_tifs and filename not in db_paths:
            url = expected.get(filename, "?")
            failed_clip.append((filename, url))

    print(f"{'='*60}")
    print(f"  Failed clips: {len(failed_clip)}")
    print(f"{'='*60}")
    for filename, url in failed_clip:
        print(f"  {filename}")
    print()

    # Failed inserts: in clipped/ but not in DB
    failed_insert = []
    for filename in clipped_tifs:
        if filename not in db_paths:
            url = expected.get(filename, "?")
            failed_insert.append((filename, url))

    print(f"{'='*60}")
    print(f"  Failed inserts: {len(failed_insert)}")
    print(f"{'='*60}")
    for filename, url in failed_insert:
        print(f"  {filename}")
    print()

    # Summary
    print(f"{'='*60}")
    print(f"  Summary")
    print(f"{'='*60}")
    print(f"  Expected:          {len(expected):>6}")
    print(f"  In raw/:           {len(raw_tifs):>6}")
    print(f"  In clipped/:       {len(clipped_tifs):>6}")
    print(f"  In database:       {len(db_paths):>6}")
    print(f"  Failed downloads:  {len(failed_download):>6}")
    print(f"  Failed clips:      {len(failed_clip):>6}")
    print(f"  Failed inserts:    {len(failed_insert):>6}")
    print()

    # Return failed URLs for retry
    retry_urls = [url for _, url in failed_download + failed_clip + failed_insert if url != "?"]
    if retry_urls:
        retry_path = "failed_urls.txt"
        with open(retry_path, "w") as f:
            for url in retry_urls:
                f.write(url + "\n")
        print(f"  Wrote {len(retry_urls)} URLs to {retry_path} for retry")
        print(f"  Re-run pipeline with: TIFF_URLS = '{retry_path}'")


if __name__ == "__main__":
    audit()
