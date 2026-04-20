"""
Yield estimation engine for Tunisia.

Given a GPS coordinate, reads pre-computed GAEZ v5 attainable yield rasters
from the local clipped tiff collection and returns ranked crop yield estimates.

Uses two yield layers:
  - RES05-YLX30AS: output density in kg(DW)/ha (~1km) → primary yield metric
  - RES05-YXX:     average yield of best suitability class (~10km) → regional ceiling

For each input level (HRLM, HILM, LRLM, LILM), a separate yield exists.
The engine queries both layers and presents the farmer with a ranked yield list.
"""


import os
import sqlite3
import rasterio
from rasterio.windows import Window
from dataclasses import dataclass, field
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed


# ──────────────────────────────────────────────────────────────────────
# Input level labels
# ──────────────────────────────────────────────────────────────────────

INPUT_LEVEL_LABELS = {
    "HRLM": "Rain-fed, high input",
    "HILM": "Irrigated, high input",
    "LRLM": "Rain-fed, low input",
    "LILM": "Irrigated, low input",
}

# Units note shown alongside yield values
YIELD_UNIT_NOTE = "kg(DW)/ha — dry weight. Sugar beet/cane: kg sugar/ha, oil palm: kg oil/ha, cotton: kg lint/ha."


# ──────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────

@dataclass
class CropYield:
    """Yield result for one crop at one location under one input level."""
    crop_code: str
    crop_name: str
    input_level: str
    ylx_yield: Optional[float] = None    # kg(DW)/ha, 1km, primary metric
    yxx_yield: Optional[float] = None    # kg(DW)/ha, 10km, regional ceiling

    @property
    def has_yield(self) -> bool:
        """True if primary yield data exists and is positive."""
        return self.ylx_yield is not None and self.ylx_yield > 0

    @property
    def yield_gap(self) -> Optional[float]:
        """
        Difference between regional ceiling and local yield.
        Positive means there is untapped potential in the area.
        None if either layer is missing.
        """
        if self.ylx_yield is not None and self.yxx_yield is not None:
            return self.yxx_yield - self.ylx_yield
        return None

    @property
    def yield_gap_pct(self) -> Optional[float]:
        """Yield gap as a percentage of the regional ceiling."""
        if self.yield_gap is not None and self.yxx_yield and self.yxx_yield > 0:
            return (self.yield_gap / self.yxx_yield) * 100.0
        return None


@dataclass
class YieldResult:
    """Complete yield result for a location under one input level."""
    lat: float
    lon: float
    input_level: str
    input_level_label: str
    yields: list[CropYield] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ranked(self) -> list[CropYield]:
        """All crops with yield data sorted by primary yield descending."""
        with_yield = [y for y in self.yields if y.has_yield]
        return sorted(with_yield, key=lambda y: y.ylx_yield, reverse=True)

    def top_n(self, n: int = 10) -> list[CropYield]:
        """
        Return top N crops by yield.
        If n exceeds available crops, returns all.
        """
        ranked = self.ranked
        return ranked[:min(n, len(ranked))]

    @property
    def no_yield(self) -> list[CropYield]:
        """Crops with no yield data at this location."""
        return [y for y in self.yields if not y.has_yield]


# ──────────────────────────────────────────────────────────────────────
# Raster reader
# ──────────────────────────────────────────────────────────────────────

class TiffReader:
    """Read pixel values from clipped GAEZ tiffs by coordinate."""

    def __init__(self, tiff_folder: str):
        self.tiff_folder = tiff_folder

    def read_pixel(self, tiff_path: str, lat: float, lon: float) -> Optional[float]:
        """Read a single pixel value at (lat, lon). Returns None if nodata."""
        full_path = os.path.join(self.tiff_folder, tiff_path)
        if not os.path.exists(full_path):
            return None

        try:
            with rasterio.open(full_path) as src:
                row, col = src.index(lon, lat)

                if row < 0 or col < 0 or row >= src.height or col >= src.width:
                    return None

                window = Window(col, row, 1, 1)
                val = src.read(1, window=window)[0, 0]

                if src.nodata is not None and val == src.nodata:
                    return None
                if val == -9 or val == -9999:
                    return None

                return float(val)
        except Exception:
            return None


