"""Utility script for writing adjusted values back into raster layers during experiments."""
import numpy as np
import rasterio
from rasterio.transform import rowcol
from scipy.ndimage import distance_transform_edt
from enum import Enum
"""
The class works in 5 sequential steps. Here is exactly what happens when you call `editor.apply()`:

---

### Step 1 — Load the raster on init

```python
editor = RasterEditor("input.tif", radius_km=10, decay=DecayFunction.GAUSSIAN)
```

When the object is created, the entire GeoTIFF is read into memory as a NumPy array of shape `(bands, rows, cols)`. The metadata (projection, transform, nodata, dtype) is stored separately so it can be reattached when saving.

---

### Step 2 — Convert coordinates to a pixel

```python
row, col = self._coords_to_pixel(longitude, latitude)
```

The raster has a **transform** — a mathematical mapping that converts geographic coordinates (longitude, latitude) into pixel positions (row, col). `rasterio.transform.rowcol()` does this conversion. If the coordinate falls outside the raster extent it raises an error immediately.

```
(36.82, 1.28)  →  transform  →  (row=412, col=278)
```

---

### Step 3 — Build the influence kernel

```python
kernel = self._build_kernel(row, col)
```

This creates a 2D array the **same size as the raster**, where each cell holds a weight between 0 and 1 representing how much influence the centre pixel has on that location.

It works in three sub-steps:

**a) Compute Euclidean distance from centre to every pixel**

```python
mask = np.ones((n_rows, n_cols))
mask[centre_row, centre_col] = 0          # only the centre is 0
dist = distance_transform_edt(mask)       # distance in pixels from centre
```

`distance_transform_edt` finds the Euclidean distance from every pixel to the nearest zero — which is just the centre. Result: a 2D array of distances in pixels.

**b) Apply the decay function**

```
Gaussian:     weight = exp(-0.5 * (dist / σ)²)     σ = radius/3
Linear:       weight = 1 - dist/radius
Exponential:  weight = exp(-3 * dist/radius)
```

All three give **weight = 1.0 at the centre** and **weight ≈ 0 at the radius boundary**. Pixels beyond the radius are forced to 0.

**c) Result — the kernel looks like this conceptually:**

```
0   0   0   0   0   0   0
0   0  .1  .3  .1   0   0
0  .1  .5  .8  .5  .1   0
0  .3  .8  1.0 .8  .3   0    ← centre pixel = 1.0
0  .1  .5  .8  .5  .1   0
0   0  .1  .3  .1   0   0
0   0   0   0   0   0   0
```

---

### Step 4 — Apply the weighted value to the band

```python
self._apply_kernel(band_idx, row, col, value, kernel)
```

The value you passed (e.g. `850.0`) is multiplied by the kernel:

```python
weighted_value = kernel * value
# centre pixel  → 1.0 * 850 = 850.0
# nearby pixel  → 0.8 * 850 = 680.0
# farther pixel → 0.3 * 850 = 255.0
# edge pixel    → 0.1 * 850 =  85.0
```

Then depending on mode:

```python
# OVERWRITE
band[influence] = weighted_value[influence]

# ADDITIVE
band[influence] += weighted_value[influence]
```

Nodata pixels are excluded from the influence mask so their values are never touched.

---

### Step 5 — Save (optional)

```python
editor.save("output.tif")
```

Writes the modified in-memory array back to a new GeoTIFF using the original metadata — same projection, same transform, same dtype, same nodata value. The original file is never touched.

---

### Full flow in one picture

```
input.tif
    │
    ▼
[Load into memory]  →  data(bands, rows, cols) + metadata
    │
    ▼
[coords → pixel]    →  (lon, lat)  →  (row=412, col=278)
    │
    ▼
[build kernel]      →  2D weight array, 1.0 at centre, 0.0 at radius
    │
    ▼
[apply value]       →  weighted_value = kernel × 850.0
                        OVERWRITE: band[pixel] = weighted_value
                        ADDITIVE:  band[pixel] += weighted_value
    │
    ▼
[save]              →  output.tif  (same projection, same metadata)
```

"""

