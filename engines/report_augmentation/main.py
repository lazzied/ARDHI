
from __future__ import annotations
from typing import List

import rasterio

from engines.report_augmentation.models_and_io import AugmentedLayer, FarmerReportParser, HWSDRepository
from engines.report_augmentation.output import ExcelExporter, ProvenanceLogger
from engines.report_augmentation.processing import AttributeProcessor, LayerInterpolator

def get_smu(raster_path: str, lat: float, lon: float) -> int:
    """Raster pixel at (lat, lon) → SMU ID."""
    src = rasterio.open(raster_path)
    row, col = src.index(lon, lat)
    # Read just one pixel, not the whole raster
    window = rasterio.windows.Window(col, row, 1, 1)
    smu_id = src.read(1, window=window)[0, 0]
    return int(smu_id)

FARM_COORDINATES = (35.0, 9.0)
RASTER_PATH = "hwsd_data/hwsd2_smu_tunisia.tif"
HWSD_SMU_ID   = get_smu(RASTER_PATH, *FARM_COORDINATES)

HWSD_DB_PATH  = "hwsd.db"
REPORT_PATH   = "engines/report_augmentation/rapport_values.json"
OUTPUT_PATH   = "engines/report_augmentation/results/soil_augmentation_output.xlsx"
LOG_CSV_PATH  = "engines/report_augmentation/results/soil_augmentation_log.csv"
LOG_JSON_PATH = "engines/report_augmentation/results/soil_augmentation_log.json"



class SoilAugmentationPipeline:
    """Wires all components together; each can be replaced independently."""

    def __init__(
        self,
        parser:       FarmerReportParser,
        repo:         HWSDRepository,
        processor:    AttributeProcessor,
        interpolator: LayerInterpolator,
        logger:       ProvenanceLogger,
        exporter:     ExcelExporter,
    ):
        self._parser       = parser
        self._repo         = repo
        self._processor    = processor
        self._interpolator = interpolator
        self._logger       = logger
        self._exporter     = exporter

    _HWSD_SUBSTITUTES = {
        "OC":  lambda h: h.org_carbon,
        "pH":  lambda h: h.ph_water,
        "EC":  lambda h: h.elec_cond,
        "CCB": lambda h: h.tcarbon_eq,
    }

    def run(
        self,
        report_path: str,
        smu_id:      int,
        output_path: str,
        log_csv:     str,
        log_json:    str,
    ) -> List[AugmentedLayer]:

        print("[1/5] Parsing farmer report")
        report = self._parser.parse(report_path)

        print(f"[2/5] Loading HWSD layers  (SMU_ID={smu_id})")
        hwsd_layers = self._repo.get_all_layers(smu_id)
        if not hwsd_layers:
            raise ValueError(f"No HWSD data for HWSD2_SMU_ID={smu_id}")
        print(f"      {len(hwsd_layers)} layers: {[l.layer for l in hwsd_layers]}")

        print("[3/5] Augmenting layers")
        layer_map = {l.layer: l for l in hwsd_layers}
        output: List[AugmentedLayer] = []

        # D1 — fully farmer-enriched
        d1_hw = layer_map["D1"]
        d1_v, d1_f = self._processor.process(report, d1_hw)
        d1_aug = AugmentedLayer("D1", 0, 20, d1_v, d1_f, smu_id)
        output.append(d1_aug)
        self._logger.record("0-20", d1_aug)
        print("      D1  (0-20 cm)   → farmer-enriched")

        # D2 — interpolated
        if "D2" in layer_map:
            d2_hw      = layer_map["D2"]
            d2_v, d2_f = self._processor.process(report, d2_hw)
            d2_raw     = AugmentedLayer("D2", 20, 40, d2_v, d2_f, smu_id)
            d2_interp  = self._interpolator.interpolate(d1_aug, d2_raw)
            output.append(d2_interp)
            self._logger.record("20-40", d2_interp)
            print("      D2  (20-40 cm)  → interpolated (D1_enriched ↔ HWSD D2)")

        # D3-D7 — HWSD direct
        for code in ["D3", "D4", "D5", "D6", "D7"]:
            hw = layer_map.get(code)
            if hw is None:
                continue
            vals, flags = self._processor.process(report, hw)
            for attr, extractor in self._HWSD_SUBSTITUTES.items():
                hwsd_val = extractor(hw)
                if hwsd_val is not None:
                    vals[attr]  = round(float(hwsd_val), 4)
                    flags[attr] = (
                        f"HWSD direct | farmer data not applicable "
                        f"at depth {hw.top_dep}-{hw.bot_dep}cm"
                    )
            aug = AugmentedLayer(code, hw.top_dep, hw.bot_dep, vals, flags, smu_id)
            output.append(aug)
            self._logger.record(f"{hw.top_dep}-{hw.bot_dep}", aug)
            print(f"      {code}  ({hw.top_dep}-{hw.bot_dep} cm) → HWSD direct")

        print("[4/5] Writing outputs")
        self._exporter.export(output, output_path)
        self._logger.flush(log_csv, log_json)

        print("[5/5] Done")
        return output


# ===========================================================================
# ENTRY POINT
# ===========================================================================

def main() -> None:
    repo = HWSDRepository(HWSD_DB_PATH)
    pipeline = SoilAugmentationPipeline(
        parser       = FarmerReportParser(),
        repo         = repo,
        processor    = AttributeProcessor(repo),
        interpolator = LayerInterpolator(),
        logger       = ProvenanceLogger(),
        exporter     = ExcelExporter(),
    )
    pipeline.run(
        report_path = REPORT_PATH,
        smu_id      = HWSD_SMU_ID,
        output_path = OUTPUT_PATH,
        log_csv     = LOG_CSV_PATH,
        log_json    = LOG_JSON_PATH,
    )


if __name__ == "__main__":
    main()