import pandas as pd
import os


def split_excel_to_csv(input_file, output_dir="output_csvs"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    xl = pd.ExcelFile(input_file)

    for sheet_name in xl.sheet_names:
        df = pd.read_excel(
            xl,
            sheet_name = sheet_name,
            header     = None,   # do NOT treat row 0 as column names —
                                  # every row is data, preserving exact row indices
            dtype      = str,    # read everything as string — prevents pandas from
                                  # converting "1" to 1.0, "999" to 999.0, etc.
        )

        # Replace the literal string 'nan' that dtype=str can produce for empty cells
        # back to genuine NaN so to_csv writes them as empty strings (,,)
        df = df.replace("nan", pd.NA)

        # Excel sheets often have an empty column A (used for spacing/borders).
        # Drop any leading all-NaN columns so data starts at col 0,
        # matching the reference format the parsers depend on.
        while not df.empty and df.iloc[:, 0].isna().all():
            df = df.iloc[:, 1:].reset_index(drop=True)

        clean_name  = sheet_name.replace(" ", "_")
        output_file = os.path.join(output_dir, f"{clean_name}.csv")

        df.to_csv(
            output_file,
            index    = False,   # no row-number column prepended
            header   = False,   # no synthetic header row prepended
            encoding = "utf-8", # plain UTF-8 — no BOM (utf-8-sig adds \xef\xbb\xbf
                                 # which corrupts the first cell when read back)
        )
        print(f"Converted: {output_file}")


# Usage
INPUT_FILE = "engines/edaphic_crop_reqs/appendixes/drip_irrigation_appendix/Appendix_6-5.xlsx"
OUTPUT_DIR = "engines/edaphic_crop_reqs/appendixes/drip_irrigation_appendix/csv_sheets"
split_excel_to_csv(INPUT_FILE, OUTPUT_DIR)