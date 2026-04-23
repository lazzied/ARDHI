from abc import ABC, abstractmethod
from typing import Any, Dict, List

from engines.report_augmentation.models_and_io import AugmentedLayer, FarmerReport, HWSDLayer, HWSDRepository


class AttributeStrategy(ABC):
    @abstractmethod
    def compute(
        self, attr: str, report: FarmerReport,
        hwsd: HWSDLayer, repo: HWSDRepository, context: Dict[str, Any],
    ) -> tuple[Any, str]:
        """Returns (value, provenance_flag)."""


class ReadStrategy(AttributeStrategy):
    """Farmer report → direct read with OC cross-check."""
    _MAP = {
        "OC":  ("Taux de carbone",        lambda v: round(v, 4)),
        "pH":  ("pH",                      lambda v: v),
        "EC":  ("Conductivité",            lambda v: round(v, 4)),
        "CCB": ("Carbonates de Calcium",   lambda v: round(v, 4)),
    }

    def compute(self, attr, report, hwsd, repo, context):
        if attr not in self._MAP:
            return None, f"READ: no mapping for {attr}"
        key, fn = self._MAP[attr]
        val  = fn(report.raw[key])
        note = f"READ | farmer {key}={val}"
        if attr == "OC":
            oc_mo = round(report.organic_matter / 1.724, 4)
            dev   = abs(val - oc_mo) / max(oc_mo, 1e-9) * 100
            note += f" | cross-check: MO/1.724={oc_mo}%"
            if dev > 15:
                note += f" ⚠ deviation={dev:.1f}% >15%"
        return val, note


class AugStrategy(AttributeStrategy):
    """HWSD fetch with lookup table decoding."""

    def compute(self, attr, report, hwsd, repo, context):
        if attr == "TXT":
            raw = hwsd.texture_usda
            dec = repo.decode_texture_usda(raw)
            return dec, f"AUG | HWSD TEXTURE_USDA={raw} → {dec}; SOTER={hwsd.texture_soter}"
        if attr == "RSD":
            raw = hwsd.root_depth
            dec = repo.decode_root_depth(raw)
            return dec, f"AUG | HWSD ROOT_DEPTH class={raw} → {dec}"
        if attr == "DRG":
            raw = hwsd.drainage
            dec = repo.decode_drainage(raw)
            return dec, f"AUG | HWSD DRAINAGE={raw} → {dec}"
        if attr == "GYP":
            return round(hwsd.gypsum or 0, 4), f"AUG | HWSD GYPSUM={hwsd.gypsum} % wt"
        if attr == "CF":
            return hwsd.coarse, f"AUG | HWSD COARSE={hwsd.coarse} % vol"
        return None, f"AUG: no handler for {attr}"


