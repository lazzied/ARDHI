"""
Crop recommendation engine for Tunisia.

Given a GPS coordinate, reads pre-computed GAEZ v5 suitability rasters
from the local clipped tiff collection and returns ranked crop recommendations.

Uses three suitability layers:
  - RES05-SXX30AS: continuous suitability index (0-10000) → primary ranking metric
  - RES05-SIX30AS: suitability class index (1-9) → human-readable class label
  - RES05-SX2:     share of VS+S+MS land (0-10000, 10km) → regional overview

For each input level (HRLM, HILM, LRLM, LILM), a separate suitability score exists.
The engine queries all layers and presents the farmer with a ranked list.
"""


import os
import sqlite3
import rasterio
from rasterio.windows import Window
from dataclasses import dataclass, field
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed


# ──────────────────────────────────────────────────────────────────────
# Suitability class definitions (from GAEZ metadata)
# ──────────────────────────────────────────────────────────────────────

SUITABILITY_CLASSES_SIX = {
    1: {"label": "Very high",      "si_min": 85, "description": "Excellent conditions for this crop"},
    2: {"label": "High",           "si_min": 70, "description": "Very good conditions with minor limitations"},
    3: {"label": "Good",           "si_min": 55, "description": "Good conditions with moderate limitations"},
    4: {"label": "Medium",         "si_min": 40, "description": "Moderate conditions, yield notably below potential"},
    5: {"label": "Moderate",       "si_min": 25, "description": "Marginal conditions, significant limitations"},
    6: {"label": "Marginal",       "si_min": 10, "description": "Poor conditions, low yield expected"},
    7: {"label": "Very marginal",  "si_min": 0,  "description": "Very poor conditions, minimal yield"},
    8: {"label": "Not suitable",   "si_min": None, "description": "Cannot grow this crop here"},
    9: {"label": "Water",          "si_min": None, "description": "Water body, not land"},
}

INPUT_LEVEL_LABELS = {
    "HRLM": "Rain-fed, high input",
    "HILM": "Irrigated, high input",
    "LRLM": "Rain-fed, low input",
    "LILM": "Irrigated, low input",
}


# ──────────────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────────────

@dataclass
class CropScore:
    """Suitability result for one crop at one location under one input level."""
    crop_code: str
    crop_name: str
    input_level: str
    sxx_index: Optional[int] = None
    six_class: Optional[int] = None
    sx2_share: Optional[int] = None

    @property
    def suitability_label(self) -> str:
        if self.six_class and self.six_class in SUITABILITY_CLASSES_SIX:
            return SUITABILITY_CLASSES_SIX[self.six_class]["label"]
        return "Unknown"

    @property
    def suitability_description(self) -> str:
        if self.six_class and self.six_class in SUITABILITY_CLASSES_SIX:
            return SUITABILITY_CLASSES_SIX[self.six_class]["description"]
        return ""

    @property
    def is_suitable(self) -> bool:
        return self.six_class is not None and 1 <= self.six_class <= 7

    @property
    def sxx_percentage(self) -> float:
        if self.sxx_index is not None and self.sxx_index >= 0:
            return self.sxx_index / 100.0
        return 0.0

    @property
    def sx2_percentage(self) -> float:
        if self.sx2_share is not None and self.sx2_share >= 0:
            return self.sx2_share / 100.0
        return 0.0


@dataclass
class Recommendation:
    """Complete recommendation result for a location."""
    lat: float
    lon: float
    input_level: str
    input_level_label: str
    scores: list[CropScore] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ranked(self) -> list[CropScore]:
        """All suitable crops sorted by suitability index descending."""
        suitable = [s for s in self.scores if s.is_suitable and s.sxx_index is not None]
        return sorted(suitable, key=lambda s: s.sxx_index, reverse=True)

    def top_n(self, n: int = 10) -> list[CropScore]:
        """
        Return top N suitable crops.
        If n exceeds the number of suitable crops, return all suitable crops.
        """
        ranked = self.ranked
        return ranked[:min(n, len(ranked))]

    @property
    def not_suitable(self) -> list[CropScore]:
        return [s for s in self.scores if not s.is_suitable]


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
# Recommendation engine
# ──────────────────────────────────────────────────────────────────────