# ──────────────────────────────────────────────────────────────────────
# Yield engine
# ──────────────────────────────────────────────────────────────────────

class CropYieldEngine:
    """
    Reads GAEZ attainable yield rasters and ranks crops by yield for a given location.

    Usage:
        engine = CropYieldEngine(
            db_path="ardhi.db",
            tiff_folder="D:/ARDHI/TIFF/clipped",
        )
        result = engine.estimate(lat=36.8, lon=10.18, input_level="HRLM")
        for crop in result.top_n(10):
            print(f"{crop.crop_name}: {crop.ylx_yield:.0f} kg/ha (ceiling: {crop.yxx_yield:.0f})")
    """

    YIELD_LAYERS = {
        "YLX": "RES05-YLX30AS",   # primary yield, 1km
        "YXX": "RES05-YXX",       # regional ceiling, 10km
    }

    MAX_WORKERS = 8

    def __init__(self, db_path: str, tiff_folder: str, crop_registry: dict = None):
        self.db_path = db_path
        self.reader = TiffReader(tiff_folder)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        if crop_registry:
            self._crop_names = self._build_crop_names(crop_registry)
        else:
            self._crop_names = {}

    def _build_crop_names(self, registry: dict) -> dict:
        """Build {RES05_code: caption} from CROP_REGISTRY."""
        names = {}
        for crop_key, crop in registry.items():
            codes = crop.get("codes", {})
            res05_code = codes.get("RES05")
            if res05_code:
                names[res05_code] = crop.get("caption", crop_key)
            for st_key, st in crop.get("subtypes", {}).items():
                st_code = st.get("codes", {}).get("RES05")
                if st_code:
                    names[st_code] = st.get("description", f"{crop.get('caption', crop_key)} ({st_key})")
        return names

    def _get_tiff_paths(self, map_code: str, input_level: str) -> dict[str, str]:
        rows = self.conn.execute(
            "SELECT crop_code, file_path FROM tiff_files "
            "WHERE map_code = ? AND input_level = ? AND crop_code IS NOT NULL",
            (map_code, input_level)
        ).fetchall()
        return {row["crop_code"]: row["file_path"] for row in rows}

    def _get_tiff_paths_no_input(self, map_code: str) -> dict[str, str]:
        """For YXX which does not have an input_level dimension."""
        rows = self.conn.execute(
            "SELECT crop_code, file_path FROM tiff_files "
            "WHERE map_code = ? AND crop_code IS NOT NULL",
            (map_code,)
        ).fetchall()
        return {row["crop_code"]: row["file_path"] for row in rows}

    def get_available_crops(self, input_level: str = "HRLM") -> list[str]:
        """List all crop codes that have yield data."""
        rows = self.conn.execute(
            "SELECT DISTINCT crop_code FROM tiff_files "
            "WHERE map_code = ? AND input_level = ? AND crop_code IS NOT NULL",
            (self.YIELD_LAYERS["YLX"], input_level)
        ).fetchall()
        return [row["crop_code"] for row in rows]

    def _yield_one_crop(
        self,
        crop_code: str,
        lat: float,
        lon: float,
        input_level: str,
        ylx_paths: dict,
        yxx_paths: dict,
    ) -> CropYield:
        """
        Read both yield layers for a single crop and return a CropYield.
        Early exit: if YLX is nodata, skip YXX read entirely.
        """
        crop_name = self._crop_names.get(crop_code, crop_code)

        # Primary yield first — main filter
        ylx_val = self.reader.read_pixel(ylx_paths.get(crop_code, ""), lat, lon)

        if ylx_val is None:
            return CropYield(
                crop_code=crop_code,
                crop_name=crop_name,
                input_level=input_level,
            )

        # Only read regional ceiling if primary yield exists
        yxx_val = self.reader.read_pixel(yxx_paths.get(crop_code, ""), lat, lon)

        return CropYield(
            crop_code=crop_code,
            crop_name=crop_name,
            input_level=input_level,
            ylx_yield=ylx_val,
            yxx_yield=yxx_val,
        )

    def _run_for_input_level(
        self,
        lat: float,
        lon: float,
        input_level: str,
        yxx_paths: dict,
    ) -> YieldResult:
        """
        Internal helper: run yield scoring for one input level
        given pre-fetched YXX paths.
        """
        result = YieldResult(
            lat=lat,
            lon=lon,
            input_level=input_level,
            input_level_label=INPUT_LEVEL_LABELS.get(input_level, input_level),
        )

        ylx_paths = self._get_tiff_paths(self.YIELD_LAYERS["YLX"], input_level)

        if not ylx_paths:
            result.errors.append(
                f"No yield data found for input level {input_level}. "
                f"Check that RES05-YLX30AS tiffs are in the database."
            )
            return result

        all_crops = sorted(ylx_paths.keys())

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            futures = {
                executor.submit(
                    self._yield_one_crop,
                    crop_code, lat, lon, input_level,
                    ylx_paths, yxx_paths,
                ): crop_code
                for crop_code in all_crops
            }

            for future in as_completed(futures):
                try:
                    crop_yield = future.result()
                    result.yields.append(crop_yield)
                except Exception as e:
                    crop_code = futures[future]
                    result.errors.append(f"Failed to estimate yield for {crop_code}: {e}")

        return result

    def estimate(
        self,
        lat: float,
        lon: float,
        input_level: str = "HRLM",
    ) -> YieldResult:
        """
        Estimate crop yields for a location under one input level.

        Args:
            lat: Latitude (e.g. 36.8 for northern Tunisia)
            lon: Longitude (e.g. 10.18 for Tunis area)
            input_level: HRLM (rain-fed high), HILM (irrigated high),
                        LRLM (rain-fed low), LILM (irrigated low)

        Returns:
            YieldResult with ranked CropYield objects.
            Use result.top_n(n) to get top N crops,
            or result.ranked for the full sorted list.
        """
        yxx_paths = self._get_tiff_paths_no_input(self.YIELD_LAYERS["YXX"])
        return self._run_for_input_level(lat, lon, input_level, yxx_paths)

    def estimate_all_inputs(
        self,
        lat: float,
        lon: float,
    ) -> dict[str, YieldResult]:
        """
        Run yield estimates for all four input levels.
        YXX paths fetched once and shared across all input levels.
        Returns {"HRLM": YieldResult, "HILM": ..., "LRLM": ..., "LILM": ...}
        """
        yxx_paths = self._get_tiff_paths_no_input(self.YIELD_LAYERS["YXX"])
        return {
            il: self._run_for_input_level(lat, lon, il, yxx_paths)
            for il in ["HRLM", "HILM", "LRLM", "LILM"]
        }

    def estimate_all_inputs_full(
        self,
        lat: float,
        lon: float,
    ) -> dict:
        """
        Run yield estimates for all four input levels and return the complete
        picture — every crop, every input level, fully scored and ranked.

        No top_n filtering applied. Returns everything so the caller
        can slice, compare, or display however they want.

        Returns:
            {
                "HRLM": [CropYield, ...],
                "HILM": [CropYield, ...],
                "LRLM": [CropYield, ...],
                "LILM": [CropYield, ...],
                "errors": {"HRLM": [...], ...}
            }
        """
        yxx_paths = self._get_tiff_paths_no_input(self.YIELD_LAYERS["YXX"])

        full = {}
        errors = {}

        for il in ["HRLM", "HILM", "LRLM", "LILM"]:
            rec = self._run_for_input_level(lat, lon, il, yxx_paths)
            full[il] = rec.ranked
            errors[il] = rec.errors

        full["errors"] = errors
        return full

    def close(self):
        self.conn.close()


