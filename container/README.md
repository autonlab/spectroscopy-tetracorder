# Tetracorder Singularity Container Guide

Welcome! This guide explains how to use the **USGS Tetracorder** system packaged in this Singularity container. 

**Goal:** We will run a "dry run" analysis to prove the software works. We will feed it a single spectral signature (simulating a single pixel from a satellite image) and ask Tetracorder to identify what material it is by comparing it against a library of known geological references.

---

## 1. Concepts: What are we doing?

### The Science (Simplified)
Imagine taking a picture of the ground, but instead of just Red, Green, and Blue (3 colors), your camera captures hundreds of "colors" (wavelengths) across the infrared spectrum.
-   **Hyperspectral Cube:** This is the input image. It's called a "cube" because it has 2 spatial dimensions (X, Y) and 1 spectral dimension (Z).
-   **Spectral Signature:** If you drill down into one pixel of that image, you get a line graph showing how much light gets reflected at different wavelengths. This curve is a unique "fingerprint" for materials like minerals, vegetation, or chemicals.
-   **Tetracorder:** This software takes that fingerprint and checks it against thousands of known fingerprints (the **Spectral Library**) to say: *"There is a 98% chance this pixel contains Kaolinite (clay)."*

### The Container
Scientific software often requires very specific, old system configurations. We have packaged everything (Operating System, Fortran compilers, Libraries) into a single file: `tetracoder5_27.sif`.

---

## 2. The Data: Inputs

In a full run, Tetracorder needs three things:

1.  **The Hyperspectral Cube (The Image)**
    -   *Location:* Usually in `cuprite95/cube/`.
    -   *Format:* Large binary files (hundreds of MBs to GBs).
    -   *Note:* The actual large data file (`cuprite.95.cal.rtgc.v`) is often excluded from code repositories to save space. We will skip the full image analysis for this dry run and focus on a single spectrum.

2.  **The Spectral Library (The Reference)**
    -   *Location:* `sl1/usgs/` (Mapped inside the container).
    -   *Content:* Thousands of laboratory-measured files defining what "Gold", "Calcite", or "Oak Leaf" look like.

3.  **Command Scripts (The Instructions)**
    -   *Location:* `cuprite95/test5.26e1/`.
    -   *Content:* Text files that tell Tetracorder which libraries to use and which wavelength ranges to analyze.

---

## 3. The "Dry Run": Verifying the System

Since we might not have the massive image file, we will run **Tetracorder Single Spectrum Mode**. This verifies the spectral library loads correctly and the system is ready to process spectra.

### Prerequisites
You need **Singularity** (or Apptainer) installed on your Linux machine.

### Step-by-Step Instructions

#### 1. Run Library Verification (Recommended)
The simplest way to verify the system works is to run with a bound writable directory. From the project root:

```bash
singularity exec --bind cuprite95:/t1/cuprite95 container/tetracoder5_27.sif \
    bash -c "cd /t1/cuprite95/test5.26e1 && tetracorder5.27single r1 < cmds.start.t5.26a.single"
```

**Important notes:**
-   The restart file `r1` must be passed as a **command line argument** (not just present in the directory)
-   The `--bind` flag mounts your local `cuprite95` directory as writable (the container's built-in `/t1` is read-only)
-   This loads all 542 materials with 960 spectral features across 22 groups

#### 2. Alternative: Interactive Shell
If you prefer to work interactively:

```bash
singularity shell --bind cuprite95:/t1/cuprite95 container/tetracoder5_27.sif
# Then inside:
cd /t1/cuprite95/test5.26e1
tetracorder5.27single r1 < cmds.start.t5.26a.single
```

### What just happened?

**Inputs:**
-   `r1` - The restart/state file containing spectral library paths and configuration
-   `cmds.start.t5.26a.single` - Command script that sets up single spectrum mode and loads material definitions
-   `cmd.lib.setup.t5.2e1` - The main library definition file (867KB, defines 542 materials)
-   `cmd.lib.setup.nots-ratios` - Defines "NOT" features for material disambiguation
-   `/sl1/usgs/` - The USGS spectral library (reference spectra)

**Processing:**
-   Loads the USGS Spectral Library (library06)
-   Compiles definitions for 542 materials organized into 22 spectral groups
-   Sets up 960 total spectral features for matching
-   In single spectrum mode, waits for interactive spectrum input after setup

**Success indicators:**
-   Lines showing materials being enabled: `material 501 is ENABLED: neodymium_oxide_compete`
-   No "Error" messages in output
-   Creates `history` and `results` files in the working directory

---

## 4. The "Real" Run (Cube Mode)

If you download the full data file (`cuprite.95.cal.rtgc.v`) and place it in `cuprite95/cube/`, you can run the full image analysis.

**Command:**
```bash
singularity exec --bind cuprite95:/t1/cuprite95 container/tetracoder5_27.sif \
    bash -c "cd /t1/cuprite95/test5.26e1 && tetracorder5.27 r1 < cmds.start.t5.26a"
```

*Note the absence of "single" in the executable name. This runs the full image processor.*

**The cube data file:**
-   Format: BIL (Band Interleaved by Line) Integer*2
-   Size: Typically hundreds of MB to several GB
-   The Cuprite test dataset: 972 lines x 614 samples x 224 bands = 596,808 pixels

---

## 5. Outputs: Where are the results?

After a full cube run, Tetracorder creates several output files:

### Key Output Files

1.  **`results`** - Summary statistics for all materials:
    ```
    ***** Group:    1 *****
    group.1um/fe3+_goethite.thincoat             0.760     26567     22138     23486
    group.1um/fe2+_goeth+musc                    0.877     93796     93606     93792
    ```
    Columns: Material name, Mean Fit, Non-Zero Fit pixels, Non-Zero Depth pixels, F*D pixels

2.  **`history`** - Detailed processing log (~1MB), showing which materials were enabled/disabled

3.  **`group.*/` directories** - Per-group output images (e.g., `group.1um/`, `group.2um/`)
    -   Contains grayscale images for each material's fit, depth, and fit*depth

4.  **`results.group.*/` directories** - Aggregated results per spectral group

### Interpreting Results

For each material, three metrics are computed per pixel:
-   **Fit**: How well the observed spectrum matches the reference (0-1 scale)
-   **Depth**: Absorption band depth indicating material abundance
-   **F*D**: Fit times Depth - confidence-weighted abundance

Example from Cuprite (596,808 pixels analyzed):
```
fe2+_goeth+musc    0.877 fit, 93796 pixels matched (15.7% of image)
Kaolinite          0.852 fit, 45231 pixels matched (7.6% of image)
Alunite            0.891 fit, 12847 pixels matched (2.2% of image)
```

### Material Groups

The 22 spectral groups cover different wavelength regions:
-   **Group 1**: 1-micron region (iron oxides like goethite, hematite)
-   **Group 2**: 2-2.5um region (clays, micas, carbonates)
-   **Group 3**: Vegetation detection
-   **Group 13-15**: 1.3-1.5um OH features
-   **Group 19**: 1.9-2um water/ice
-   **Group 20-22**: Rare earth elements