class CropRecommendationEngine:
    """
    Reads GAEZ suitability rasters and ranks crops for a given location.

    Usage:
        engine = CropRecommendationEngine(
            db_path="ardhi.db",
            tiff_folder="D:/ARDHI/TIFF/clipped",
        )
        result = engine.recommend(lat=36.8, lon=10.18, input_level="HRLM")
        for crop in result.top_n(10):
            print(f"{crop.crop_name}: {crop.sxx_percentage:.1f}% ({crop.suitability_label})")
    """

    SUITABILITY_LAYERS = {
        "SXX": "RES05-SXX30AS",
        "SIX": "RES05-SIX30AS",
        "SX2": "RES05-SX2",
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
        rows = self.conn.execute(
            "SELECT crop_code, file_path FROM tiff_files "
            "WHERE map_code = ? AND crop_code IS NOT NULL",
            (map_code,)
        ).fetchall()
        return {row["crop_code"]: row["file_path"] for row in rows}

    def get_available_crops(self, input_level: str = "HRLM") -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT crop_code FROM tiff_files "
            "WHERE map_code = ? AND input_level = ? AND crop_code IS NOT NULL",
            (self.SUITABILITY_LAYERS["SXX"], input_level)
        ).fetchall()
        return [row["crop_code"] for row in rows]

    def _score_one_crop(
        self,
        crop_code: str,
        lat: float,
        lon: float,
        input_level: str,
        sxx_paths: dict,
        six_paths: dict,
        sx2_paths: dict,
    ) -> CropScore:
        """
        Read all three layers for a single crop and return a CropScore.
        Early exit: if SXX is nodata, skip SIX and SX2 reads entirely.
        """
        crop_name = self._crop_names.get(crop_code, crop_code)

        sxx_val = self.reader.read_pixel(sxx_paths.get(crop_code, ""), lat, lon)

        if sxx_val is None:
            return CropScore(
                crop_code=crop_code,
                crop_name=crop_name,
                input_level=input_level,
            )

        six_val = self.reader.read_pixel(six_paths.get(crop_code, ""), lat, lon)
        sx2_val = self.reader.read_pixel(sx2_paths.get(crop_code, ""), lat, lon)

        return CropScore(
            crop_code=crop_code,
            crop_name=crop_name,
            input_level=input_level,
            sxx_index=int(sxx_val),
            six_class=int(six_val) if six_val is not None else None,
            sx2_share=int(sx2_val) if sx2_val is not None else None,
        )

    def _run_for_input_level(
        self,
        lat: float,
        lon: float,
        input_level: str,
        sx2_paths: dict,
    ) -> Recommendation:
        """
        Internal helper: run scoring for one input level given pre-fetched SX2 paths.
        Used by both recommend() and recommend_all_inputs_full().
        """
        result = Recommendation(
            lat=lat,
            lon=lon,
            input_level=input_level,
            input_level_label=INPUT_LEVEL_LABELS.get(input_level, input_level),
        )

        sxx_paths = self._get_tiff_paths(self.SUITABILITY_LAYERS["SXX"], input_level)
        six_paths = self._get_tiff_paths(self.SUITABILITY_LAYERS["SIX"], input_level)

        if not sxx_paths:
            result.errors.append(
                f"No suitability data found for input level {input_level}. "
                f"Check that RES05-SXX30AS tiffs are in the database."
            )
            return result

        all_crops = sorted(sxx_paths.keys())

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            futures = {
                executor.submit(
                    self._score_one_crop,
                    crop_code, lat, lon, input_level,
                    sxx_paths, six_paths, sx2_paths,
                ): crop_code
                for crop_code in all_crops
            }

            for future in as_completed(futures):
                try:
                    score = future.result()
                    result.scores.append(score)
                except Exception as e:
                    crop_code = futures[future]
                    result.errors.append(f"Failed to score {crop_code}: {e}")

        return result

    def recommend(
        self,
        lat: float,
        lon: float,
        input_level: str = "HRLM",
    ) -> Recommendation:
        """
        Generate crop recommendations for a location under one input level.

        Args:
            lat: Latitude (e.g. 36.8 for northern Tunisia)
            lon: Longitude (e.g. 10.18 for Tunis area)
            input_level: HRLM (rain-fed high), HILM (irrigated high),
                        LRLM (rain-fed low), LILM (irrigated low)

        Returns:
            Recommendation with ranked CropScore objects.
            Use result.top_n(n) to get the top N crops,
            or result.ranked for the full sorted list.
        """
        sx2_paths = self._get_tiff_paths_no_input(self.SUITABILITY_LAYERS["SX2"])
        return self._run_for_input_level(lat, lon, input_level, sx2_paths)

    def recommend_all_inputs(
        self,
        lat: float,
        lon: float,
    ) -> dict[str, Recommendation]:
        """
        Run recommendations for all four input levels.
        SX2 paths fetched once and shared across all input levels.
        Returns {"HRLM": Recommendation, "HILM": ..., "LRLM": ..., "LILM": ...}
        Use result[il].top_n(n) or result[il].ranked on each entry.
        """
        sx2_paths = self._get_tiff_paths_no_input(self.SUITABILITY_LAYERS["SX2"])
        return {
            il: self._run_for_input_level(lat, lon, il, sx2_paths)
            for il in ["HRLM", "HILM", "LRLM", "LILM"]
        }

    def recommend_all_inputs_full(
        self,
        lat: float,
        lon: float,
    ) -> dict[str, list[CropScore]]:
        """
        Run recommendations for all four input levels and return the complete
        picture — every crop, every input level, fully scored and ranked.

        No top_n filtering applied here. Returns everything so the caller
        can slice, compare, or display however they want.

        Returns:
            {
                "HRLM": [CropScore, ...],   # all ranked suitable crops
                "HILM": [CropScore, ...],
                "LRLM": [CropScore, ...],
                "LILM": [CropScore, ...],
                "errors": {"HRLM": [...], ...}  # any per-level errors
            }
        """
        sx2_paths = self._get_tiff_paths_no_input(self.SUITABILITY_LAYERS["SX2"])

        full = {}
        errors = {}

        for il in ["HRLM", "HILM", "LRLM", "LILM"]:
            rec = self._run_for_input_level(lat, lon, il, sx2_paths)
            full[il] = rec.ranked        # full sorted list, no cutoff
            errors[il] = rec.errors

        full["errors"] = errors
        return full

    def close(self):
        self.conn.close()


