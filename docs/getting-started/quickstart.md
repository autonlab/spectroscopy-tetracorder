# First analysis

This example deliberately creates a spectrum with NumPy. It proves that the
entire Python → temporary ENVI cube → container → Tetracorder → Python result
path works without relying on a tutorial input file.

## Construct a minimally plausible curve

Use the exact wavelength and bandpass arrays associated with the
`aviris_1995` profile:

```python
import numpy as np

from tetracorderpy import analyze, get_profile

profile = get_profile("aviris_1995")
wavelength = profile.wavelength
assert wavelength is not None

# A gentle continuum with three synthetic absorption features.
continuum = 0.47 + 0.07 * (
    (wavelength - wavelength.min()) / np.ptp(wavelength)
)
reflectance = continuum.copy()

for center, depth, width in (
    (0.92, 0.11, 0.065),
    (2.20, 0.13, 0.035),
    (2.33, 0.055, 0.030),
):
    reflectance -= depth * np.exp(
        -0.5 * ((wavelength - center) / width) ** 2
    )

reflectance = np.clip(reflectance, 0.02, 0.98).astype(np.float32)
```

The values are dimensionless reflectance fractions. The three Gaussian dips
make the curve spectrum-like; they do not assert the presence of a real
mineral.

Inspect the exact array before running it:

```python
print(reflectance.shape)
print(f"{wavelength.min():.8f} {wavelength.max():.8f}")
print(f"{reflectance.min():.6f} {reflectance.max():.6f}")
```

Expected output:

```text
(224,)
0.37892981 2.49833569
0.377862 0.540000
```

<div class="tc-spectrum-figure">
  <canvas data-spectrum-chart role="img" aria-label="The exact 224-point synthetic AVIRIS-1995 reflectance spectrum used in this example">
    An interactive plot of the synthetic reflectance spectrum from 0.379 to 2.498 micrometers.
  </canvas>
  <div class="tc-spectrum-status">Loading the interactive spectrum…</div>
</div>
<p class="tc-spectrum-caption">
  Exact 224 wavelength/reflectance pairs from the Python example. Hover for
  values. The three markers show the constructed feature centers.
</p>

The interactive canvas uses the pinned Chart.js 4.5.1
`chart.umd.min.js` build from jsDelivr; no npm build is needed. If external
JavaScript is unavailable, the numeric example and expected values above
remain the source of truth.

## Run Tetracorder once

```python
result = analyze(
    reflectance,
    wavelength=wavelength,
    fwhm=profile.fwhm,
    profile=profile,
)
```

For a one-dimensional input, every result variable has one final decision
axis:

```python
print(result.shape)
print(len(result.decisions))
print(result.backend_version)
```

Expected output with Tetracorder 6.00a5:

```text
(45,)
45
6.00
```

Print only matched decisions:

```python
for index, decision in enumerate(result.decisions):
    if not result.matched[index]:
        continue

    material_id = int(result.material_id[index])
    print(
        f"{decision.kind:5} {decision.number:>2} "
        f"{decision.name:22} "
        f"{result.material_name(material_id):38} "
        f"fit={float(result.fit[index]):.4f} "
        f"depth={float(result.depth[index]):.4f} "
        f"fd={float(result.fit_depth[index]):.4f}"
    )
```

The current 6.00a5 image produces three matched decisions for this exact
synthetic curve:

```text
group  1 group.1um              fe2+fe3+_water_RTsludge                 fit=0.8471 depth=0.2078 fd=0.1765
group  2 group.2um              micagrp_muscovite-low-Al                fit=0.9569 depth=0.1706 fd=0.1627
group  4 group.1.5um-broad      g4-fe2+generic_nrw.cummingtonite        fit=0.6078 depth=0.1373 fd=0.0843
```

The native packing is also observable:

```python
keys = ("native_lines", "native_samples", "input_spectra", "padded_spectra")
print({key: result.provenance[key] for key in keys})
```

```text
{'native_lines': 1, 'native_samples': 1, 'input_spectra': 1, 'padded_spectra': 0}
```

That 1×1 layout is intentional: even one Python spectrum uses the native cube
workflow. See [Native modes & parameters](../concepts/native-modes.md).

!!! warning "Execution test ≠ scientific validation"

    A made-up spectrum is useful for checking schemas, packing, execution, and
    decoding. The names above are deterministic software output, not a claim
    that the invented curve contains those materials. Validate real analyses
    with suitable calibration, known materials, reference products, and domain
    review.

## Keep native files only for inspection

The call above uses a Python temporary directory and deletes it after all
result arrays have been decoded. To inspect native maps and logs, give a new
or empty directory:

```python
result = analyze(
    reflectance,
    wavelength=wavelength,
    fwhm=profile.fwhm,
    profile=profile,
    output_dir="artifacts/synthetic-001",
)

print(result.artifacts_path)
```

The empty-directory requirement prevents an accidental overwrite. See
[Results & artifacts](../guides/results.md) for the output schema.

## Move from one spectrum to a cube

The function does not change. Stack spectra on leading axes:

```python
cube = np.stack(
    [
        np.stack([reflectance, reflectance * 0.98]),
        np.stack([reflectance * 1.02, reflectance]),
    ]
)

result = analyze(
    cube,                       # (y=2, x=2, bands=224)
    wavelength=wavelength,
    fwhm=profile.fwhm,
    profile=profile,
)

assert result.shape[:2] == (2, 2)
```

All four spectra are packed into one native cube and launch one container
process, not four.
