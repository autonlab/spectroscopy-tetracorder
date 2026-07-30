# Hyperspectral data

A spectrum describes how a measured quantity changes with wavelength.
Hyperspectral imaging repeats that measurement over a spatial field, giving
each image pixel a spectrum rather than a single brightness or RGB triplet.

## The minimal abstraction

For this wrapper, one observation consists of:

- **reflectance values** — a real numeric vector;
- **wavelength centers** — one coordinate per band;
- **bandpass widths (FWHM)** — optional in the Python model, but important to
  the sensor response; and
- **validity information** — a mask plus automatic handling of NaN and
  infinity.

A collection adds any number of leading sample dimensions:

| Shape | Interpretation |
|---|---|
| `(bands,)` | one spectrum |
| `(samples, bands)` | an unordered or tabular batch |
| `(y, x, bands)` | one image cube |
| `(..., bands)` | any collection whose last axis is spectral |

For example:

```python
import numpy as np

from tetracorderpy import SpectralData, get_profile

profile = get_profile("aviris_1995")
cube = np.full((2, 3, 224), 0.5, dtype=np.float32)
data = SpectralData(
    cube,
    profile.wavelength,
    fwhm=profile.fwhm,
    dims=("y", "x", "band"),
)

print("sample_shape:", data.sample_shape)
print("bands:", data.bands)
print("spectra:", data.spectra)
print("canonical_unit:", data.wavelength_unit)
```

Expected output:

```text
sample_shape: (2, 3)
bands: 224
spectra: 6
canonical_unit: um
```

No container is launched by constructing `SpectralData`; it validates and
normalizes the abstract input model.

This is the abstract data model. ENVI, NumPy, a future xarray adapter, and
instrument-specific archives are representations that can all produce the
same model.

## Why many bands matter

Materials can absorb, scatter, or emit energy differently at nearby
wavelengths. Narrow, contiguous bands can preserve feature shape that would be
lost when broad bands are collapsed into a few colors. Tetracorder uses feature
positions, shapes, continuum behavior, and expert-system rules to compare an
observation with prepared reference spectra.

NASA's original [AVIRIS instrument description](https://aviris.jpl.nasa.gov/aviris/concept.html)
is a concrete example: 224 detectors cover approximately 380–2500 nm. The
[USGS High Resolution Spectral Library](https://www.usgs.gov/centers/gggsc/science/usgs-high-resolution-spectral-library)
shows the corresponding reference side, with measured spectra for minerals,
rocks, soils, plants, liquids, manufactured materials, and more.

## Where cubes and spectra come from

| Source | Typical structure | Examples of concerns before analysis |
|---|---|---|
| Airborne imaging spectrometer | long spatial flight lines | atmospheric correction, geolocation, sensor calibration |
| Spaceborne imaging spectrometer | tiled or orbital scenes | clouds, viewing geometry, atmospheric effects |
| Field spectrometer | individual or repeated spectra | illumination and reference-panel procedure |
| Laboratory spectrometer | samples under controlled conditions | sample preparation, geometry, instrument response |

Tetracorder can analyze laboratory spectra as well as image pixels, but the
same array shape does not make measurements scientifically interchangeable.
The selected expert system and reference response must suit the measurement.

## Reflectance is not radiance

Radiance records energy reaching the sensor and depends on illumination,
atmosphere, geometry, and instrument response. Reflectance attempts to express
the fraction reflected by a surface under a stated calibration model.

`tetracorderpy` currently accepts `quantity="reflectance"` only. It does not
perform radiometric calibration or atmospheric correction. Those steps belong
upstream:

```text
raw detector values
        ↓
radiometric calibration
        ↓
atmospheric / illumination correction
        ↓
apparent surface reflectance
        ↓
sensor-profile validation
        ↓
Tetracorder analysis
```

!!! note

    The repository's Cuprite example uses AVIRIS data calibrated to apparent
    surface reflectance. Use the processing requirements for your own product,
    not simply the fact that its values fall between zero and one.

## Format and meaning are separate

An ENVI header describes storage shape, byte order, interleave, and often
spectral metadata. It does not by itself prove that the values are reflectance,
that atmospheric correction was appropriate, or that the wavelength response
matches a Tetracorder profile.

That separation motivates two layers:

1. format adapters read a file into `SpectralData`;
2. sensor profiles validate that the abstract spectrum is compatible with a
   native Tetracorder dataset.

Continue with [Sampling & sensor profiles](sampling-and-profiles.md), then
[ENVI](../data/envi.md) for a concrete storage format.
