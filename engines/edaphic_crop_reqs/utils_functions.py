import re
from typing import List

import pandas as pd

from engines.edaphic_crop_reqs.models import AttributePair, InputLevel


def attribute_pairs_to_df(pairs: List[AttributePair]) -> pd.DataFrame:
    rows, index = [], []
    for pair in pairs:
        attr  = pair.attribute_name
        curve = pair.rating_curve
        rows.append(curve.thresholds);  index.append(f"{attr}_val")
        rows.append(curve.penalties);   index.append(f"{attr}_fct")
    return pd.DataFrame(rows, index=index)

def generate_sq_df(dfs: List[pd.DataFrame]) -> pd.DataFrame:
    return pd.concat(dfs, axis=0)

def write_sq_df_to_csv(df: pd.DataFrame, path: str) -> None:
    df.to_csv(path, header=False)
    
def parse_sq_labels(text: str) -> List[str]:
    return [f"SQ{n}" for n in re.findall(r"SQ\s*(\d+)", text)]

def parse_input_levels(text: str) -> List[InputLevel]:
    lower = text.lower()
    return [lvl for lvl in InputLevel if lvl.value in lower]