class CalcStrategy(AttributeStrategy):
    """Scientifically grounded derivations from farmer + HWSD data."""

    def compute(self, attr, report, hwsd, repo, context):

        if attr == "TEB":
            ca = (report.Ca_exch / 40.08) * 2 * 10   # Ca²⁺, atomic mass 40.08
            mg = (report.Mg_exch / 24.31) * 2 * 10   # Mg²⁺, atomic mass 24.31
            k  = (report.K_exch  / 39.10) * 1 * 10   # K⁺,   atomic mass 39.10
            na = (report.Na_exch  / 22.99) * 1 * 10  # Na⁺,  atomic mass 22.99
            teb_farmer = round(ca + mg + k + na, 3)
            teb_hwsd   = hwsd.teb

            note = (
                f"CALC | farmer TEB={teb_farmer} cmolc/kg "
                f"(Ca={ca:.3f}+Mg={mg:.3f}+K={k:.3f}+Na={na:.3f}); "
                f"HWSD TEB={teb_hwsd} cmolc/kg | ISO 11260:2018"
            )
            if teb_hwsd and abs(teb_farmer - teb_hwsd) / max(teb_hwsd, 1e-9) > 0.5:
                note += (
                    " | ⚠ discrepancy >50% — farmer cations may include total "
                    "(not only exchangeable) fractions. Using HWSD TEB as reference."
                )
                teb_use = teb_hwsd
            else:
                teb_use = teb_farmer

            context["TEB"]        = teb_use
            context["TEB_farmer"] = teb_farmer
            context["TEB_hwsd"]   = teb_hwsd
            return teb_use, note

        if attr == "CECsoil":
            clay = hwsd.clay or 20.0
            oc   = report.OC
            cec  = round(0.57 * clay + 3.58 * oc, 3)
            context["CECsoil"] = cec
            note = (f"CALC | Bell&VanKeulen(1995): 0.57×{clay}+3.58×{oc}={cec} cmolc/kg ...")
            hwsd_cec = hwsd.cec_soil
            if hwsd_cec and abs(cec - hwsd_cec) / max(hwsd_cec, 1e-9) > 0.30:
                note += (f" | ⚠ HWSD CEC_SOIL={hwsd_cec} cmolc/kg, divergence=...% >30%")
            return cec, note

        if attr == "CECclay":
            cec_s = context.get("CECsoil") or 0
            oc    = report.OC
            clay  = (hwsd.clay or 20.0) / 100.0
            if clay > 0:
                om_frac = (oc * 1.724) / 100.0   # Van Bemmelen: OC -> OM fraction
                cec_c = round((cec_s - om_frac * 200.0) / clay, 3)
                note  = (
                    f"CALC | FAO HWSD §4: ({cec_s}−({oc}/100)×200)/{clay:.2f}"
                    f"={cec_c} cmolc/kg | FAO Soils Bulletin 52"
                )
            else:
                cec_c = None
                note  = "CALC | clay=0, CEC_clay undefined"
            context["CECclay"] = cec_c
            return cec_c, note

        if attr == "BS":
            teb  = context.get("TEB") or 0
            cecs = context.get("CECsoil") or 1
            bs_raw = 100.0 * teb / cecs
            bs     = round(min(bs_raw, 100.0), 2)
            note   = (
                f"CALC | BS=100×TEB({teb})/CECsoil({cecs})={bs}%"
                f" | Sys et al. (1991)"
            )
            if bs_raw > 100:
                note += f" | ⚠ raw={bs_raw:.1f}% capped at 100% (fully saturated)"
            return bs, note

        if attr == "ESP":
            na_cmolc = (report.Na_exch / 22.99) * 1 * 10
            cecs     = context.get("CECsoil") or 1
            esp      = round(min(100.0 * na_cmolc / cecs, 100.0), 2)
            return esp, (
                f"CALC | ESP=100×Na_cmolc({na_cmolc:.4f})/CECsoil({cecs})"
                f"={esp}% | Note: strategy upgraded from READ→CALC (unit conversion required)"
            )

        if attr == "OSD":
            oc = report.OC
            if   oc < 0.6:   cls, code = "Very low",  0
            elif oc < 1.25:  cls, code = "Low",        1
            elif oc < 2.5:   cls, code = "Medium",     2
            elif oc < 6.0:   cls, code = "High",       3
            else:             cls, code = "Very high", 4
            return code, (
                f"CALC | OSD={cls}(code={code}) from OC={oc}% "
                f"| FAO Soil Description 4th ed. (2006) Annex 2"
            )

        if attr == "SPR":
            oc  = report.OC
            bd  = round(100.0 / (oc / 0.244 + (100.0 - oc) / 1.64), 3)
            txt = int(hwsd.texture_usda or 9)
            if txt in {1, 2, 3}:          critical_bd = 1.40
            elif txt in {12, 13}:          critical_bd = 1.80
            else:                          critical_bd = 1.65
            spr = 0 if bd < critical_bd else 1
            context["SPR"] = spr
            """
            note = (f"CALC | BD={bd} g/cm³ ...")
            if oc < 2.0:
                note += (f" | warning: OC={oc}% <2%, Adams(1973) extrapolated beyond calibration range for mineral soils")
            return spr, note
                    
            """
            return spr, (
                f"CALC | BD={bd} g/cm³ (Adams 1973; OC={oc}%), "
                f"critical={critical_bd} g/cm³ (TXT_USDA={txt}), SPR={spr} "
                f"| Arshad et al. (1996) SSSA Spec. Pub. 49"
            )

        if attr == "SPH":
            ph1 = repo.decode_phase(hwsd.phase1)
            ph2 = repo.decode_phase(hwsd.phase2)
            HARD     = {"Petric","Petrocalcic","Petrogypsic","Duripan","Fragipan","Placic","Lithic"}
            SKELETIC = {"Skeletic"}
            active   = {ph1, ph2} - {"None"}

            if any(p in HARD     for p in active): sph, label = 1, "hard phase detected"
            elif any(p in SKELETIC for p in active): sph, label = 2, "Skeletic"
            elif report.CCB > 40:                   sph, label = 1, "CaCO3>40% → petrocalcic risk"
            elif report.EC  > 15:                   sph, label = 1, "EC>15 dS/m → salic"
            else:                                   sph, label = 0, "no limitation"
            return sph, (
                f"CALC | PHASE1={ph1}, PHASE2={ph2}, CaCO3={report.CCB}%, "
                f"EC={report.EC} dS/m → SPH={sph} ({label}) "
                f"| Sys et al. (1991); FAO Soils Bulletin 55"
            )

        if attr == "VSP":
            oc   = report.OC
            silt = hwsd.silt or 40.0
            clay = hwsd.clay or 20.0
            OM   = oc * 1.724
            M    = silt * (100.0 - clay)
            s, p = 2, 3
            K    = round((2.1e-4 * (M ** 1.14) * (12.0 - OM) + 3.25 * (s - 2) + 2.5 * (p - 3)) / 100.0, 4)
            vsp  = 0 if K < 0.04 else 1
            return vsp, (
                f"CALC | K={K} (Wischmeier&Smith 1978; M={M:.0f}, OM={OM:.2f}%), "
                f"VSP={vsp} | ⚠ slope unavailable — K-factor only (no LS term)"
            )

        if attr == "GSP":
            ph1 = repo.decode_phase(hwsd.phase1)
            ph2 = repo.decode_phase(hwsd.phase2)
            COARSE_PHASES = {"Skeletic", "Lithic", "Stony", "Gravelly", "Bouldery", "Petroferric"}
            active = {ph1, ph2} - {"None"}
            gsp = 1 if any(p in COARSE_PHASES for p in active) else 0
            return gsp, (f"CALC | PHASE1={ph1}, PHASE2={ph2} -> GSP={gsp} | ...")

        return None, f"CALC: no handler for {attr}"
    
