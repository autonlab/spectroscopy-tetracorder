# Tetracorder Singularity Container Guide

This guide explains how to use the **USGS Tetracorder** system packaged in this Singularity container.

**Goal:** Feed a single spectral signature (a single pixel from a hyperspectral image) to Tetracorder and have it identify the material by comparing against a library of 542 known geological references.

---

## 1. Concepts: What are we doing?

### The Science (Simplified)
Imagine taking a picture of the ground, but instead of just Red, Green, and Blue (3 colors), your camera captures hundreds of "colors" (wavelengths) across the infrared spectrum.
-   **Hyperspectral Cube:** This is the input image. It's called a "cube" because it has 2 spatial dimensions (X, Y) and 1 spectral dimension (Z).
-   **Spectral Signature:** If you drill down into one pixel of that image, you get a line graph showing how much light gets reflected at different wavelengths. This curve is a unique "fingerprint" for materials like minerals, vegetation, or chemicals.
-   **Tetracorder:** This software takes that fingerprint and checks it against thousands of known fingerprints (the **Spectral Library**) to say: *"This pixel is Alunite (a sulfate mineral) with Fit=0.98."*

### The Container
Scientific software often requires very specific, old system configurations. We have packaged everything (Ubuntu 22.04, Fortran compilers, Libraries) into a single file: `tetracoder5_27.sif`.

---

## 2. Inputs

Tetracorder needs three things:

1.  **A Spectrum to Analyze**
    -   In single spectrum mode, this is a reference to a record in a SPECPR binary file (e.g., record 300 in file `y` = Alunite).
    -   The spectral library files inside the container already contain thousands of known spectra.

2.  **The Spectral Library (The Reference)**
    -   *Location inside container:* `/sl1/usgs/` (built-in, read-only).
    -   *Content:* USGS Spectral Library 06 -- thousands of laboratory-measured spectra.
    -   File `y` = `/sl1/usgs/library06.conv/s06av95a` (convolved for AVIRIS).
    -   File `w` = `/sl1/usgs/rlib06/r06av95a` (reference library).

3.  **Command Scripts (The Instructions)**
    -   *Location:* `cuprite95/test5.26e1/` (or `cuprite95/example-01/` via symlinks).
    -   `r1` -- restart file defining library paths, 224 wavelength channels.
    -   `cmds.start.t5.26a.single` -- command script for single spectrum mode.
    -   `cmd.lib.setup.t5.2e1` -- 867KB file defining 542 materials with 960 spectral features.
    -   `cmd.lib.setup.nots-ratios` -- "NOT" features for material disambiguation.

---

## 3. Running Single Spectrum Mode

### Prerequisites
You need **Singularity** (or Apptainer) installed on your Linux machine.

### Quick Start with `example-01/`

The `cuprite95/example-01/` directory contains a minimal setup with symlinks to config files and all required output directories. From the project root:

```bash
# Analyze Alunite (record 300 in convolved library)
./cuprite95/example-01/run.sh y 300

# Analyze Dry Long Grass (record 7128)
./cuprite95/example-01/run.sh y 7128
```

### Manual Command

If you prefer to run manually, from the project root:

```bash
singularity exec --bind cuprite95:/t1/cuprite95 container/tetracoder5_27.sif \
    bash -c 'cd /t1/cuprite95/example-01 && \
    printf "s\ny 300\n0 0\n4\n\ne\n" | \
    cat cmds.start.t5.26a.single - | \
    tetracorder5.27single r1'
```

### How the stdin Protocol Works

Tetracorder reads commands from stdin. The command file (`cmds.start.t5.26a.single`) is piped first, followed by interactive commands appended via `printf`:

| Step | Input | Purpose |
|------|-------|---------|
| 1 | `cmds.start.t5.26a.single` | Aliases, group directories, library setup |
| 2 | `s` | Enter single spectrum mode |
| 3 | `y 300` | File letter + record number of spectrum to analyze |
| 4 | `0 0` | Data thresholds (0 = none) |
| 5 | `4` | Output verbosity (one-line screen + full results file) |
| 6 | *(blank line)* | Acknowledge "Analysis Complete" |
| 7 | `e` | Exit program |

