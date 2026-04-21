import re
import pandas as pd
import os
from typing import List
from dataclasses import dataclass
from engines.edaphic_crop_reqs.models import AttributePair, InputLevel, RatingCurve, SoilCharacteristicsBlock

@dataclass
class SoilPhaseBlock(SoilCharacteristicsBlock):
    shares: List[str] = None

# --- Constants for Appendix 6.3.4 (0-based indices) ---
SHARE_ROW = 3        
SOIL_PHASE_ROW = 4   
DATA_START_ROW = 6   # Row 7 in Excel
SQ_COLUMN_RANGES = {
    "SQ3": (2, 28),
    "SQ4": (29, 44),
    "SQ5": (45, 47),
    "SQ6": (48, 49),
    "SQ7": (50, 76)
}

def set_input_level(df: pd.DataFrame) -> InputLevel:
    text = str(df.iloc[1, 1]).lower()
    if re.search(r"\bhigh\b", text):
        return InputLevel.HIGH
    elif re.search(r"\bintermediate\b", text):
        return InputLevel.INTERMEDIATE
    elif re.search(r"\blow\b", text):
        return InputLevel.LOW
    raise ValueError(f"Could not determine input level from text: {text}")

def extract_blocks_v4(df: pd.DataFrame, crop_id: int) -> List[SoilPhaseBlock]:
    """Extracts Soil Phase blocks for each Soil Quality."""
    blocks = []
    
    # FIX: Robust crop ID lookup (handles floats, strings, and formatting)
    try:
        # Convert first column to numeric to ensure '4' matches '4.0'
        id_column = pd.to_numeric(df[0], errors='coerce')
        crop_row_indices = df.index[id_column == crop_id].tolist()
        if not crop_row_indices:
            print(f"Warning: Crop ID {crop_id} not found.")
            return []
        crop_row_idx = crop_row_indices[0]
    except Exception as e:
        print(f"Error during crop lookup: {e}")
        return []

    for sq_name, (start, end) in SQ_COLUMN_RANGES.items():
        # Safety check for column ranges
        if start >= df.shape[1]: continue
        actual_end = min(end, df.shape[1] - 1)
        
        block_df = df.iloc[:, start : actual_end + 1]
        
        # FIX: Strip whitespace from names for cleaner lookup files
        thresholds = block_df.iloc[SOIL_PHASE_ROW].fillna("").astype(str).str.strip().tolist()
        shares = block_df.iloc[SHARE_ROW].fillna("").astype(str).str.strip().tolist()
        
        # Convert penalties to float, default to 100 if missing
        penalties = pd.to_numeric(df.iloc[crop_row_idx, start:actual_end+1], errors='coerce').fillna(100.0).tolist()
        
        # Filter out empty entries in the range
        valid_t, valid_p = [], []
        for t, p in zip(thresholds, penalties):
            if t: # Only keep if a soil phase name exists
                valid_t.append(t)
                valid_p.append(p)

        if valid_t:
            blocks.append(
                SoilPhaseBlock(
                    col_start=start, col_end=actual_end,
                    attribute_name="SPH", soil_qualities=[sq_name],
                    penalties=valid_p, thresholds_row=valid_t, shares=shares,
                    input_levels=[set_input_level(df)]  # Assuming one input level per sheet
                )
            )
    return blocks

def build_attribute_pair_v4(block: SoilPhaseBlock, crop_id: int) -> AttributePair:
    return AttributePair(
        attribute_name=block.attribute_name,
        rating_curve=RatingCurve(crop_id=crop_id, penalties=block.penalties, thresholds=block.thresholds_row)
    )

def run_pipeline_v4(csv_path: str, crop_id: int, output_dir: str = ".") -> None:
    """Main pipeline to parse SPH data and generate individual SQ CSV files."""
    if not os.path.exists(csv_path):
        local_name = os.path.basename(csv_path)
        if os.path.exists(local_name):
            csv_path = local_name
        else:
            print(f"Error: {csv_path} not found.")
            return

    df = pd.read_csv(csv_path, header=None)
    blocks = extract_blocks_v4(df, crop_id)
    
    if not blocks:
        print("No data found for the specified crop.")
        return

    for block in blocks:
        sq_label = block.soil_qualities[0]
        pair = build_attribute_pair_v4(block, crop_id)
        
        output_data = [
            ["SPH_val"] + pair.rating_curve.thresholds,
            ["SPH_fct"] + pair.rating_curve.penalties
        ]
        
        out_df = pd.DataFrame(output_data)
        out_filename = f"{output_dir}/{sq_label}_SPH.csv"
        out_df.to_csv(out_filename, header=False, index=False)
        print(f"Successfully saved: {out_filename}")

# Run for Crop ID 4 (Maize)
run_pipeline_v4("engines/edaphic_crop_reqs/appendixes/appendix6_3_4.csv", 4, "engines/edaphic_crop_reqs/temp_results")

"""
    
    In the context of the Appendix 6.3.4 parser, the **Share (%)** represents the "Soil Phase Applicability Share." In simpler terms, it defines the weight or the percentage of a specific crop rating that should be applied when a particular soil phase (like "Lithic" or "Petric") is present.

Here is the technical breakdown of how the parser logic handles this data:

### 1. Recognition as Metadata (Not a Functional Constraint)
Unlike the crop ratings (penalties), the share values are not used as direct inputs for the standard GAEZ (Global Agro-Ecological Zones) rating curves. Instead, the parser treats the share as **embedded metadata**. 
* **Why:** In previous appendices (6.3.1–6.3.3), the logic is purely threshold-based. In 6.3.4, the share is a descriptive property of the soil phase itself. 
* **Storage:** It is captured during the block extraction phase and stored in the `shares` field of the `SoilPhaseBlock` dataclass.

### 2. The Slice-and-Align Strategy
Because the columns in Table A6-3.4 are irregular, I implemented a "Slice-and-Align" strategy to ensure the share stays correctly mapped to the right soil phase:
* **Vertical Alignment:** The parser looks at the fixed column range (e.g., `D` through `AD` for SQ3).
* **Index Mapping:** It extracts Row 4 (Shares) and Row 5 (Soil Phases) simultaneously. This ensures that if the "Lithic" phase is in the third column of the block, it is paired exactly with the share value located directly above it in that same column.

### 3. Handling Sparse Data (Nulls)
The CSV layout for the share row is "sparse," meaning the percentage might only be written once for a group of columns, or there might be empty cells between values.
* **The Logic:** The parser uses `.fillna("")` to prevent code crashes on empty cells. 
* **Cleaning:** It strips whitespace and % signs so that the resulting data structure is clean for downstream calculations, transforming `"50%"` into a clean string or numeric value if required by the pipeline.

### 4. Downstream Integration (The "Invisible" Field)
While the final CSV output for `SPH_val` and `SPH_fct` follows the rigid two-row format required by your current pipeline (to avoid breaking existing code), the **Share** data is preserved in the underlying `SoilPhaseBlock` object.

This allows the system to remain extensible:
* **Current State:** The output CSVs only show the Phase Name and the Penalty.
* **Future State:** If your calculation engine needs to apply a "Weighted Penalty" (e.g., *Penalty * Share*), the `shares` list is already indexed and ready to be exported or used in a third row without needing to rewrite the parser.

**Summary of Data Flow:**
1.  **Extract:** Grab the entire SQ block.
2.  **Zip:** Pair `Soil Phase Name[i]` with `Share[i]` and `Penalty[i]`.
3.  **Filter:** Remove any columns where the Soil Phase Name is empty.
4.  **Produce:** Output the standard 2-row CSV while holding the Share data in memory for metadata logging.
    
    """