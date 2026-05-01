import csv
from pathlib import Path
from engines.OCR_processing.models import AugmentedLayer, AugmentedLayersGroup
import pandas as pd
import os
import glob

TEMP_FOLDER = "engines/soil_properties_builder/output/temp_csv"

class Output:
    
    
    @staticmethod
    def to_csv(layer: AugmentedLayer, output_path: str):
        fieldnames = ["CODE"] + list(layer.values.keys())
        row = {"CODE": layer.smu_id, **layer.values}
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(row)

    @staticmethod
    def _merge_csvs_to_xlsx(output_dir: str, filename: str):
        output_path = f"{output_dir}/{filename}.xlsx"
        csv_files = sorted(glob.glob(os.path.join(TEMP_FOLDER, "*.csv")))

        if not csv_files:
            print(f"No CSV files found in '{output_dir}'.")
            return

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for csv_path in csv_files:
                sheet_name = os.path.splitext(os.path.basename(csv_path))[0][:31]
                df = pd.read_csv(csv_path)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                print(f"Added: '{csv_path}' → sheet '{sheet_name}'")

        print(f"\nDone! Saved to: {output_path}")

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
        print(f"Cleaned up temp folder: {TEMP_FOLDER}")