# ──────────────────────────────────────────────────────────────────────
# Display helpers
# ──────────────────────────────────────────────────────────────────────

def print_recommendation(rec: Recommendation, top_n: int = 10):
    """
    Pretty-print a recommendation result.
    If top_n exceeds the number of suitable crops, prints all suitable crops.
    """
    print(f"\n{'='*70}")
    print(f"  Crop recommendations at ({rec.lat:.4f}, {rec.lon:.4f})")
    print(f"  Input level: {rec.input_level_label}")
    print(f"{'='*70}")

    ranked = rec.ranked
    if not ranked:
        print("  No suitable crops found at this location.")
        if rec.errors:
            for e in rec.errors:
                print(f"  Error: {e}")
        return

    # If top_n exceeds available crops, show all
    to_display = ranked[:min(top_n, len(ranked))]

    print(f"\n  {'Rank':<5} {'Crop':<25} {'Score':>6} {'Class':<15} {'Region':>8}")
    print(f"  {'-'*5} {'-'*25} {'-'*6} {'-'*15} {'-'*8}")

    for i, score in enumerate(to_display, 1):
        region = f"{score.sx2_percentage:.1f}%" if score.sx2_share is not None else "N/A"
        print(
            f"  {i:<5} {score.crop_name:<25} "
            f"{score.sxx_percentage:>5.1f}% "
            f"{score.suitability_label:<15} "
            f"{region:>8}"
        )

    total_suitable = len(ranked)
    total_unsuitable = len(rec.not_suitable)
    print(f"\n  {total_suitable} crops suitable, {total_unsuitable} not suitable")
    print(f"  Showing {len(to_display)} of {total_suitable}")


