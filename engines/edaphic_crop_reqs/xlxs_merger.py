import pandas as pd
import os
import glob


def merge_csvs_to_xlsx(
    folder="my_csv_folder",
    output_file="merged_output.xlsx",
):
    csv_files = sorted(glob.glob(os.path.join(folder, "*.csv")))

    if not csv_files:
        print(f"No CSV files found in '{folder}'.")
        return

    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        for csv_path in csv_files:
            sheet_name = os.path.splitext(os.path.basename(csv_path))[0][:31]
            df = pd.read_csv(csv_path)
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"Added: '{csv_path}' → sheet '{sheet_name}'")

    print(f"\nDone! Saved to: {output_file}")


if __name__ == "__main__":
    merge_csvs_to_xlsx(
        "engines/edaphic_crop_reqs/results", "engines/edaphic_crop_reqs/results/merged_output.xlsx"
    )