ATTRIBUTE_ORDER: List[tuple[str, AttributeStrategy]] = [
    ("OC",      ReadStrategy()),
    ("pH",      ReadStrategy()),
    ("EC",      ReadStrategy()),
    ("CCB",     ReadStrategy()),
    ("TXT",     AugStrategy()),
    ("RSD",     AugStrategy()),
    ("DRG",     AugStrategy()),
    ("GYP",     AugStrategy()),
    ("CF",     AugStrategy()),
    ("TEB",     CalcStrategy()),
    ("CECsoil", CalcStrategy()),
    ("CECclay", CalcStrategy()),
    ("BS",      CalcStrategy()),
    ("ESP",     CalcStrategy()),
    ("OSD",     CalcStrategy()),
    ("SPR",     CalcStrategy()),
    ("SPH",     CalcStrategy()),
    ("GSP",     CalcStrategy()),
    ("VSP",     CalcStrategy()),
]


class AttributeProcessor:
    def __init__(self, repo: HWSDRepository):
        self._repo = repo

    def process(
        self, report: FarmerReport, hwsd: HWSDLayer,
    ) -> tuple[Dict[str, Any], Dict[str, str]]:
        values:  Dict[str, Any] = {}
        flags:   Dict[str, str] = {}
        context: Dict[str, Any] = {}

        for attr, strategy in ATTRIBUTE_ORDER:
            val, flag = strategy.compute(attr, report, hwsd, self._repo, context)
            values[attr]  = val
            flags[attr]   = flag
            context[attr] = val

        return values, flags


# ===========================================================================
# V — LAYER INTERPOLATOR  (SRP)
# ===========================================================================

class LayerInterpolator:
    CATEGORICAL = {"TXT", "DRG", "RSD", "OSD", "SPR", "SPH", "VSP", "CF", "GSP"}

    def interpolate(
        self, d1: AugmentedLayer, d2_hwsd: AugmentedLayer,
    ) -> AugmentedLayer:
        values: Dict[str, Any] = {}
        flags:  Dict[str, str] = {}

        for attr in d1.values:
            v1 = d1.values.get(attr)
            v2 = d2_hwsd.values.get(attr)

            if attr in self.CATEGORICAL:
                values[attr] = v2
                flags[attr]  = f"INTERP | categorical → HWSD D2 ({v2})"
            elif v1 is not None and v2 is not None:
                try:
                    iv = round(0.5 * float(v1) + 0.5 * float(v2), 4)
                    values[attr] = iv
                    flags[attr]  = f"INTERP | 0.5×D1({v1}) + 0.5×D2({v2}) = {iv}"
                except (TypeError, ValueError):
                    values[attr] = v2
                    flags[attr]  = f"INTERP | non-numeric → HWSD D2 ({v2})"
            elif v2 is not None:
                values[attr] = v2
                flags[attr]  = f"INTERP | D1 missing → HWSD D2 ({v2})"
            else:
                values[attr] = v1
                flags[attr]  = f"INTERP | D2 missing → D1 enriched ({v1})"

        return AugmentedLayer("D2", d2_hwsd.top_dep, d2_hwsd.bot_dep, values, flags, d2_hwsd.smu_id)