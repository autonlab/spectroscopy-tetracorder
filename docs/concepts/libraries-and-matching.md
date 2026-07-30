# Libraries & matching

Tetracorder identifies candidate materials by comparing spectral features with
reference spectra and applying a configured expert system. The library,
instrument response, and command set are part of the analysis definition—not
background files that can be swapped without changing the meaning of a run.

## What is inside the SIF

The clean Tetracorder 6.00a5 image embeds:

- compiled Tetracorder and SPECPR executables;
- the `tetracorder.cmds` expert-system tree at `/t1/tetracorder.cmds`;
- the repository's full `sl1` spectral-library tree at `/sl1`; and
- system packages needed by the native workflow.

The container test specifically verifies the AVIRIS-1995 convolved records
`/sl1/usgs/library06.conv/s06av95a` and
`/sl1/usgs/rlib06/r06av95a`.

These are image contents, not files mounted from the local Git checkout at
runtime. For each analysis, only the Python working directory is bind-mounted
at `/work`. That makes a shared read-only SIF usable from any uv project
without cloning the large library next to that project.

## Measured, resampled, and convolved libraries

A laboratory reference spectrum may have much finer or different sampling than
an imaging sensor. Tetracorder uses library variants prepared for the relevant
instrument response. This is why `aviris_1995` is more than a 224-element
shape label: its command setup points to AVIRIS-specific convolved library
records.

For broader scientific context, the official
[USGS Spectral Library Version 7 report](https://pubs.usgs.gov/publication/ds1035)
describes native SPECPR records, generic text exports, and convolved/resampled
versions for selected instruments. The SIF in this project uses the
library-generation resources present in this repository, including the
`library06.conv` and `rlib06` trees; it does not silently substitute the
newest online library release.

## What the Python result means

The native expert system is organized into groups and conditional cases. For
each decision, Tetracorder writes material-specific fit, depth, and fit-depth
rasters after applying its rules. The wrapper:

1. discovers the configured group/case axis;
2. decodes native numeric scales;
3. collates winning material maps;
4. restores the original sample shape; and
5. returns aligned arrays plus a material ID/name catalog.

The Python code does not independently compare your curve against every raw
library record. Consequently, a future “return a reference spectrum” API would
need a deliberate SPECPR/library reader and metadata model; it should not be
inferred from the final material-name catalog.

## Expected output from the worked spectrum

The exact synthetic curve in [First analysis](../getting-started/quickstart.md)
currently yields:

| Decision | Material ID | Native material name | Fit | Depth | Fit-depth |
|---|---:|---|---:|---:|---:|
| group 1 · `group.1um` | 117 | `fe2+fe3+_water_RTsludge` | 0.8471 | 0.2078 | 0.1765 |
| group 2 · `group.2um` | 196 | `micagrp_muscovite-low-Al` | 0.9569 | 0.1706 | 0.1627 |
| group 4 · `group.1.5um-broad` | 385 | `g4-fe2+generic_nrw.cummingtonite` | 0.6078 | 0.1373 | 0.0843 |

The remaining 42 decision cells have `matched == False` and
`material_id == -1`. These values were measured through the current 6.00a5
SIF; changing the expert system, library, profile, or input curve can change
the matches.

!!! warning

    This table is a reproducibility fixture, not geological validation. The
    input was invented mathematically and is not a sample of the named
    materials.

## Choosing a library today

The public choice is the sensor `profile`, which selects a Tetracorder dataset
preset and, through the expert-system commands, its prepared library records:

```python
result = analyze(data, profile="aviris_1995")
```

There is not yet a Python parameter that selects an arbitrary library file.
Supporting that safely would require validating compatible wavelength
response, expert-system commands, material scaling metadata, and container
contents together.