# ──────────────────────────────────────────────────────────────────────
# Display helpers
# ──────────────────────────────────────────────────────────────────────

def print_yield(result: YieldResult, top_n: int = 10):
    """
    Pretty-print a yield result.
    If top_n exceeds available crops, prints all.
    """
    print(f"\n{'='*75}")
    print(f"  Yield estimates at ({result.lat:.4f}, {result.lon:.4f})")
    print(f"  Input level: {result.input_level_label}")
    print(f"  Unit: {YIELD_UNIT_NOTE}")
    print(f"{'='*75}")

    ranked = result.ranked
    if not ranked:
        print("  No yield data found at this location.")
        if result.errors:
            for e in result.errors:
                print(f"  Error: {e}")
        return

    to_display = ranked[:min(top_n, len(ranked))]

    print(f"\n  {'Rank':<5} {'Crop':<25} {'Yield (kg/ha)':>14} {'Ceiling (kg/ha)':>16} {'Gap':>8}")
    print(f"  {'-'*5} {'-'*25} {'-'*14} {'-'*16} {'-'*8}")

    for i, cy in enumerate(to_display, 1):
        ceiling = f"{cy.yxx_yield:>14,.0f}" if cy.yxx_yield is not None else f"{'N/A':>14}"
        gap = f"{cy.yield_gap_pct:.1f}%" if cy.yield_gap_pct is not None else "N/A"
        print(
            f"  {i:<5} {cy.crop_name:<25} "
            f"{cy.ylx_yield:>14,.0f} "
            f"{ceiling:>16} "
            f"{gap:>8}"
        )

    total = len(ranked)
    print(f"\n  {total} crops with yield data, {len(result.no_yield)} with no data")
    print(f"  Showing {len(to_display)} of {total}")


