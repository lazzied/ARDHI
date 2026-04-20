"""
Pipeline benchmark.

Runs the full pipeline on a sample of N files and measures
per-stage timing. Extrapolates to the full dataset size.

Usage:
    python benchmark.py --sample 50 --urls gaez_scripts/test_tiff_urls.txt
"""

import argparse
import os
import time
import random
import statistics

from gaez_scripts.TIFFpipeline import Downloader, RasterProcessor
from gaez_scripts.tiff_layer import from_url
from gaez_scripts.batch_TIFF_parallel_pipeline import (
    download_one, clip_one,
    SHAPEFILE, RAW_FOLDER, CLIPPED_FOLDER,
    DOWNLOAD_WORKERS, CLIP_WORKERS,
)
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed


def load_urls(path: str) -> list[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def benchmark_sequential(urls: list[str]) -> dict:
    """Time each stage per-file sequentially. Gets per-file baselines."""
    download_times = []
    clip_times = []
    metadata_times = []
    file_sizes = []

    processor = RasterProcessor()

    for url in urls:
        # Download
        t0 = time.perf_counter()
        _, path, error = download_one(url)
        t1 = time.perf_counter()
        if error or path is None:
            print(f"  Skip (download failed): {url}")
            continue
        download_times.append(t1 - t0)
        file_sizes.append(os.path.getsize(path) / (1024 * 1024))  # MB

        # Clip
        t2 = time.perf_counter()
        _, clipped_path, error = clip_one((url, path, SHAPEFILE, CLIPPED_FOLDER))
        t3 = time.perf_counter()
        if error:
            print(f"  Skip (clip failed): {url}")
            continue
        clip_times.append(t3 - t2)

        # Metadata
        t4 = time.perf_counter()
        layer = from_url(url)
        layer.local_path = clipped_path
        layer.validate()
        t5 = time.perf_counter()
        metadata_times.append(t5 - t4)

    return {
        "download": download_times,
        "clip": clip_times,
        "metadata": metadata_times,
        "file_sizes_mb": file_sizes,
    }


def benchmark_parallel(urls: list[str]) -> dict:
    """Time each stage with actual concurrency. Gets real throughput."""

    # Stage 1: threaded download
    t0 = time.perf_counter()
    downloaded = {}
    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        futures = {pool.submit(download_one, url): url for url in urls}
        for future in as_completed(futures):
            url, path, error = future.result()
            if path:
                downloaded[url] = path
    t1 = time.perf_counter()

    # Stage 2: multiprocess clip
    t2 = time.perf_counter()
    clipped = {}
    tasks = [(url, path, SHAPEFILE, CLIPPED_FOLDER) for url, path in downloaded.items()]
    with ProcessPoolExecutor(max_workers=CLIP_WORKERS) as pool:
        futures = {pool.submit(clip_one, task): task[0] for task in tasks}
        for future in as_completed(futures):
            url, path, error = future.result()
            if path:
                clipped[url] = path
    t3 = time.perf_counter()

    # Stage 3: metadata (single thread)
    t4 = time.perf_counter()
    for url, path in clipped.items():
        layer = from_url(url)
        layer.local_path = path
        layer.validate()
    t5 = time.perf_counter()

    return {
        "download_total": t1 - t0,
        "clip_total": t3 - t2,
        "metadata_total": t5 - t4,
        "files_downloaded": len(downloaded),
        "files_clipped": len(clipped),
    }


def print_report(seq: dict, par: dict, total_files: int, sample_size: int):
    n = len(seq["download"])
    if n == 0:
        print("No files completed. Check URLs and network.")
        return

    print()
    print("=" * 65)
    print(f"  PIPELINE BENCHMARK — {n} files sampled from {total_files}")
    print("=" * 65)

    # File sizes
    sizes = seq["file_sizes_mb"]
    print(f"\n  File sizes:")
    print(f"    Mean:   {statistics.mean(sizes):>8.1f} MB")
    print(f"    Median: {statistics.median(sizes):>8.1f} MB")
    print(f"    Min:    {min(sizes):>8.1f} MB")
    print(f"    Max:    {max(sizes):>8.1f} MB")
    print(f"    Total:  {sum(sizes):>8.1f} MB for {n} files")

    # Sequential per-file timing
    print(f"\n  Sequential per-file timing (n={n}):")
    for stage in ["download", "clip", "metadata"]:
        times = seq[stage]
        if times:
            avg = statistics.mean(times)
            med = statistics.median(times)
            sd = statistics.stdev(times) if len(times) > 1 else 0
            print(f"    {stage:12s}  mean={avg:.2f}s  median={med:.2f}s  stdev={sd:.2f}s")

    seq_per_file = (
        statistics.mean(seq["download"])
        + statistics.mean(seq["clip"])
        + statistics.mean(seq["metadata"])
    )

    # Parallel batch timing
    par_n = par["files_clipped"]
    par_total = par["download_total"] + par["clip_total"] + par["metadata_total"]
    par_per_file = par_total / max(par_n, 1)

    print(f"\n  Parallel batch timing ({par_n} files):")
    print(f"    Download:  {par['download_total']:>6.1f}s  ({par['files_downloaded']} files)")
    print(f"    Clip:      {par['clip_total']:>6.1f}s  ({par['files_clipped']} files)")
    print(f"    Metadata:  {par['metadata_total']:>6.1f}s")
    print(f"    Total:     {par_total:>6.1f}s")
    print(f"    Per file:  {par_per_file:>6.2f}s")

    # Speedup
    speedup = seq_per_file / par_per_file if par_per_file > 0 else 0
    print(f"\n  Speedup: {speedup:.1f}x  (sequential {seq_per_file:.2f}s → parallel {par_per_file:.2f}s per file)")

    # Extrapolation
    print(f"\n  Extrapolation to {total_files} files:")
    seq_total_est = seq_per_file * total_files
    par_total_est = par_per_file * total_files
    print(f"    Sequential: {seq_total_est/3600:.1f} hours  ({seq_total_est/60:.0f} min)")
    print(f"    Parallel:   {par_total_est/3600:.1f} hours  ({par_total_est/60:.0f} min)")
    print(f"    Time saved: {(seq_total_est - par_total_est)/3600:.1f} hours")

    print()
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Benchmark the pipeline")
    parser.add_argument("--sample", type=int, default=50, help="Number of files to test")
    parser.add_argument("--urls", default="gaez_scripts/test_tiff_urls.txt")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    args = parser.parse_args()

    all_urls = load_urls(args.urls)
    total_files = len(all_urls)

    random.seed(args.seed)
    sample = random.sample(all_urls, min(args.sample, total_files))

    print(f"Benchmarking on {len(sample)} files (from {total_files} total)...")

    # Split sample: first half for sequential, second half for parallel
    # so we don't measure cached files
    half = len(sample) // 2
    seq_sample = sample[:half]
    par_sample = sample[half:]

    print(f"\n--- Sequential benchmark ({len(seq_sample)} files) ---")
    seq = benchmark_sequential(seq_sample)

    print(f"\n--- Parallel benchmark ({len(par_sample)} files) ---")
    par = benchmark_parallel(par_sample)

    print_report(seq, par, total_files, len(sample))


if __name__ == "__main__":
    main()