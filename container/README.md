# Tetracorder Singularity Container Guide

This guide explains how to use the **USGS Tetracorder** system packaged in a Singularity container.

**Goal:** Feed a single spectral signature (one pixel from a hyperspectral image) to Tetracorder and have it identify the material by comparing against a library of 542 known geological references.

---

## 1. Concepts

### The Science (Simplified)

Imagine taking a picture of the ground, but instead of just Red, Green, and Blue (3 colors), your camera captures hundreds of "colors" (wavelengths) across the infrared spectrum.

- **Hyperspectral Cube:** The input image. It's called a "cube" because it has 2 spatial dimensions (X, Y) and 1 spectral dimension (wavelength).
- **Spectral Signature:** If you drill down into one pixel, you get a line graph showing reflectance at different wavelengths. This curve is a unique "fingerprint" for materials like minerals, vegetation, or chemicals.
- **Tetracorder:** Software that takes that fingerprint, checks it against thousands of known fingerprints (the **Spectral Library**), and says: *"This pixel is Alunite (a sulfate mineral) with Fit=0.98."*

### Singularity / Containers

Scientific software often requires very specific, old system configurations. We package everything (Ubuntu 22.04, Fortran compilers, spectral libraries, Tetracorder binaries) into a single file: `tetracoder5_27.sif`.

- **Singularity** (also called Apptainer) is a container runtime designed for HPC clusters. It works like Docker but runs without root privileges, which is why it's used on shared clusters like Bridges-2.
- **`.sif` file:** A Singularity Image File -- a single read-only file containing an entire Linux filesystem with all our software pre-installed.
- **`singularity exec <image> <command>`:** Runs a command inside the container. The command sees the container's filesystem (with all the Tetracorder binaries and libraries) but can also access files from the host.
- **`--bind host_path:container_path`:** Mounts a directory from the host into the container at a specific path. This is how we make our local config files visible inside the container.

### The `/t1` Convention

Inside the container, the Dockerfile creates `/t1` as a symlink to `/home/t1`. This is an arbitrary convention inherited from the original USGS setup. The container has built-in data at several paths:

- `/t1/cuprite95/` -- a read-only copy of the cuprite95 test data
- `/t1/tetracorder.cmds/` -- command templates
- `/sl1/usgs/` -- the spectral reference libraries

When we run `--bind cuprite95:/t1/cuprite95`, we overlay our local `cuprite95/` directory over the container's built-in `/t1/cuprite95/`. This lets Tetracorder find our config files (which may differ from the built-in ones) while the rest of the container filesystem remains unchanged.

---

## 2. Getting the Container

