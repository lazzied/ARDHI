import numpy as np



def compute_suitability(constrained_yield, max_yield):
    """
    Compute GAEZ v5 Suitability Index (SI) and Suitability Class (SC)
    for a single pixel / single entry.

    Parameters
    ----------
    constrained_yield : float
        Yield after all constraints (PyAEZ Modules 2-5), kg/ha.
    max_yield : float
        Global maximum yield across the entire study area, kg/ha.
        Must be precomputed as np.nanmax(constrained_yield_raster)
        before calling this function.

    Returns
    -------
    ratio : float
        Yield as fraction of maximum (0.0 to 1.0)
    suitability_class_label : str
        VS / S / MS / mS / VmS / NS
    SI : float
        Normalized suitability index (0 to 10000)
    SC : int
        Aggregated suitability class (1=Very high ... 8=Not suitable)
    SC_label : str
        Human-readable label for SC
    """

    # ------------------------------------------------------------------
    # 0. Guard: handle NoData / zero max
    # ------------------------------------------------------------------
    if max_yield is None or max_yield == 0 or np.isnan(max_yield):
        return 0.0, "NS", 0.0, 8, "Not suitable"

    if constrained_yield is None or np.isnan(constrained_yield) or constrained_yield < 0:
        return 0.0, "NS", 0.0, 8, "Not suitable"

    # ------------------------------------------------------------------
    # 1. Yield ratio
    # ------------------------------------------------------------------
    ratio = constrained_yield / max_yield
    ratio = np.clip(ratio, 0.0, 1.0)

    # ------------------------------------------------------------------
    # 2. Per-pixel suitability class (VS → NS)
    #    Thresholds from GAEZ v4/v5 and PyAEZ documentation
    # ------------------------------------------------------------------
    if   ratio >= 0.80:  pixel_class = "VS"   # Very suitable
    elif ratio >= 0.60:  pixel_class = "S"    # Suitable
    elif ratio >= 0.40:  pixel_class = "MS"   # Moderately suitable
    elif ratio >= 0.20:  pixel_class = "mS"   # Marginally suitable
    elif ratio >  0.00:  pixel_class = "VmS"  # Very marginally suitable
    else:                pixel_class = "NS"   # Not suitable

    # ------------------------------------------------------------------
    # 3. Area shares (single pixel → one class gets 1.0, rest get 0.0)
    # ------------------------------------------------------------------
    shares = {"VS": 0.0, "S": 0.0, "MS": 0.0, "mS": 0.0, "VmS": 0.0, "NS": 0.0}
    shares[pixel_class] = 1.0

    # ------------------------------------------------------------------
    # 4. GAEZ v5 Suitability Index formula
    #    SI = 100 * (90*VS + 70*S + 50*MS + 30*mS + 15*VmS + 0*NS) / 0.9
    #    Range: 0 to 10000
    # ------------------------------------------------------------------
    SI = 100 * (
        90  * shares["VS"]  +
        70  * shares["S"]   +
        50  * shares["MS"]  +
        30  * shares["mS"]  +
        15  * shares["VmS"] +
         0  * shares["NS"]
    ) / 0.9

    # ------------------------------------------------------------------
    # 5. Aggregated Suitability Class (1–8) from SI
    #    GAEZ v5 thresholds
    # ------------------------------------------------------------------
    if   SI >  8500:  SC = 1; SC_label = "Very high"
    elif SI >  7000:  SC = 2; SC_label = "High"
    elif SI >  5500:  SC = 3; SC_label = "Good"
    elif SI >  4000:  SC = 4; SC_label = "Medium"
    elif SI >  2500:  SC = 5; SC_label = "Moderate"
    elif SI >  1000:  SC = 6; SC_label = "Marginal"
    elif SI >     0:  SC = 7; SC_label = "Very marginal"
    else:             SC = 8; SC_label = "Not suitable"

    return ratio, pixel_class, round(SI, 2), SC, SC_label


# ----------------------------------------------------------------------
# Convenience lookup (no division needed — result is deterministic
# per pixel class once you know which class the pixel falls in)
# ----------------------------------------------------------------------
PIXEL_CLASS_TO_SI = {
    "VS":  round(100 * 90  / 0.9, 2),   # 10000.0
    "S":   round(100 * 70  / 0.9, 2),   # 7777.78
    "MS":  round(100 * 50  / 0.9, 2),   # 5555.56
    "mS":  round(100 * 30  / 0.9, 2),   # 3333.33
    "VmS": round(100 * 15  / 0.9, 2),   # 1666.67
    "NS":  0.0,
}


# ----------------------------------------------------------------------
# Example usage
# ----------------------------------------------------------------------
if __name__ == "__main__":

    # Precompute max_yield once from your full raster
    constrained_yield_raster = np.array([0, 500, 1200, 2400, 3200, 4100, 5500, np.nan])
    max_yield = float(np.nanmax(constrained_yield_raster))

    print(f"Global max yield: {max_yield} kg/ha\n")
    print(f"{'Yield':>8}  {'Ratio':>6}  {'Class':>4}  {'SI':>8}  {'SC':>2}  SC Label")
    print("-" * 60)

    test_yields = [np.nan, 0, 500, 1200, 2400, 3200, 4100, 5500]

    for y in test_yields:
        ratio, pixel_class, SI, SC, SC_label = compute_suitability(y, max_yield)
        y_str = "NaN" if (y is None or (isinstance(y, float) and np.isnan(y))) else str(y)
        print(f"{y_str:>8}  {ratio:>6.3f}  {pixel_class:>4}  {SI:>8.2f}  {SC:>2}  {SC_label}")