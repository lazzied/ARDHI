import csv
import glob
import logging
import os
from pathlib import Path

import pandas as pd

from engines.OCR_processing.models import AugmentedLayer, AugmentedLayersGroup


logger = logging.getLogger(__name__)

TEMP_FOLDER = "engines/soil_properties_builder/output/temp_csv"


class Output:
    @staticmethod
    def to_csv(layer: AugmentedLayer, output_path: str):
        fieldnames = ["CODE"] + list(layer.values.keys())
        row = {"CODE": layer.smu_id, **layer.values}
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(row)

    @staticmethod
    def _merge_csvs_to_xlsx(output_dir: str, filename: str):
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        output_path = f"{output_dir}/{filename}.xlsx"
        csv_files = sorted(glob.glob(os.path.join(TEMP_FOLDER, "*.csv")))

        if not csv_files:
            logger.warning("No CSV files found in '%s'.", TEMP_FOLDER)
            return

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for csv_path in csv_files:
                sheet_name = os.path.splitext(os.path.basename(csv_path))[0][:31]
                df = pd.read_csv(csv_path)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                logger.debug("Added '%s' to sheet '%s'", csv_path, sheet_name)

        logger.info("Saved augmented soil workbook to %s", output_path)

    @staticmethod
    def to_xlsx(group: AugmentedLayersGroup, output_dir: str, filename: str):
        Path(TEMP_FOLDER).mkdir(parents=True, exist_ok=True)

        for layer in group.layers:
            Output.to_csv(layer, f"{TEMP_FOLDER}/{layer.layer}.csv")

        Output._merge_csvs_to_xlsx(output_dir, filename)
        Output.cleanup_temp()
        return os.path.join(output_dir, f"{filename}.xlsx")

    @staticmethod
    def cleanup_temp():
        for file in Path(TEMP_FOLDER).glob("*.csv"):
            file.unlink()
        logger.debug("Cleaned up temp folder: %s", TEMP_FOLDER)
