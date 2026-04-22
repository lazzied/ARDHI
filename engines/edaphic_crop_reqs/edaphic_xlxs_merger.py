import pandas as pd
import os

def merge_sq_csvs_to_xlsx(input_dir: str, output_file: str) -> None:
    """
    Read SQ1_merged.csv … SQ7_merged.csv from input_dir and write them
    into a single Excel workbook, one sheet per SQ in order.
    """
    sq_labels = [f"SQ{i}" for i in range(1, 8)]

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        for sq_label in sq_labels:
            csv_path = os.path.join(input_dir, f"{sq_label}_merged.csv")

            if not os.path.exists(csv_path):
                print(f"  Skipped {sq_label} — file not found: {csv_path}")
                continue

            df = pd.read_csv(csv_path, header=None, index_col=0)
            df.index.name = None

            df.to_excel(writer, sheet_name=sq_label, header=False)
            print(f"  Written sheet: {sq_label}  ({len(df)} rows)")

    print(f"\nDone → {output_file}")


if __name__ == "__main__":
    INPUT_DIR   = "engines/edaphic_crop_reqs/results"
    OUTPUT_FILE = "engines/edaphic_crop_reqs/results/SQ_aggregated.xlsx"
    merge_sq_csvs_to_xlsx(INPUT_DIR, OUTPUT_FILE)