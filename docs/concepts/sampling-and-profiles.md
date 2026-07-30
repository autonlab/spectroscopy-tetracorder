# Sampling & sensor profiles

Wavelength coordinates tell you where bands are centered. They do not fully
describe what each detector measured, and they do not select a scientifically
valid reference library on their own.

## Centers, spacing, and FWHM

For band *i*:

- `wavelength[i]` is its nominal center;
- `fwhm[i]` is the full width at half maximum of its spectral response; and
- the distance to neighboring centers is the **sampling interval**, not
  necessarily the bandpass width.

The centers may be irregularly spaced. Different detector modules can overlap,
leave gaps, or preserve a channel order that is not globally monotonic.

`SpectralData` therefore requires wavelengths to be one-dimensional, finite,
positive, and aligned with the spectral axis. It does **not** require uniform
spacing or sort the bands.

## What Tetracorder actually supports

There are two distinct questions:

| Question | Answer |
|---|---|
| Can Python represent this wavelength vector? | Yes, if it passes the basic numeric checks. |
| Can Tetracorder analyze it correctly? | Only if a native dataset preset and reference libraries exist for that sensor response. |

The Tetracorder 6.00 cube executable used here is compiled for at most **710
bands**. A native line holds at most **32,765 samples**; larger tensors are
repacked over additional lines automatically. There is no corresponding fixed
limit on the number of input spectra imposed by the Python tensor interface,
although memory, storage, and runtime remain practical limits.

The wavelength range and usable band count are determined by the selected
sensor profile. The wrapper does not pad, crop, resample, or interpolate a
spectrum to make it match.

## Strict and partial profile validation

```python
import numpy as np

from tetracorderpy import available_profiles, get_profile

names = available_profiles()
profile = get_profile("aviris_1995")

print(len(names))
print("aviris_1995" in names, "emit_a" in names, "prisma01a" in names)
print(profile.expected_bands)
print(f"{profile.wavelength.min():.8f} {profile.wavelength.max():.8f}")
print(np.count_nonzero(np.diff(profile.wavelength) < 0))
```

Expected from the bundled 6.00 metadata:

```text
61
True True True
224
0.37892981 2.49833569
3
```

Four profiles package exact native center and FWHM arrays:

| Profile | Bands | Center range (µm) | Validation |
|---|---:|---:|---|
| `aviris_1995` | 224 | 0.37892981–2.49833569 | wavelength and FWHM |
| `aviris_2024` | 224 | 0.37892981–2.49833569 | wavelength and FWHM |
| `emit_c` | 285 | 0.3810055–2.4929238 | wavelength and FWHM |
| `aviris5_2025` | 424 | 0.38170–2.49962 | wavelength and FWHM |

Validation requires the same channels in the stored order, within `1e-6 µm`.
The AVIRIS 1995 and 2024 grids are identical, but their native restart
configurations differ; wavelength-only inference therefore refuses to choose
between them.

Other bundled dataset names come from the Tetracorder command tree. Where the
package has only their restart-file channel count, validation can check the
number of bands but **not** prove center wavelengths or FWHM. The caller must
confirm the native dataset's sensor response.

!!! warning "Do not sort a wavelength array by itself"

    The upstream AVIRIS-1995 response contains three decreases in its stored
    channel order. Reordering only the coordinates would detach them from the
    reflectance values. Preserve the response and values together exactly as
    the profile expects.

## Why interpolation is not enough

Resampling an observed spectrum onto familiar wavelength centers can be useful
in a well-designed preprocessing workflow, but it does not recreate the
instrument line-spread function or automatically prepare a valid library.
Tetracorder's references are convolved to sensor range and resolution. Both
observation and library must participate in that model.

For a new instrument, the native work normally includes:

1. characterize center wavelengths and spectral response/FWHM;
2. convolve the reference libraries for that response;
3. create and verify the corresponding Tetracorder dataset/restart setup;
4. include those resources in a rebuilt SIF; and
5. expose a matching `SpectralProfile` in Python.

An advanced caller can construct `SpectralProfile(...,
backend_profile="native_dataset_name")`, but that object does not generate the
native resources. The named dataset must already exist inside the image.

## Units

Pass micrometers by default:

```python
data = SpectralData(reflectance, wavelength_um, fwhm=fwhm_um)
```

Nanometers are canonicalized to micrometers:

```python
data = SpectralData(
    reflectance,
    wavelength_nm,
    fwhm=fwhm_nm,
    wavelength_unit="nm",
)
```

FWHM uses the same declared unit as wavelength. Supported spellings include
`um`, `µm`, `micrometer(s)`, `nm`, and `nanometer(s)`.
