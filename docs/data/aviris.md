# AVIRIS

AVIRIS—the Airborne Visible/Infrared Imaging Spectrometer—is a useful reference
instrument for learning the wrapper because this repository contains a
complete, runnable 1995 configuration.

AVIRIS names a sensor family, not one file format or one immutable spectral
response. The Pittsburgh Supercomputing Center (PSC) examples include AVIRIS
Classic 2024 in ENVI BIL, AVIRIS-3 L2A in NetCDF, and a reduced 188-band
Cuprite ENVI benchmark. See
[PSC shared dataset examples](psc-shared-datasets.md) for their concrete
schemas and current compatibility.

## Instrument context

NASA JPL describes the original AVIRIS as 224 detectors with approximately
10 nm bandwidths spanning roughly 380–2500 nm. Each spatial pixel therefore
contains a VIS–NIR–SWIR spectrum. See the official
[AVIRIS concept page](https://aviris.jpl.nasa.gov/aviris/concept.html) for the
instrument and scanning geometry.

“224 bands” alone does not identify a calibration. Wavelength centers and
bandpasses can be specific to an instrument configuration and processing
generation.

## The `aviris_1995` profile

```python
import numpy as np

from tetracorderpy import get_profile

profile = get_profile("aviris_1995")

assert profile.expected_bands == 224
assert profile.wavelength is not None
assert profile.fwhm is not None

print(profile.wavelength.min(), profile.wavelength.max())
print(np.count_nonzero(np.diff(profile.wavelength) < 0))  # 3
```

The arrays are loaded from the upstream `waves.txt` and `resol.txt` records
associated with the repository's `s06av95a` calibration. They are packaged
with the Python wheel, so code can construct a valid tensor without reaching
into the SIF.

The three negative differences are retained intentionally. They reflect the
stored channel order; the wrapper does not sort or regularize it.

## Reading an AVIRIS-style ENVI cube

If the ENVI header contains the matching wavelength and FWHM lists:

```python
from tetracorderpy import analyze
from tetracorderpy.formats import read_envi

scene = read_envi("scene/cuprite_reflectance")
result = analyze(scene, profile="aviris_1995")
```

The profile compares the cube's wavelength coordinates to the exact response.
If the values are in nanometers, the ENVI `wavelength units` field is honored
and canonicalized to micrometers.

## When this profile is the wrong choice

Do not choose `aviris_1995` merely because:

- a dataset came from some AVIRIS flight;
- it contains 224 bands;
- its approximate range is 0.4–2.5 µm; or
- you can interpolate it to 224 values.

Confirm the dataset documentation and calibration arrays. A different sensor,
AVIRIS generation, removed-band product, or resampled derivative needs a
matching native Tetracorder dataset and convolved libraries.

## The Cuprite tutorial data

The upstream repository's `cuprite95` directory contains commands and
reference results for an AVIRIS 1995 Cuprite run. The large image cube is
distributed separately, as described by `cuprite95/README-image-cube.txt`.
That tutorial is valuable for regression against known upstream output.

The synthetic NumPy test serves a different purpose: it proves that the public
API can build and execute a valid one-pixel cube without claiming a known
geological answer.

The separate shared file `nasa_aviris_cuprite/Cuprite_S1_R188.img` is not this
full 1995 tutorial cube. It is a 188-band reduced benchmark with no declared
radiometric scale and no matching native profile; do not pass it as
`profile="aviris_1995"`.
