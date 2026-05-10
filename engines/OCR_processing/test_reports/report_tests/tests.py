import json
import copy
import re
import os
import sys
import difflib
from pathlib import Path
from typing import Union

# Database and Engine Imports
from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.connections import get_ardhi_connection, get_hwsd_connection
from ardhi.db.hwsd import HwsdRepository
from engines.OCR_processing.models import InputLevel, WaterSupply
from engines.OCR_processing.yield_service.yield_rank import ReportCropYield
from engines.global_engines.yield_service.debug_print_yield import format_ranking_summary

# =================================================================
# 1. COORDINATE MAPPING (Tunisian Regions)
# =================================================================
REGION_COORDS = {
    "fertile_tell_loam_n.json":           (36.68, 9.05),   # Béja farmland west of city
    "medjerda_valley_alluvial.json":      (36.57, 9.72),   # Medjerda floodplain fields
    "alkaline_sahel_olive_grove.json":    (35.74, 10.55),  # Olive groves SW of Sousse
    "alkaline_enfidha_plain.json":        (36.08, 10.25),  # Enfidha agricultural plain
    "calcareous_zaghouan_hillslope.json": (36.32, 10.02),  # Zaghouan hillside terraces
    "degraded_eroded_cap_bon.json":       (36.78, 10.85),  # Cap Bon vineyard/farmland
    "degraded_overirrigated_beja.json":   (36.65, 9.38),   # Irrigated fields NW Béja
    "organic_rich_kroumirie_forest.json": (36.72, 8.55),   # Kroumirie forest edge farmland
    "organic_rich_mogods_hillside.json":  (37.05, 9.12),   # Mogods hillside terraces
    "saline_irrigated_sfax_plain.json":   (34.68, 10.62),  # Sfax olive/farm perimeter
}

json_reports_paths = list(REGION_COORDS.keys())

# =================================================================
# 2. PATHS AND DIRECTORIES
# =================================================================
base_file_path = "engines/OCR_processing/test_reports/report_generator/generated_lab_reports"
results_dir = Path("engines/OCR_processing/test_reports/report_tests/results")
results_dir.mkdir(parents=True, exist_ok=True)

# =================================================================
# 3. DATABASE SETUP
# =================================================================
conn_hwsd = get_hwsd_connection()
conn_ardhi = get_ardhi_connection()

hwsd_repo = HwsdRepository(conn_hwsd)
ardhi_repo = ArdhiRepository(conn_ardhi)


# =================================================================
# 5. EXECUTION LOOP
# =================================================================
output_path = results_dir / "all_regions_yield_ranking.txt"

with open(output_path, "w", encoding="utf-8") as f:
    for filename in json_reports_paths:
        report_path = os.path.join(base_file_path, filename)

        if not os.path.exists(report_path):
            print(f"Skipping: {filename} (File not found)")
            continue

        current_coord = REGION_COORDS.get(filename)
        paths = {
            "report_input": report_path,
            "report_out": "engines/soil_properties_builder/output/results/report_results",
            "hwsd_out": "engines/soil_properties_builder/output/results/hwsd_results"
        }

        print(f"Processing: {filename} at {current_coord}...")

        crop_yield = ReportCropYield(
            hwsd_repo,
            ardhi_repo,
            InputLevel.LOW,
            WaterSupply.RAINFED,
            None,
            current_coord,
            paths
        )

        f.write(f"\n{'='*73}\n")
        f.write(f"REGION: {filename}\n")
        f.write(f"COORDINATE: {current_coord}\n")
        f.write(f"{'='*73}\n")

        try:
            ranking_results = crop_yield.build_ranking_class()
            f.write(format_ranking_summary(ranking_results,10))
            f.write("\n")
        except Exception as e:
            f.write(f"ERROR: {str(e)}\n")

print(f"\n[Done] Single ranking file generated at: {output_path}")