**Important notes:**
-   The `--bind` flag mounts your local `cuprite95` directory as writable (the container's built-in `/t1` is read-only).
-   The restart file `r1` must be passed as a **command line argument**.
-   `<cmd.lib.setup.t5.2e1` inside the command file is a **Tetracorder include directive** (not shell redirection) -- Tetracorder opens that file directly from disk.
-   The process may time out or show "pipe crashed" errors after analysis is complete; results are already written to disk at that point.

### Available Test Spectra

| Record | File | Material |
|--------|------|----------|
| `y 300` | splib06 | Alunite GDS97 K Syn (150C) |
| `y 7128` | splib06 | Dry Long Grass AV87-2 |
| `w 654` | rlib06 | Muscovite GDS113 Ruby |

---

## 4. Outputs

After a single spectrum analysis, Tetracorder writes two files to the working directory:

### `results` (~200 KB)

Contains a summary header, then per-spectrum analysis. The key section is **CHOSEN OUTPUT**:

```
Spectrum: s06av95a    300  Alunite GDS97 K Syn (150C) s06av95a=a
    Grp/Cse              Material                              Fit     Depth    F*D
     grp 1   1um region    none
     grp 2   2-2.5um       129  MATCHES:  sulfate_kalun150c   1.0000   0.1804   0.1804
     grp 3   veg detect    none
     ...
     grp13   1.3-1.4 nrw   401  MATCHES:  oh_1.432_phyllo-vermiculite  0.8137  0.0936  0.0761
     grp14   1.4-1.5 nrw   442  MATCHES:  ohb_1.449_sulfate-schwertm   0.9787  0.1234  0.1208
     grp15   1.5um OH      448  MATCHES:  ohc_1.455_zeolite-natrolite  0.9302  0.1113  0.1035
```

Following the summary, the file contains detailed per-material scores for all 542 materials.

### Interpreting Results

For each spectral group, the best-matching material is shown with three metrics:
-   **Fit** (0--1): How well the observed spectrum shape matches the reference.
-   **Depth**: Absorption band depth, a proxy for material abundance.
-   **F\*D**: Fit times Depth -- confidence-weighted abundance.

The 22 spectral groups cover different wavelength regions:
-   **Group 1**: 1-micron region (iron oxides like goethite, hematite)
-   **Group 2**: 2-2.5um region (clays, micas, carbonates, sulfates)
-   **Group 3**: Vegetation detection
-   **Group 13-15**: 1.3-1.5um OH features
-   **Group 19**: 1.9-2um water/ice
-   **Group 20-22**: Rare earth elements

### `history` (~1.1 MB)

Detailed processing log showing which materials were enabled/disabled and the full library loading sequence.

---

## 5. Python Wrapper

A Python wrapper is available at `cuprite95/example-01/run_tetracorder.py`.

### Usage

```bash
# Requires Python 3.7+ (uses dataclasses)
uv run python cuprite95/example-01/run_tetracorder.py y 300
```

Output:
```
Spectrum: Alunite GDS97 K Syn (150C) s06av95a=a
  Source: file 's06av95a' record 300

Matches:
  grp  2 2-2.5um          sulfate_kalun150c                   Fit=1.0000  Depth=0.1804  F*D=0.1804
  grp 14 1.4-1.5 nrw      ohb_1.449_sulfate-schwertm          Fit=0.9787  Depth=0.1234  F*D=0.1208
  grp 15 1.5um OH         ohc_1.455_zeolite-natrolite         Fit=0.9302  Depth=0.1113  F*D=0.1035
  grp 13 1.3-1.4 nrw      oh_1.432_phyllo-vermiculite         Fit=0.8137  Depth=0.0936  F*D=0.0761

No match in: grp 1, grp 3, grp 4, grp 5, grp 19, grp 20, grp 21, grp 22
```

### Programmatic Use

```python
from run_tetracorder import run_tetracorder

result = run_tetracorder("y", 300)

for match in result.matches:
    print(f"{match.material_name}: Fit={match.fit}")
```

The `SpectrumResult` object contains:
-   `matches`: list of `GroupMatch` objects (group_num, material_name, fit, depth, fd)
-   `no_match_groups`: list of groups with no identification
-   `title`: spectrum title from the library