The `.sif` file is **not tracked in git** (it's 1.1 GB). You need to obtain it separately.

### Option A: Copy from shared storage

```bash
cp /ocean/projects/cis250251p/shared/tetracoder5_27.sif container/
```

### Option B: Symlink (saves disk space)

```bash
ln -s /ocean/projects/cis250251p/shared/tetracoder5_27.sif container/tetracoder5_27.sif
```

### Verify

Confirm the binary is accessible inside the container:

```bash
singularity exec container/tetracoder5_27.sif tetracorder5.27single
```

This should print a usage message or error (proving the binary exists and runs).

---

## 3. Inputs -- What You Need

### Files you provide

These must be in your working directory (e.g. `cuprite95/example-01/`). They form an include chain and must all be present together:

| File | Purpose |
|------|---------|
| `r1` | Restart file. Defines which spectral library files to use and the 224 wavelength channels. |
| `cmds.start.t5.26a.single` | Command script for single-spectrum mode. Sets up aliases, group directories, and includes the library setup. Line 134 contains `<cmd.lib.setup.t5.2e1`. |
| `cmd.lib.setup.t5.2e1` | Library setup (867 KB). Defines 542 materials with 960 spectral features. Line 222 contains `<cmd.lib.setup.nots-ratios`. |
| `cmd.lib.setup.nots-ratios` | "NOT" features used for material disambiguation. |

The `<filename` syntax is a **Tetracorder include directive** (not shell redirection). Tetracorder opens the referenced file directly from disk, so all 4 files must be co-located.

### Files inside the container (read-only)

You don't need to provide these -- they're baked into the `.sif` image:

| Path | Description | File letter |
|------|-------------|-------------|
| `/sl1/usgs/library06.conv/s06av95a` | Convolved spectral library (AVIRIS) | `y` |
| `/sl1/usgs/rlib06/r06av95a` | Reference spectral library | `w` |

### Auto-generated files (gitignored)

These are created during analysis in the working directory:

| File / Directory | Description |
|------------------|-------------|
| `results` | Main output file (~200 KB) with match results |
| `history` | Detailed processing log (~1.1 MB) |
| `spoolfile`, `fort.55` | Internal Tetracorder temp files |
| `.cmd`, `.spttl` | Internal state files |
| `group.1um/`, `group.2um/`, ... (24 directories) | Per-group analysis output directories |

All of these are listed in `.gitignore` and can be safely deleted.

---

## 4. Running Single Spectrum Mode

### Prerequisites

- **Singularity** (or Apptainer) installed on your Linux machine
- The `.sif` container file (see [Getting the Container](#2-getting-the-container))

### Quick Start with `run.sh`

From the project root:

```bash
# Analyze Alunite (record 300 in convolved library)
./cuprite95/example-01/run.sh y 300

# Analyze Dry Long Grass (record 7128)
./cuprite95/example-01/run.sh y 7128
```

### Manual Command

If you prefer to run Tetracorder directly:

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

### Important Notes

- The `--bind` flag mounts your local `cuprite95` directory over the container's built-in `/t1/cuprite95` (which is read-only).
- The restart file `r1` must be passed as a **command-line argument**, not via stdin.
- `<cmd.lib.setup.t5.2e1` inside the command file is a **Tetracorder include directive** (not shell redirection) -- Tetracorder opens that file directly from disk.
- The process may time out or show "pipe crashed" errors after analysis is complete. This is expected -- results are already written to disk at that point.

### Available Test Spectra

| Record | File | Material |
|--------|------|----------|
| `y 300` | splib06 | Alunite GDS97 K Syn (150C) |
| `y 7128` | splib06 | Dry Long Grass AV87-2 |
| `w 654` | rlib06 | Muscovite GDS113 Ruby |

---

## 5. Outputs -- Understanding Results

After a single spectrum analysis, Tetracorder writes two files to the working directory.

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

- **Fit** (0--1): How well the observed absorption band shape matches the reference. 1.0 = perfect shape match.
- **Depth** (0--1): Absorption band depth. Deeper = more of that material present. A proxy for material abundance/concentration.
- **F\*D** (Fit x Depth): The confidence-weighted abundance score. This is typically the most useful single metric -- it combines shape match quality with signal strength. Higher = more confident identification.
- **"none"** means no material in that spectral group matched above threshold.

### Spectral Groups

The 22 spectral groups cover different wavelength regions:

- **Group 1**: 1-micron region (iron oxides like goethite, hematite)
- **Group 2**: 2-2.5um region (clays, micas, carbonates, sulfates)
- **Group 3**: Vegetation detection
- **Groups 13-15**: 1.3-1.5um OH features
- **Group 19**: 1.9-2um water/ice
- **Groups 20-22**: Rare earth elements

### `history` (~1.1 MB)

Detailed processing log showing which materials were enabled/disabled and the full library loading sequence.

---

## 6. Python Wrapper

The `tetracorderpy` package provides a Python interface to Tetracorder.

### Installation

From the project root:

```bash
uv sync
```

This installs the package (and its `tetracorderpy` CLI entry point) into the project's virtual environment.

### CLI Usage

```bash
uv run tetracorderpy --work-dir cuprite95/example-01 y 300
```

or equivalently:

```bash
uv run python -m tetracorderpy --work-dir cuprite95/example-01 y 300
```

CLI options:

| Flag | Default | Description |
|------|---------|-------------|
| `--work-dir` | *(required)* | Directory containing the 4 config files |
| `--container` | auto-discover | Path to `.sif` file (default: finds `container/*.sif`) |
| `--timeout` | 15 | Timeout in seconds (a timeout is expected and normal) |

### Programmatic Usage

```python
import tetracorderpy as tt

result = tt.run("y", 300, work_dir="cuprite95/example-01")

for match in result.matches:
    print(f"{match.material_name}: Fit={match.fit}")
```

### Return Types

**`SpectrumResult`** -- returned by `tt.run()`:

| Field | Type | Description |
|-------|------|-------------|
| `file_letter` | `str` | SPECPR file letter (e.g. `"y"`) |
| `record` | `int` | Record number in the SPECPR file |
| `title` | `str` | Spectrum title from the library |
| `matches` | `list[GroupMatch]` | Materials matched per spectral group |
| `no_match_groups` | `list[tuple[int, str]]` | Groups with no match (group_num, group_name) |

**`GroupMatch`** -- one entry per spectral group that found a match:

| Field | Type | Description |
|-------|------|-------------|
| `group_num` | `int` | Spectral group number |
| `group_name` | `str` | Group name (e.g. `"2-2.5um"`) |
| `material_id` | `int` | Material ID within the group |
| `material_name` | `str` | Material name (e.g. `"sulfate_kalun150c"`) |
| `fit` | `float` | Fit score (0--1) |
| `depth` | `float` | Absorption band depth (0--1) |
| `fd` | `float` | Fit x Depth |

---

## 7. Using Other File Letters/Records (`y 300` is Just an Example)

`y 300` is only one test case. In Tetracorder single-spectrum mode, the input is always:

```text
<FILE_LETTER> <RECORD_NUMBER>
```

For example:

- `y 7128` (still from the convolved library)
- `w 654` (from the reference library)

### What the file letter means

The letter (`y`, `w`, etc.) is resolved by the restart file `r1`:

- `iyfl=...` and `inmy=...` define the file behind letter `y`
- `iwfl=...` and `iwdgt=...` define the file behind letter `w`

So you can use letters other than `y` as long as:

1. That device letter is configured in `r1`
2. The referenced library file exists inside the container
3. The record number exists in that library

### Python usage with different inputs

No code changes are required. Just pass different arguments:

```python
import tetracorderpy as tt

r1 = tt.run("y", 7128, work_dir="my-run")
r2 = tt.run("w", 654, work_dir="my-run")
```

---

## 8. New Data (Not `cuprite95`): What to Do

You do **not** need to use the `cuprite95/` directory name. The current Python wrapper works with any directory that contains the required config files.

### 8.1 If you only want single-spectrum analysis

This is the simplest path.

1. Create a new working directory (for example `my-data/run-01/`).
2. Copy these four files into it:
   - `r1`
   - `cmds.start.t5.26a.single`
   - `cmd.lib.setup.t5.2e1`
   - `cmd.lib.setup.nots-ratios`
3. Edit `r1` if needed to point to the correct libraries and channel count.
4. Run from Python:

```python
import tetracorderpy as tt
result = tt.run("y", 300, work_dir="my-data/run-01")
```

This mode does not require a hyperspectral cube file. It analyzes one library spectrum per call.

### 8.2 If you need full cube mapping for a new instrument/cube

This requires more setup and currently is **not** fully wrapped by `tetracorderpy`.

High-level steps:

1. Convolve spectral libraries for your instrument (create the `r06...` and `s06...` library files).
2. Create/update a restart file (`r1-...`) with correct:
   - library file paths
   - file-letter mapping (`w`, `y`, etc.)
   - `nchans`
3. Add a dataset entry under:
   - `tetracorder.cmds/tetracorder5.27a.cmds/DATASETS/`
4. Add deleted-channel definition under:
   - `tetracorder.cmds/tetracorder5.27a.cmds/DELETED.channels/`
5. Generate a new run directory with:
   - `cmd-setup-tetrun`
6. Run tetracorder (`cmd.runtet cube ...`) and post-processing scripts.

This is the official USGS workflow for new sensors.

---

## 9. Python-First Workflow (Current State)

Current status:

- `tetracorderpy` already supports Python-driven single-spectrum runs (`tt.run(...)`).
- It accepts arbitrary file letters and record numbers.
- `work_dir` can be any path, not just `cuprite95/example-01`.

What is not yet wrapped:

- End-to-end automation for creating a new dataset/instrument definition
- Full cube-mode setup (`cmd-setup-tetrun`) and map post-processing

Practical recommendation today:

1. Use shell/command-file steps once to create a valid run directory for your new dataset.
2. Use Python for repeated single-spectrum analyses and result parsing.
3. Add Python automation for dataset bootstrap in a later phase.

If you want, a next step is to add a new Python helper like:

- `tetracorderpy.bootstrap_run_dir(...)` for `cmd-setup-tetrun`
- `tetracorderpy.run_cube(...)` for `cmd.runtet cube`
