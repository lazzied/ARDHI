import logging
from typing import Any

import pandas as pd

from ardhi.db.ardhi import ArdhiRepository
from ardhi.db.connections import close_connection, get_ecocrop_connection
from ardhi.db.ecocrop import EcoCropRepository
from ardhi.db.hwsd import HwsdRepository
from engines.OCR_processing.models import InputLevel, Texture, WaterSupply, pH_level
from engines.global_engines.constants import (
    ASCENDING_ATTRIBUTES,
    ATTRIBUTE_TO_HEADER,
    BOOLEAN_ATTRIBUTES,
    CLIMATE_NEEDS_COLUMNS,
    DESCENDING_ATTRIBUTES,
    SHEET_NAMES,
    SOIL_NEEDS_COLUMNS,
    STANDARD_UNITS,
    TERRAIN_NEEDS_COLUMNS,
)
from engines.global_engines.models import CropEcologicalRequirements


logger = logging.getLogger(__name__)


def _extract_group(
    attributes: dict[str, Any],
    group_spec: dict[str, list[str]],
) -> dict[str, dict[str, Any]]:
    return {
        need: {col: attributes[col] for col in columns if col in attributes}
        for need, columns in group_spec.items()
    }


class EdaphicAugmentation:
    def __init__(self, filepath: str):
        self._sheets = pd.read_excel(filepath, sheet_name=None, header=None)

    def _parse_sq_sheet(self, df: pd.DataFrame) -> dict:
        labels = df.iloc[:, 0].astype(str).str.strip()
        data = df.iloc[:, 1:]

        attr_rows: dict[str, dict] = {}
        for row_idx, label in labels.items():
            if label.endswith("_val"):
                attr = label[:-4]
                attr_rows.setdefault(attr, {})["val"] = data.loc[row_idx].reset_index(drop=True)
            elif label.endswith("_fct"):
                attr = label[:-4]
                attr_rows.setdefault(attr, {})["fct"] = data.loc[row_idx].reset_index(drop=True)

        result = {}
        for attr, rows in attr_rows.items():
            if attr not in ATTRIBUTE_TO_HEADER or "val" not in rows or "fct" not in rows:
                continue

            val_row = rows["val"]
            fct_row = pd.to_numeric(rows["fct"], errors="coerce")
            valid_mask = fct_row.notna()
            val_row = val_row[valid_mask].reset_index(drop=True)
            fct_row = fct_row[valid_mask].reset_index(drop=True)

            if fct_row.empty:
                continue

            opt_mask = fct_row == 100
            if not opt_mask.any():
                continue
            opt_raw = val_row[opt_mask].iloc[0]

            if attr in BOOLEAN_ATTRIBUTES:
                opt_val = bool(int(opt_raw))
                abs_raw = val_row[fct_row == fct_row.min()].iloc[0]
                abs_val = bool(int(abs_raw))
            elif attr in ASCENDING_ATTRIBUTES:
                opt_val = opt_raw
                numeric = pd.to_numeric(val_row, errors="coerce")
                non_zero = numeric[(numeric.notna()) & (numeric != 0)]
                abs_val = non_zero.min() if not non_zero.empty else val_row[fct_row.idxmin()]
            elif attr in DESCENDING_ATTRIBUTES:
                opt_val = opt_raw
                numeric = pd.to_numeric(val_row, errors="coerce")
                non_zero = numeric[(numeric.notna()) & (numeric != 0)]
                abs_val = non_zero.max() if not non_zero.empty else val_row[fct_row.idxmin()]
            else:
                opt_val = opt_raw
                abs_val = val_row[fct_row.idxmin()]

            def to_python(value):
                if hasattr(value, "item"):
                    return value.item()
                return value

            header = ATTRIBUTE_TO_HEADER[attr]
            result[header] = {
                "opt": to_python(opt_val),
                "abs": to_python(abs_val),
                "uni": STANDARD_UNITS[attr],
            }

        return result

    def parse(self) -> dict:
        return {
            sq_label: self._parse_sq_sheet(self._sheets[sq_key])
            for sq_key, sq_label in SHEET_NAMES.items()
            if sq_key in self._sheets
        }


class EcoCrop:
    def __init__(self, eco_crop_repo: EcoCropRepository, edaphic_augmentation: EdaphicAugmentation) -> None:
        self._repo = eco_crop_repo
        self._raw: dict[str, dict[str, Any]] = eco_crop_repo.query_from_ecology()
        self._soil_quality: dict[str, dict[str, Any]] = edaphic_augmentation.parse()

    def get_crop_needs(self, crop_name: str) -> CropEcologicalRequirements:
        attributes = self._raw[crop_name]

        soil_needs = {
            key.lower(): value
            for key, value in _extract_group(attributes, SOIL_NEEDS_COLUMNS).items()
        }
        for sq_attrs in self._soil_quality.values():
            for attr_name, values in sq_attrs.items():
                soil_needs[attr_name.lower()] = values

        return CropEcologicalRequirements(
            climate_needs=_extract_group(attributes, CLIMATE_NEEDS_COLUMNS),
            terrain_needs=_extract_group(attributes, TERRAIN_NEEDS_COLUMNS),
            soil_needs=soil_needs,
        )

    def get_all_crop_needs(self) -> dict[str, CropEcologicalRequirements]:
        return {name: self.get_crop_needs(name) for name in self._raw}


def build_crop_needs_report(
    ardhi_repo: ArdhiRepository,
    eco_crop_repo: EcoCropRepository,
    input_level: InputLevel,
    water_supply: WaterSupply,
    ph_level: pH_level,
    texture_class: Texture,
) -> dict[str, CropEcologicalRequirements]:
    result = {}
    skipped = []

    crops_edaphic_paths_dict = ardhi_repo.query_crop_edaphic_paths(input_level, water_supply, ph_level, texture_class)

    for crop_name, path in crops_edaphic_paths_dict.items():
        edaphic_augmentation = EdaphicAugmentation(path)
        eco_crop = EcoCrop(eco_crop_repo, edaphic_augmentation)

        if crop_name not in eco_crop._raw:
            skipped.append(crop_name)
            continue

        result[crop_name] = eco_crop.get_crop_needs(crop_name)

    logger.info(
        "Built crop ecology report: total=%s found=%s skipped=%s",
        len(crops_edaphic_paths_dict),
        len(result),
        len(skipped),
    )
    if result:
        logger.debug("Crop ecology report found: %s", sorted(result))
    if skipped:
        logger.debug("Crop ecology report skipped: %s", sorted(skipped))

    return result


if __name__ == "__main__":
    from ardhi.db.connections import get_ardhi_connection, get_hwsd_connection

    conn_eco = get_ecocrop_connection()
    conn_hwsd = get_hwsd_connection()
    conn_ardhi = get_ardhi_connection()

    eco_crop_repo = EcoCropRepository(conn_eco)
    ardhi_repo = ArdhiRepository(conn_ardhi)
    hwsd_repo = HwsdRepository(conn_hwsd)

    report = build_crop_needs_report(
        ardhi_repo,
        eco_crop_repo,
        InputLevel.HIGH,
        WaterSupply.RAINFED,
        pH_level.BASIC,
        Texture.FINE,
    )
    logger.info("Built %s crop ecology records", len(report))

    close_connection(conn_eco)
    close_connection(conn_hwsd)
    close_connection(conn_ardhi)
