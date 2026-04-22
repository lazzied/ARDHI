from dataclasses import dataclass, field
from dbm import sqlite3
import json
from typing import Any, Dict, List, Optional


@dataclass
class FarmerReport:
    pH:              float
    EC:              float    # mS/cm = dS/m
    salinity:        float    # %
    moisture:        float    # %
    dry_matter:      float    # %
    organic_matter:  float    # % (MO — Rodier)
    total_N:         float    # %
    CN_ratio:        float
    sulfur:          float    # %
    OC:              float    # % (Taux de carbone)
    CCB:             float    # % (Carbonates de calcium)
    Ca_exch:         float    # g/kg DM
    Mg_exch:         float    # g/kg DM
    K_exch:          float    # g/kg DM
    P_exch:          float    # g/kg DM
    Na_exch:         float    # g/kg DM
    active_lime:     float    # %
    raw: Dict[str, float] = field(default_factory=dict)


@dataclass
class HWSDLayer:
    layer:         str
    top_dep:       int
    bot_dep:       int
    clay:          Optional[float]
    sand:          Optional[float]
    silt:          Optional[float]
    texture_usda:  Optional[float]
    texture_soter: Optional[str]
    org_carbon:    Optional[float]
    ph_water:      Optional[float]
    teb:           Optional[float]
    bsat:          Optional[float]
    cec_soil:      Optional[float]
    cec_clay:      Optional[float]
    esp:           Optional[float]
    elec_cond:     Optional[float]
    tcarbon_eq:    Optional[float]
    gypsum:        Optional[float]
    coarse:        Optional[float]
    root_depth:    Optional[float]
    drainage:      Optional[str]
    phase1:        Optional[float]
    phase2:        Optional[float]
    bulk:          Optional[float]


@dataclass
class AugmentedLayer:
    layer:    str
    top_dep:  int
    bot_dep:  int
    values:   Dict[str, Any]
    flags:    Dict[str, str]
    
    
class FarmerReportParser:
    def parse(self, path: str) -> FarmerReport:
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
        raw = {item["attribute"]: item["value"] for item in items}
        return FarmerReport(
            pH             = raw["pH"],
            EC             = raw["Conductivité"],
            salinity       = raw["Salinité"],
            moisture       = raw["Humidité"],
            dry_matter     = raw["Matière sèche"],
            organic_matter = raw["Matière Organique"],
            total_N        = raw["Azote total"],
            CN_ratio       = raw["Rapport C/N"],
            sulfur         = raw["Souffre"],
            OC             = raw["Taux de carbone"],
            CCB            = raw["Carbonates de Calcium"],
            Ca_exch        = raw["Calcium échangeable"],
            Mg_exch        = raw["Magnésium échangeable"],
            K_exch         = raw["Potassium échangeable"],
            P_exch         = raw["Phosphore échangeable"],
            Na_exch        = raw["Sodium échangeable"],
            active_lime    = raw["Calcaire actif"],
            raw            = raw,
        )


# ===========================================================================
# II — HWSD REPOSITORY
# ===========================================================================

class HWSDRepository:
    def __init__(self, db_path: str):
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def get_all_layers(self, smu_id: int) -> List[HWSDLayer]:
        sql = """
            SELECT LAYER, TOPDEP, BOTDEP, CLAY, SAND, SILT,
                   TEXTURE_USDA, TEXTURE_SOTER, ORG_CARBON, PH_WATER,
                   TEB, BSAT, CEC_SOIL, CEC_CLAY, ESP, ELEC_COND,
                   TCARBON_EQ, GYPSUM, COARSE, ROOT_DEPTH, DRAINAGE,
                   PHASE1, PHASE2, BULK
            FROM HWSD2_LAYERS
            WHERE HWSD2_SMU_ID = ?
            ORDER BY TOPDEP
        """
        with self._connect() as conn:
            rows = conn.execute(sql, (smu_id,)).fetchall()
        return [
            HWSDLayer(
                layer=r[0], top_dep=r[1], bot_dep=r[2],
                clay=r[3], sand=r[4], silt=r[5],
                texture_usda=r[6], texture_soter=r[7],
                org_carbon=r[8], ph_water=r[9],
                teb=r[10], bsat=r[11], cec_soil=r[12], cec_clay=r[13],
                esp=r[14], elec_cond=r[15], tcarbon_eq=r[16],
                gypsum=r[17], coarse=r[18], root_depth=r[19],
                drainage=r[20], phase1=r[21], phase2=r[22], bulk=r[23],
            )
            for r in rows
        ]

    def decode_drainage(self, code: Optional[str]) -> str:
        if not code: return "Unknown"
        with self._connect() as conn:
            row = conn.execute("SELECT VALUE FROM D_DRAINAGE WHERE CODE=?", (code,)).fetchone()
        return row[0].strip() if row else code

    def decode_texture_usda(self, code: Optional[float]) -> str:
        if code is None: return "Unknown"
        with self._connect() as conn:
            row = conn.execute("SELECT VALUE FROM D_TEXTURE_USDA WHERE CODE=?", (int(code),)).fetchone()
        return row[0].strip() if row else str(code)

    def decode_root_depth(self, code: Optional[float]) -> str:
        if code is None: return "Unknown"
        with self._connect() as conn:
            row = conn.execute("SELECT VALUE FROM D_ROOT_DEPTH WHERE CODE=?", (int(code),)).fetchone()
        return row[0].strip() if row else str(code)

    def decode_phase(self, code: Optional[float]) -> str:
        if code is None: return "None"
        with self._connect() as conn:
            row = conn.execute("SELECT VALUE FROM D_PHASE WHERE CODE=?", (int(code),)).fetchone()
        return row[0].strip() if row else "None"
