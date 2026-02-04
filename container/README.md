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

Since we might not have the massive image file, we will run **Tetracorder Single Spectrum Mode**. This effectively says: *"Pretend I just clicked one pixel. Here is its data. What is it?"*

### Prerequisites
You need **Singularity** (or Apptainer) installed on your Linux machine.

### Step-by-Step Instructions

#### 1. Enter the Container
Open your terminal in the project root and run:
```bash
singularity shell container/tetracoder5_27.sif
```
*Your prompt should change. You are now "inside" the isolated environment.*

#### 2. Go to the Test Directory
Inside the container, navigate to the configured test folder:
```bash
cd /t1/cuprite95/test5.26e1
```
*(Note: `/t1` is a shortcut inside the container that points to your project folder).*

#### 3. Run the Analysis
We will run `tetracorder5.27single`. It is an interactive program, so we feed it a prepared script (`cmds.start.t5.26a.single`) that answers all its questions automatically.

Run this command:
```bash
tetracorder5.27single < cmds.start.t5.26a.single
```

### What just happened?
-   **Input:** The script `cmds.start.t5.26a.single` told Tetracorder to load the spectral libraries.
-   **Processing:** It compiled a mapping list of materials (look for lines like `Deepest absorption features extracted`).
-   **Success:** If it finishes without an error (exit code 0), the "Brain" of the system is working. It successfully loaded the geology definitions and is ready to process data.

---

## 4. The "Real" Run (Cube Mode)

If you download the full data file (`cuprite.95.cal.rtgc.v`) and place it in `cuprite95/cube/`, you can run the full image analysis.

**Command:**
```bash
# Inside /t1/cuprite95/test5.26e1
tetracorder5.27 < cmds.start.t5.26a
```
*Note the absence of "single". This runs the full image processor.*

---

## 5. Outputs: Where are the results?

After a full run, Tetracorder creates several output files in your current directory or specified subdirectories.

1.  **Log Files (`cmd.runtet.out`):**
    -   A massive text log of everything that happened.
    -   *How to read:* Look for "Errors" or "Warnings".

2.  **Material Maps (Images):**
    -   Tetracorder generates generic gray-scale images representing where materials are found.
    -   *Format:* often raw binary or specially formatted image cubes.
    -   *Interpretation:* Brighter pixels = higher confidence/abundance of that material.

3.  **Post-Processing:**
    -   Usually, you run a second step (using the `davinci` tool included in the container) to turn those raw result maps into colorful, human-readable maps (e.g., "Red = Alunite, Green = Calcite").

### Interpreting Screen Output
During the run, you will see scrolling text like:
```text
Group 1: Carbonates...
Group 2: Clays...
```
This indicates the software is actively matching your data against these material families.
