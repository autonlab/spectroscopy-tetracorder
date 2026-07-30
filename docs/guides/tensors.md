# Tensors & metadata

`analyze()` has one shape rule: there is one shared spectral axis, and every
other axis describes samples. It accepts one spectrum, a list, an image cube,
or a higher-dimensional collection without separate APIs.

## Raw arrays

The spectral axis is last by default:

```python
result = analyze(
    values,
    wavelength=wavelength_um,
    fwhm=fwhm_um,
    profile="aviris_1995",
)
```

Move another axis to the canonical last position with `spectral_axis`:

```python
# Input is (bands, y, x).
result = analyze(
    values,
    wavelength=wavelength_um,
    fwhm=fwhm_um,
    spectral_axis=0,
    profile="aviris_1995",
)
```

The original leading shape is retained after the spectral axis is moved.

| Input shape | Result-variable shape |
|---|---|
| `(bands,)` | `(decisions,)` |
| `(n, bands)` | `(n, decisions)` |
| `(y, x, bands)` | `(y, x, decisions)` |
| `(time, y, x, bands)` | `(time, y, x, decisions)` |

All samples in one call must share wavelength, FWHM, quantity, and profile.
Use separate calls when instruments or calibrations differ.

## The canonical data object

Construct `SpectralData` when metadata should travel with the values:

```python
from tetracorderpy import SpectralData, analyze

data = SpectralData(
    values,
    wavelength_nm,
    fwhm=fwhm_nm,
    mask=invalid,
    spectral_axis=-1,
    wavelength_unit="nm",
    dims=("y", "x", "band"),
    coords={"flight_line": "f230512t01"},
    metadata={"processing_level": "surface reflectance"},
)

result = analyze(data, profile="aviris_1995")
```

When `data` is already `SpectralData`, do not repeat `wavelength`, `fwhm`,
`mask`, `dims`, `coords`, or `metadata` in `analyze()`. This prevents two
conflicting sources of truth.

`dims`, `coords`, and `metadata` are lightweight labels retained by the
input model. They are not currently copied into `AnalysisResult` or interpreted
as xarray coordinates.

## Masks and invalid values

A mask may have the full tensor shape or any shape NumPy can broadcast to it:

```python
# Mask one bad band across all pixels.
band_mask = np.zeros(wavelength.shape, dtype=bool)
band_mask[bad_band_indices] = True

data = SpectralData(cube, wavelength, mask=band_mask)
```

`True` means invalid. NaN and infinity are always invalid, independent of the
explicit mask. Before writing the temporary native cube, invalid cells become
the deleted-point value configured by the selected dataset.

## NumPy-like and xarray inputs

The constructor uses NumPy array coercion and therefore accepts many array-like
objects. This is an interoperability convenience, not a lazy xarray or Dask
backend:

- xarray dimension names and coordinates are not discovered automatically;
- Dask-backed values may be materialized by NumPy coercion; and
- the native backend ultimately writes a concrete float32 cube.

Pass `.data` or `.values` intentionally and provide metadata explicitly.
For datasets larger than memory, use a storage-backed array and a controlled
chunk loop as described in [Large cubes & memory](large-cubes.md).

## Profile inference

If `profile` is omitted, the wrapper currently attempts exact automatic
matching only for the known AVIRIS-1995 response:

```python
profile = get_profile("aviris_1995")
data = SpectralData(values, profile.wavelength, fwhm=profile.fwhm)
result = analyze(data)  # unique exact profile match
```

For every other instrument, pass the profile explicitly. Ambiguity fails
closed instead of guessing from the vector length.