def print_yield_comparison(results: dict[str, YieldResult]):
    """Compare best yielding crop across all input levels."""
    print(f"\n{'='*75}")
    print(f"  Input level yield comparison")
    print(f"{'='*75}\n")

    for il, result in results.items():
        ranked = result.ranked
        label = result.input_level_label
        if ranked:
            top = ranked[0]
            ceiling = f" / ceiling {top.yxx_yield:,.0f}" if top.yxx_yield else ""
            print(f"  {label:<25} Best: {top.crop_name} ({top.ylx_yield:,.0f} kg/ha{ceiling}) — {len(ranked)} crops")
        else:
            print(f"  {label:<25} No yield data")


def print_full_yield_research(full: dict, top_n: int = None):
    """
    Print complete cross-input-level yield table.
    If top_n is None, shows all crops with yield data.
    """
    input_levels = ["HRLM", "HILM", "LRLM", "LILM"]
    errors = full.get("errors", {})

    print(f"\n{'='*75}")
    print(f"  Full yield research — all input levels")
    print(f"  Unit: {YIELD_UNIT_NOTE}")
    print(f"{'='*75}")

    for il in input_levels:
        yields = full.get(il, [])
        label = INPUT_LEVEL_LABELS.get(il, il)
        to_display = yields[:top_n] if top_n and top_n < len(yields) else yields

        print(f"\n  [{il}] {label}  —  {len(yields)} crops with yield data")
        print(f"  {'Rank':<5} {'Crop':<25} {'Yield (kg/ha)':>14} {'Ceiling (kg/ha)':>16} {'Gap':>8}")
        print(f"  {'-'*5} {'-'*25} {'-'*14} {'-'*16} {'-'*8}")

        if not to_display:
            print("  No yield data.")
            continue

        for i, cy in enumerate(to_display, 1):
            ceiling = f"{cy.yxx_yield:>14,.0f}" if cy.yxx_yield is not None else f"{'N/A':>14}"
            gap = f"{cy.yield_gap_pct:.1f}%" if cy.yield_gap_pct is not None else "N/A"
            print(
                f"  {i:<5} {cy.crop_name:<25} "
                f"{cy.ylx_yield:>14,.0f} "
                f"{ceiling:>16} "
                f"{gap:>8}"
            )

        if errors.get(il):
            for e in errors[il]:
                print(f"  Warning: {e}")

    print(f"\n{'='*75}\n")


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")

    from gaez_scripts.metadata.gaez_metadata_templates import CROP_REGISTRY

    engine = CropYieldEngine(
        db_path="ardhi.db",
        tiff_folder="D:/ARDHI/TIFF/clipped",
        crop_registry=CROP_REGISTRY,
    )

    # Test location: Medjerda Valley, northern Tunisia (prime farmland)
    lat, lon = 36.72, 9.68

    # Single input level
    result = engine.estimate(lat, lon, input_level="HRLM")
    print_yield(result, top_n=10)

    # Compare best crop across all input levels
    all_results = engine.estimate_all_inputs(lat, lon)
    print_yield_comparison(all_results)

    # Full research — every crop, every input level
    full = engine.estimate_all_inputs_full(lat, lon)
    print_full_yield_research(full)

    engine.close()