def print_comparison(results: dict[str, Recommendation]):
    """Compare top crops across all input levels."""
    print(f"\n{'='*70}")
    print(f"  Input level comparison")
    print(f"{'='*70}\n")

    for il, rec in results.items():
        ranked = rec.ranked
        label = rec.input_level_label
        if ranked:
            top = ranked[0]
            print(f"  {label:<25} Best: {top.crop_name} ({top.sxx_percentage:.1f}%) — {len(ranked)} crops suitable")
        else:
            print(f"  {label:<25} No suitable crops")


def print_full_research(full: dict, top_n: int = None):
    """
    Print the complete cross-input-level research table.
    Shows every suitable crop under every input level side by side.
    If top_n is None, shows all suitable crops.
    """
    input_levels = ["HRLM", "HILM", "LRLM", "LILM"]
    errors = full.get("errors", {})

    print(f"\n{'='*70}")
    print(f"  Full research — all input levels")
    print(f"{'='*70}")

    for il in input_levels:
        scores = full.get(il, [])
        label = INPUT_LEVEL_LABELS.get(il, il)
        to_display = scores[:top_n] if top_n and top_n < len(scores) else scores

        print(f"\n  [{il}] {label}  —  {len(scores)} suitable crops")
        print(f"  {'Rank':<5} {'Crop':<25} {'Score':>6} {'Class':<15} {'Region':>8}")
        print(f"  {'-'*5} {'-'*25} {'-'*6} {'-'*15} {'-'*8}")

        if not to_display:
            print("  No suitable crops.")
            continue

        for i, score in enumerate(to_display, 1):
            region = f"{score.sx2_percentage:.1f}%" if score.sx2_share is not None else "N/A"
            print(
                f"  {i:<5} {score.crop_name:<25} "
                f"{score.sxx_percentage:>5.1f}% "
                f"{score.suitability_label:<15} "
                f"{region:>8}"
            )

        if errors.get(il):
            for e in errors[il]:
                print(f"  Warning: {e}")

    print(f"\n{'='*70}\n")


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")

    from gaez_scripts.metadata.gaez_metadata_templates import CROP_REGISTRY

    engine = CropRecommendationEngine(
        db_path="ardhi.db",
        tiff_folder="D:/ARDHI/TIFF/clipped",
        crop_registry=CROP_REGISTRY,
    )

    lat, lon = 36.72, 9.68
    
    #engine.recommend(lat, lon, input_level="HRLM")
    print_recommendation(engine.recommend(lat, lon, input_level="HRLM"), top_n=30)  # shows all if fewer than 15 suitable
    

    # Single input level — use top_n() on the result
    #result = engine.recommend(lat, lon, input_level="HRLM")
    #print_recommendation(result, top_n=30)      # shows all if fewer than 15 suitable

    # Compare best crop across all input levels
    #all_results = engine.recommend_all_inputs(lat, lon)
    #print_comparison(all_results)

    # Full research — every crop, every input level, no cutoff
    #full = engine.recommend_all_inputs_full(lat, lon)
    #print_full_research(full)                   # all suitable crops
    #print_full_research(full, top_n=5)          # top 5 per input level

    engine.close()
    
    #engines\suitability_engine.py