class UpdateMode(Enum):
    OVERWRITE = "overwrite"
    ADDITIVE  = "additive"


class DecayFunction(Enum):
    LINEAR      = "linear"
    GAUSSIAN    = "gaussian"
    EXPONENTIAL = "exponential"


class RasterEditor:
    """
    Modifies raster data in a GeoTIFF file at a given geographic location,
    applying a spatially decaying influence within a defined radius.

    Parameters
    ----------
    filepath : str
        Path to the input GeoTIFF file.
    radius_km : float
        Influence radius in kilometres. Assumes 1 pixel = 1 km.
        Default is 10 km (10 pixels).
    decay : DecayFunction
        Decay function to use for spatial influence.
        Options: LINEAR, GAUSSIAN, EXPONENTIAL.
    mode : UpdateMode
        OVERWRITE replaces pixel values; ADDITIVE adds to existing values.
    """

    def __init__(
        self,
        filepath: str,
        radius_km: float       = 10.0,
        decay: DecayFunction   = DecayFunction.GAUSSIAN,
        mode: UpdateMode       = UpdateMode.OVERWRITE,
    ):
        self.filepath  = filepath
        self.radius_px = radius_km          # 1 pixel = 1 km
        self.decay     = decay
        self.mode      = mode

        # Load raster into memory
        with rasterio.open(filepath) as src:
            self.data      = src.read()           # shape: (bands, rows, cols)
            self.meta      = src.meta.copy()
            self.transform = src.transform
            self.nodata    = src.nodata
            self.crs       = src.crs

        self.n_bands, self.n_rows, self.n_cols = self.data.shape

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply(
        self,
        longitude : float,
        latitude  : float,
        value     : float,
        band      : int = 1,
        output_path: str | None = None,
    ) -> np.ndarray:
        """
        Apply a value at the pixel corresponding to (longitude, latitude)
        with spatial decay to surrounding pixels within the radius.

        Parameters
        ----------
        longitude : float
            X coordinate in the raster's CRS (or WGS84 longitude).
        latitude : float
            Y coordinate in the raster's CRS (or WGS84 latitude).
        value : float
            The value to apply at the centre pixel.
        band : int
            1-based band index to modify. Default is 1.
        output_path : str, optional
            If provided, saves the modified raster to this path.
            If None, modifies in-memory only.

        Returns
        -------
        np.ndarray
            The modified band array (2D).
        """
        # Validate band
        if band < 1 or band > self.n_bands:
            raise ValueError(f"Band {band} out of range (1–{self.n_bands}).")

        # Locate centre pixel
        row, col = self._coords_to_pixel(longitude, latitude)

        # Build influence kernel
        kernel = self._build_kernel(row, col)

        # Apply update to band (0-indexed internally)
        band_idx = band - 1
        self._apply_kernel(band_idx, row, col, value, kernel)

        # Optionally save
        if output_path:
            self.save(output_path)

        return self.data[band_idx]

    def save(self, output_path: str) -> None:
        """
        Write the current (possibly modified) raster to a new GeoTIFF,
        preserving original metadata and projection.

        Parameters
        ----------
        output_path : str
            Destination file path.
        """
        with rasterio.open(output_path, "w", **self.meta) as dst:
            dst.write(self.data)
        print(f"Saved modified raster → {output_path}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _coords_to_pixel(self, longitude: float, latitude: float) -> tuple[int, int]:
        """
        Convert geographic coordinates to (row, col) pixel indices.
        Raises ValueError if the coordinate falls outside the raster extent.
        """
        row, col = rowcol(self.transform, longitude, latitude)
        row, col = int(row), int(col)

        if not (0 <= row < self.n_rows and 0 <= col < self.n_cols):
            raise ValueError(
                f"Coordinates ({longitude}, {latitude}) map to pixel "
                f"({row}, {col}) which is outside the raster extent "
                f"({self.n_rows} rows × {self.n_cols} cols)."
            )
        return row, col

    def _build_kernel(self, centre_row: int, centre_col: int) -> np.ndarray:
        """
        Build a 2D influence kernel (same size as the raster) centred at
        (centre_row, centre_col). Values range from 1.0 at the centre
        to 0.0 at and beyond the radius.

        Returns
        -------
        np.ndarray
            2D array of influence weights, shape (n_rows, n_cols).
        """
        # Distance from centre pixel for every pixel in the raster
        # Uses a binary mask: centre = 0, rest = 1 → distance_transform_edt
        # gives Euclidean distance in pixels from the centre.
        mask = np.ones((self.n_rows, self.n_cols), dtype=np.uint8)
        mask[centre_row, centre_col] = 0
        dist = distance_transform_edt(mask)          # Euclidean distance (px)

        # Normalised distance: 0 at centre, 1 at radius boundary
        d_norm = np.clip(dist / self.radius_px, 0.0, 1.0)

        # Apply decay function
        if self.decay == DecayFunction.LINEAR:
            # w = 1 - d/R   (1 at centre, 0 at radius)
            kernel = 1.0 - d_norm

        elif self.decay == DecayFunction.GAUSSIAN:
            # w = exp(-0.5 * (d/σ)²)  with σ = radius/3 so ≈0 at boundary
            sigma  = self.radius_px / 3.0
            kernel = np.exp(-0.5 * (dist / sigma) ** 2)
            # Zero out pixels beyond radius
            kernel[dist > self.radius_px] = 0.0

        elif self.decay == DecayFunction.EXPONENTIAL:
            # w = exp(-λ * d/R)  with λ=3 so ≈0.05 at boundary
            lam    = 3.0
            kernel = np.exp(-lam * d_norm)
            kernel[dist > self.radius_px] = 0.0

        else:
            raise ValueError(f"Unknown decay function: {self.decay}")

        # Centre always gets full weight = 1.0
        kernel[centre_row, centre_col] = 1.0

        return kernel

    def _apply_kernel(
        self,
        band_idx  : int,
        centre_row: int,
        centre_col: int,
        value     : float,
        kernel    : np.ndarray,
    ) -> None:
        """
        Apply the weighted value to the raster band using the chosen mode,
        respecting nodata pixels and raster bounds.
        """
        band_data = self.data[band_idx].astype(np.float64)

        # Influence mask: only pixels with non-zero kernel weight
        influence = kernel > 0.0

        # Respect nodata: do not modify nodata pixels
        if self.nodata is not None:
            valid = band_data != self.nodata
            influence = influence & valid

        weighted_value = kernel * value

        if self.mode == UpdateMode.OVERWRITE:
            band_data[influence] = weighted_value[influence]

        elif self.mode == UpdateMode.ADDITIVE:
            band_data[influence] += weighted_value[influence]

        # Write back, preserving dtype
        self.data[band_idx] = band_data.astype(self.meta["dtype"])


# =============================================================================
# Example usage
# =============================================================================
if __name__ == "__main__":

    # --- Overwrite with Gaussian decay ---
    editor = RasterEditor(
        filepath  = "input.tif",
        radius_km = 10.0,
        decay     = DecayFunction.GAUSSIAN,
        mode      = UpdateMode.OVERWRITE,
    )

    modified_band = editor.apply(
        longitude    = 36.82,       # x coordinate
        latitude     = 1.28,        # y coordinate
        value        = 850.0,       # value to apply at centre
        band         = 1,
        output_path  = "output_gaussian.tif",
    )

    # --- Additive with linear decay, no file save ---
    editor2 = RasterEditor(
        filepath  = "input.tif",
        radius_km = 10.0,
        decay     = DecayFunction.LINEAR,
        mode      = UpdateMode.ADDITIVE,
    )

    editor2.apply(longitude=36.82, latitude=1.28, value=100.0, band=1)
    editor2.save("output_additive_linear.tif")
