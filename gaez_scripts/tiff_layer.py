"""
GAEZ URL patterns:
  A — static (2 dims):       GAEZ-V5.{map_code}.tif
  B — land cover (3 dims):   GAEZ-V5.LR-LCC.{lc_class}.tif
  C — RES06 (4 dims):        GAEZ-V5.{map_code}.{crop}.{water_supply}.tif
  D — SQX/SQ-IDX (4 dims):   GAEZ-V5.{map_code}.{sq_factor}.{management}.tif
  E — RES01 (5 dims):        GAEZ-V5.{map_code}.{period}.{climate}.{ssp}.tif
  F — RES02/RES05 (7 dims):  GAEZ-V5.{map_code}.{period}.{climate}.{ssp}.{crop}.{input_level}.tif
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

from gaez_scripts.metadata.gaez_metadata_templates import (
    METADATA_TEMPLATES,
    DATASET_CATEGORIES,
    CROP_REGISTRY,
    CROP_AGGREGATE_GROUPS,
    CLIMATE_MODELS,
    PERIODS,
    SSP_SCENARIOS,
    INPUT_LEVELS,
    WATER_SUPPLY,
    WATER_CONTENT,
    MANAGEMENT_LEVELS,
    SOIL_QUALITIES,
    LAND_COVER_CLASSES,
    LICENSE,
)


# ──────────────────────────────────────────────────────────────────────
# Dataclass
# ──────────────────────────────────────────────────────────────────────

@dataclass
class TiffLayer:
    """One GAEZ tiff layer with parsed dimensions and resolved metadata."""
    url: str = ""
    map_code: str = ""
    source: str = "gaez"
    local_path: str = ""

    # GAEZ dimensions (None when not applicable)
    crop_code: Optional[str] = None
    period: Optional[str] = None
    climate_model: Optional[str] = None
    ssp: Optional[str] = None
    input_level: Optional[str] = None
    water_content: Optional[str] = None
    water_supply: Optional[str] = None
    management: Optional[str] = None
    sq_factor: Optional[str] = None
    lc_class: Optional[str] = None

    # Resolved metadata (populated by enrich())
    metadata: dict = field(default_factory=dict)

    @property
    def family(self) -> str:
        if self.map_code.startswith("RES01"):
            return "RES01"
        if self.map_code.startswith("RES02"):
            return "RES02"
        if self.map_code.startswith("RES05"):
            return "RES05"
        if self.map_code.startswith("RES06"):
            return "RES06"
        if self.map_code in ("SQX", "SQ-IDX"):
            return "soil_quality"
        if self.map_code == "LR-LCC":
            return "land_cover"
        return "static"

    @property
    def filename(self) -> str:
        return self.url.rsplit("/", 1)[-1]

    def validate(self) -> list[str]:
        """Check that dimension codes are recognized."""
        issues = []
        if self.map_code not in METADATA_TEMPLATES and self.map_code != "LR-LCC":
            issues.append(f"Unknown map_code: {self.map_code}")
        if self.period and self.period not in PERIODS:
            issues.append(f"Unknown period: {self.period}")
        if self.ssp and self.ssp not in SSP_SCENARIOS:
            issues.append(f"Unknown SSP: {self.ssp}")
        if self.climate_model and self.climate_model not in CLIMATE_MODELS:
            issues.append(f"Unknown climate model: {self.climate_model}")
        if self.input_level and self.input_level not in INPUT_LEVELS:
            issues.append(f"Unknown input level: {self.input_level}")
        if self.period and self.period.startswith("FP") and self.ssp == "HIST":
            issues.append(f"Future period {self.period} with HIST SSP")
        if self.period and self.period.startswith("HP") and self.ssp and self.ssp != "HIST":
            issues.append(f"Historical period {self.period} with {self.ssp}")
        return issues

    def to_dict(self) -> dict:
        raw = asdict(self)
        return {k: v for k, v in raw.items() if v is not None and v != {}}

    def save_json(self, output_folder: str = ".") -> None:
        path = os.path.join(output_folder, self.filename + ".json")
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_json(cls, path: str) -> TiffLayer:
        with open(path) as f:
            data = json.load(f)
        return cls(**data)


# ──────────────────────────────────────────────────────────────────────
# Parser
# ──────────────────────────────────────────────────────────────────────

def parse_url(url: str) -> TiffLayer:
    """Parse a GAEZ tiff URL into a TiffLayer."""
    filename = url.rsplit("/", 1)[-1]
    dims = filename.replace(".tif", "").split(".")
    map_code = dims[1]
    n = len(dims)

    if map_code.startswith(("RES02", "RES05")) and n == 7:
        return TiffLayer(url=url, map_code=map_code,
                         period=dims[2], climate_model=dims[3], ssp=dims[4],
                         crop_code=dims[5], input_level=dims[6])
    if map_code.startswith("RES01") and n == 5:
        return TiffLayer(url=url, map_code=map_code,
                         period=dims[2], climate_model=dims[3], ssp=dims[4])
    if map_code == "SQ-IDX" and n == 3:
        return TiffLayer(url=url, map_code=map_code, management=dims[2])
    if map_code == "SQX" and n == 4:
        return TiffLayer(url=url, map_code=map_code,
                         sq_factor=dims[2], management=dims[3])
    if map_code.startswith("RES06") and n == 4:
        return TiffLayer(url=url, map_code=map_code,
                         crop_code=dims[2], water_supply=dims[3])
    if map_code == "LR-LCC" and n == 3:
        return TiffLayer(url=url, map_code=map_code, lc_class=dims[2])
    if n == 2:
        return TiffLayer(url=url, map_code=map_code)

    raise ValueError(
        f"Unrecognized GAEZ filename pattern: {filename!r} "
        f"(map_code={map_code!r}, {n} dims)"
    )


# ──────────────────────────────────────────────────────────────────────
# Enrichment
# ──────────────────────────────────────────────────────────────────────

def _lookup(registry: dict, key: str) -> Optional[dict]:
    val = registry.get(key)
    if val is None or isinstance(val, str):
        return None
    return val


def _resolve_crop(code: str, family: str) -> Optional[dict]:
    source = family
    for crop_key, crop in CROP_REGISTRY.items():
        codes = crop.get("codes", {})
        if codes.get(source) == code:
            return {"key": crop_key, "caption": crop.get("caption"), "source": source}
        for st_key, st in crop.get("subtypes", {}).items():
            if st.get("codes", {}).get(source) == code:
                return {
                    "key": crop_key, "subtype": st_key,
                    "caption": st.get("description", crop.get("caption")),
                    "source": source,
                }

    for group_key, group in CROP_AGGREGATE_GROUPS.items():
        if group.get("codes", {}).get(source) == code:
            return {"key": group_key, "caption": group.get("description"),
                    "source": source, "is_aggregate": True}

    return {"key": code, "caption": None, "source": source, "unresolved": True}


def enrich(layer: TiffLayer) -> TiffLayer:
    """Resolve all dimension codes to full metadata."""
    meta = {}

    template = METADATA_TEMPLATES.get(layer.map_code)
    if template:
        meta["layer"] = {
            "map_code": layer.map_code,
            "title": template.get("title"),
            "description": template.get("description"),
            "unit": template.get("unit"),
            "nodata": template.get("nodata"),
            "scale_factor": template.get("scale_factor"),
            "resolution": template.get("resolution"),
            "category": template.get("category"),
            "dimension_profile": template.get("dimension_profile"),
            "license": LICENSE,
        }
        if "range" in template:
            meta["layer"]["range"] = template["range"]
        if "classes" in template:
            meta["layer"]["classes"] = template["classes"]
        if "classes_ref" in template:
            meta["layer"]["classes"] = {
                k: v for k, v in SOIL_QUALITIES.items() if not k.startswith("_")
            }
        if "note" in template:
            meta["layer"]["note"] = template["note"]
        if "reference_year" in template:
            meta["layer"]["reference_year"] = template["reference_year"]
            meta["layer"]["statistics_source"] = template.get("statistics_source")

        cat = template.get("category")
        if cat and cat in DATASET_CATEGORIES:
            meta["category"] = {"name": cat, "description": DATASET_CATEGORIES[cat]}
    else:
        meta["layer"] = {"map_code": layer.map_code, "unresolved": True}

    if layer.crop_code:
        meta["crop"] = _resolve_crop(layer.crop_code, layer.family)
    if layer.period:
        p = _lookup(PERIODS, layer.period)
        meta["period"] = {"code": layer.period, **(p if p else {"unresolved": True})}
    if layer.climate_model:
        c = _lookup(CLIMATE_MODELS, layer.climate_model)
        meta["climate_model"] = {"code": layer.climate_model, **(c if c else {"unresolved": True})}
    if layer.ssp:
        s = _lookup(SSP_SCENARIOS, layer.ssp)
        meta["ssp"] = {"code": layer.ssp, **(s if s else {"unresolved": True})}
    if layer.input_level:
        il = _lookup(INPUT_LEVELS, layer.input_level)
        meta["input_level"] = {"code": layer.input_level, **(il if il else {"unresolved": True})}
    if layer.water_content:
        wc = _lookup(WATER_CONTENT, layer.water_content)
        meta["water_content"] = {"code": layer.water_content, **(wc if wc else {"unresolved": True})}
    if layer.water_supply:
        ws = _lookup(WATER_SUPPLY, layer.water_supply)
        meta["water_supply"] = {"code": layer.water_supply, **(ws if ws else {"unresolved": True})}
    if layer.sq_factor:
        sq = _lookup(SOIL_QUALITIES, layer.sq_factor)
        meta["sq_factor"] = {"code": layer.sq_factor, **(sq if sq else {"unresolved": True})}
    if layer.management:
        ml = _lookup(MANAGEMENT_LEVELS, layer.management)
        meta["management"] = {"code": layer.management, **(ml if ml else {"unresolved": True})}
    if layer.lc_class:
        lc = _lookup(LAND_COVER_CLASSES, layer.lc_class)
        meta["lc_class"] = {"code": layer.lc_class, **(lc if lc else {"unresolved": True})}

    layer.metadata = meta
    return layer


# ──────────────────────────────────────────────────────────────────────
# Convenience
# ──────────────────────────────────────────────────────────────────────

def from_url(url: str) -> TiffLayer:
    """Parse a URL and enrich with full metadata in one step."""
    layer = parse_url(url)
    return enrich(layer)