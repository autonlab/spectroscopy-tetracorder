# Getting Started

`tetracorderpy` is an **unofficial** Python interface to the existing
Tetracorder 6 expert system. It accepts reflectance arrays and their spectral
coordinates, runs the native cube workflow in an Apptainer or Singularity
container, and returns aligned NumPy result arrays.

These instructions are written for the Pittsburgh Supercomputing Center
(**PSC**) allocation used by this project.

!!! note "Unofficial interface and documentation"

    This fork and website are not the official Tetracorder project, and the
    fork maintainers do not claim authorship of Tetracorder, Specpr, its expert
    systems, or its spectral libraries. The
    [upstream repository](https://github.com/PSI-edu/spectroscopy-tetracorder)
    remains authoritative. See the
    [license and disclaimer](development/license-and-disclaimer.md).

## What the wrapper does

| You provide | The wrapper handles | You receive |
|---|---|---|
| reflectance values | temporary native ENVI input | material identifiers |
| wavelength centers and, when available, FWHM | container discovery and one native cube run | fit, depth, and fit-depth arrays |
| a matching sensor profile | native file parsing and cleanup | decision metadata and provenance |

A one-dimensional spectrum, a batch, and a spatial cube all use the same
`analyze()` function. All spectra in one call are sent through one native
batch run; the wrapper does not launch one process per pixel.

## Before you begin

You need:

- access to the project allocation on PSC;
- Python 3.12 or later and `uv` in your own project;
- `apptainer` or `singularity` on `PATH`; and
- reflectance data whose wavelength sampling matches a supported
  [sensor profile](concepts/sampling-and-profiles.md).

## 1. Install the package

From the Python project that will call Tetracorder:

```bash
cd /ocean/projects/cis250251p/<username>/<your-project>
uv add /ocean/projects/cis250251p/shared/repos/spectroscopy-tetracorder
```

The package is installed into your project's uv environment. The large
Tetracorder image and spectral libraries remain in shared storage.

See [Installation on PSC](getting-started/installation.md) for the runtime
layout, overrides, and recovery setup command.

## 2. Check the shared runtime

```bash
uv run tetracorderpy setup --dry-run
```

The normal result on this allocation is:

```text
Would reuse existing image: /ocean/projects/cis250251p/shared/containers/tetracorder/6.00a5/tetracorder-6.00a5.sif
```

This command does not rebuild the image. It only reports which existing image
would be used.

## 3. Analyze a spectrum

```python
import numpy as np

from tetracorderpy import analyze, get_profile

profile = get_profile("aviris_1995")
wavelength = profile.wavelength
assert wavelength is not None

continuum = 0.46 + 0.05 * (
    (wavelength - wavelength.min()) / np.ptp(wavelength)
)
reflectance = continuum - 0.12 * np.exp(
    -0.5 * ((wavelength - 2.20) / 0.035) ** 2
)
reflectance = np.clip(reflectance, 0.02, 0.98).astype(np.float32)

result = analyze(
    reflectance,
    wavelength=wavelength,
    fwhm=profile.fwhm,
    profile=profile,
)

print(result.shape)
print(result.backend_version)
```

Expected structural output with the shared 6.00a5 image:

```text
(45,)
6.00
```

The exact material matches depend on the input curve. Read
[First analysis](getting-started/quickstart.md) for a complete executed example
with expected match rows and an interactive spectrum plot.

!!! warning "A successful run is not a validated identification"

    Synthetic examples test installation, array packing, native execution, and
    result decoding. Scientific use still requires suitable calibration,
    compatible sampling, an appropriate reference library, and domain review.

## Where to go next

| Goal | Section |
|---|---|
| Understand spectra, wavelength sampling, and reference matching | [Core Concepts](concepts/hyperspectral-data.md) |
| Pass arrays, masks, cubes, and metadata | [Input tensors & metadata](guides/tensors.md) |
| Read ENVI or work with AVIRIS and shared example data | [Reading and writing ENVI](data/envi.md) |
| Process a scene that is larger than memory | [Cubes larger than memory](guides/large-cubes.md) |
| Interpret returned arrays and optional native artifacts | [Results & artifacts](guides/results.md) |
| Look up exact functions and signatures | [API Reference](reference/index.md) |
| Synchronize upstream or deploy the shared checkout | [Maintainer Notes](development/upstream-sync.md) |

The **Core Concepts** section explains scientific meaning. The **User Guide**
is task-oriented. **API Reference** documents exact Python objects and
signatures. Normal users do not need the **Maintainer Notes** section.

## One important scientific constraint

A wavelength vector is necessary but not sufficient. Tetracorder compares an
observation with reference spectra prepared for a particular instrument
response. The band centers, FWHM values, preprocessing, native dataset preset,
and convolved library must describe the data you are actually analyzing.

If you are bringing a new instrument or product generation, begin with
[Sampling & sensor profiles](concepts/sampling-and-profiles.md).
