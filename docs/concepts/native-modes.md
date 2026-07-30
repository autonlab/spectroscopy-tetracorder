# Native execution parameters

Tetracorder 6.00 is configured in several stages rather than through one
function call. The Python wrapper automates those stages, but understanding
their order is useful when comparing a Python run with an upstream tutorial.

This page follows the order used by the 6.00a5 setup script:

1. positional arguments to `cmd-setup-tetrun`;
2. optional setup arguments;
3. values selected by the dataset preset;
4. commands written into the generated start file; and
5. prompts used only by the interactive single-spectrum executable.

!!! note "Native terms versus Python arguments"

    This is a description of the native interface, not a promise that every
    native control is a keyword argument of `analyze()`. Each entry below says
    what the wrapper currently supplies, derives, or leaves at the upstream
    default.

## Setup command grammar

For cube mapping, the setup script prints this interface:

```text
cmd-setup-tetrun \
  sub_directory data_set cube image_cube scale_factor \
  [-T min_temperature max_temperature K|C] \
  [-P min_pressure max_pressure bar|Bar] \
  [image gif|png|none] \
  [shortcubeid id_text] \
  [longcubeid long_id_text] \
  [geology|nogeology] \
  [noredoverlayimages] [nodualimages] [autostart]
```

For an interactive or real-time single-spectrum setup, the positional part is
different and there is no cube scale factor:

```text
cmd-setup-tetrun \
  sub_directory data_set singlespectrum follow|nofollow \
  [-T min_temperature max_temperature K|C] \
  [-P min_pressure max_pressure bar|Bar] \
  [longcubeid long_id_text] \
  [geology|nogeology] [autostart]
```

The script scans optional arguments after the positional fields. The
explanations below keep the order in the printed cube grammar.

## Positional parameters, in order

### 1. `sub_directory`

The run directory that `cmd-setup-tetrun` will create and populate. It must not
already exist. Tetracorder copies the restart file, expert-system commands,
support files, and result-directory structure into it.

**Wrapper choice:** `/work/run` inside the container. `/work` is a temporary
directory by default, or the directory passed as `output_dir=` when artifacts
should be retained. The native run-directory name itself is not configurable.

### 2. `data_set`

The name of a file in `tetracorder6.00a.cmds/DATASETS`, such as
`aviris_1995`. This is an instrument/sampling preset, not an input filename.
It selects the restart file, convolved library setup, deleted channels,
threshold defaults, and related support files.

**Wrapper choice:** `profile.backend_profile`. Passing
`profile="aviris_1995"` therefore supplies `aviris_1995` at this position.
Profile validation happens before the container starts.

### 3. `cube` or `singlespectrum`

This chooses the native execution family:

- `cube` maps every pixel in an image cube;
- `singlespectrum` opens the interactive single-spectrum workflow;
- `singlespectrum follow` is the real-time variant that watches a growing
  SPECPR file configured by the dataset preset.

**Wrapper choice:** always `cube`. A `(bands,)` input is packed as a one-line,
one-sample cube; a batch or spatial tensor is packed as a larger cube. This
keeps one output contract, `sample_shape + (decisions,)`, and lets an entire
batch run in one container process.

### 4. `image_cube` or `follow|nofollow`

The meaning depends on parameter 3:

- after `cube`, `image_cube` is the native raster path;
- after `singlespectrum`, `follow` enables a configured real-time SPECPR feed,
  while `nofollow` selects ordinary interactive analysis.

For cube mode, the setup script requires the image path to exist and limits
the path plus filename to 73 characters.

**Wrapper choice:** `/work/input`, an ENVI-compatible binary cube generated
from the caller's spectral tensor. The wrapper does not use follow mode.

### 5. `scale_factor` — cube mode only

A multiplier that converts stored cube values to reflectance or I/F before
analysis. For example, upstream examples use `0.00005` when a stored value of
20,000 represents reflectance 1.0. Single-spectrum mode has no scale-factor
argument.

**Wrapper choice:** `1.0`. The generated cube already contains floating-point
reflectance, so applying another native multiplier would change the data.

## Optional setup parameters, in order

### 6. `-T min_temperature max_temperature unit`

Declares the applicable temperature interval for the data. The canonical flag
is `-T`; the script also accepts `-t`, `T`, and `t`. Units must be `K` or `C`.
If omitted, the setup script writes `0 9999 K`.

**Wrapper choice:** omitted, so the upstream default is used. Temperature is
not currently exposed by `analyze()`.

### 7. `-P min_pressure max_pressure unit`

Declares the applicable pressure interval. The script accepts `-P`, `-p`, `P`,
and `p`; the unit must be `bar` or `Bar`. If omitted, it writes `0 999 bar`.

**Wrapper choice:** omitted, so the upstream default is used. Pressure is not
currently exposed by `analyze()`.

### 8. `image gif|png|none` — cube workflow

Selects the format for native quick-look images produced by the surrounding
cube workflow. The setup default is `gif`.

**Wrapper choice:** `image none`. The Python result is decoded from numerical
Tetracorder products rather than quick-look graphics.

### 9. `shortcubeid id_text` — cube workflow

A short, single-token cube identifier used in output filenames and written to
`AAA.info/shortcubeid.txt`. Its setup default is `tet`.

**Wrapper choice:** omitted, leaving `tet`. It is not a public Python option.

### 10. `longcubeid long_id_text`

A longer, single-token identifier written to `AAA.info/longcubeid.txt` and
used by color and geology products. Its setup default is also `tet`.

**Wrapper choice:** omitted, leaving `tet`. User metadata passed to Python is
preserved on `SpectralData`; it is not substituted into this native filename
field.

### 11. `geology` or `nogeology`

`geology` requests geologic-origin and classification products in addition to
the ordinary material mapping products. The parser also recognizes
`nogeology`, which is the default. The upstream 6.00 notes say geology output
is not yet added to single-spectrum mode.

**Wrapper choice:** omitted, so `nogeology` is generated. Geology products are
not currently decoded or exposed.

### 12. `noredoverlayimages` and `nodualimages` — cube workflow

These independent flags suppress the red-overlay and dual-overlay image
post-processing products. Without the flags, the setup records that those
images may be made.

**Wrapper choice:** both flags are supplied. They avoid unrelated image
products in a numerical Python analysis.

### 13. `autostart`

Requests that the setup script launch the run after installation. Cube runs
may autostart directly. A single-spectrum run may autostart only when following
a configured growing file.

**Wrapper choice:** omitted. The wrapper must first make its compatibility
patches and then invoke the executable itself, so setup and execution are kept
as separate controlled steps.

## The exact setup used by Python

After validating and packing the input, the 6.00 backend executes the
equivalent of:

```text
cmd-setup-tetrun \
  /work/run PROFILE cube /work/input 1.0 \
  image none noredoverlayimages nodualimages
```

Here `PROFILE` is the selected `profile.backend_profile`. It then runs
`/usr/local/bin/tetracorder6.00 r1`, feeds the generated cube start file, and
requests exit when processing finishes.

The SIF also contains `tetracorder6.00single`, but the public Python API does
not currently select it.

## Parameters derived from `data_set`

The dataset preset expands one short name into another ordered set of native
choices. These are read by `cmd-setup-tetrun`, not passed as additional command
line arguments.

| Order | Dataset key | Native purpose | Wrapper behavior |
|---:|---|---|---|
| 1 | `restart` | Restart file copied to the run as `r1`; required | selected by `profile=` |
| 2 | `lib` | Expert-system library setup command | preset value, or the script's 6.00 default |
| 3 | `band` | Channel used for grayscale quick-look images | preset value, or channel 20; not used for result decoding |
| 4 | `start` | Cube start-file template | preset value, or `cmds.start.t6.00a` |
| 5 | `c_nots` | Size-specific NOT/ratio setup | preset value, or the small-channel default |
| 6 | `deletedpoint` | Numeric marker for invalid input | preset value, otherwise `-32767` |
| 7 | `threshholdmin` | Optional lower data threshold | preset value or unset |
| 8 | `threshholdmax` | Optional upper data threshold | preset value or unset |
| 9 | `offset` | Additive cube-value offset | preset value, otherwise `0` |
| 10 | `vfollowfile` | Start file for a real-time SPECPR feed | used only with `singlespectrum follow` |

`threshholdmin` and `threshholdmax` retain the spelling used by the upstream
script. Additional files keyed by the same dataset name supply deleted-channel
lists, variable definitions, force-disable rules, and color-channel choices.

For Python input, the wrapper reads the preset's deleted-point value and writes
masked or non-finite samples with that marker. The other values remain under
the control of the selected native preset.

## Generated cube start file, in order

The setup script substitutes the preceding values into
`cmds.start.t6.00a`. Tetracorder then consumes commands in this order:

| Order | Start-file entry | Purpose | Wrapper-specific handling |
|---:|---|---|---|
| 1 | library, wavelength, directory, and deleted-channel aliases | Names the SPECPR libraries and instrument channel selection | supplied by the template and dataset files |
| 2 | repeated `c` commands, then a blank line | Synchronizes restart-file assignments with file sizes | unchanged |
| 3 | `history`, `results` | Names diagnostic output files | decoded or retained as artifacts |
| 4 | `[WAVEID]` | Selects the wavelength record | dataset-derived |
| 5 | `temperature min max unit` | Applies the setup temperature interval | upstream default because `-T` is omitted |
| 6 | `pressure min max unit` | Applies the setup pressure interval | upstream default because `-P` is omitted |
| 7 | `geology` or `nogeology` | Enables or skips geologic-origin work | `nogeology` |
| 8 | `mode cube` | Enters native cube processing | fixed |
| 9 | `<cmd.lib.setup...` | Loads the selected expert-system rules and library records | dataset-derived |
| 10 | `c` | Starts cube processing after library setup | unchanged |
| 11 | `nomask` | Chooses the native mask mode | invalid data are represented by the deleted-point marker instead |
| 12 | `cube: /work/input` | Identifies the packed input cube | generated |
| 13 | `offset deleted scale threshold_min threshold_max` | Defines cube numeric conversion and validity bounds | preset values with scale `1.0` |
| 14 | error-message flag | Controls additional native error reporting | template default `0` |
| 15 | print interval and diagnostic flag | Controls progress/diagnostic cadence | interval changed to `min(10, native_lines)` |
| 16 | `==list`, then `e` | Records defined variables and exits | unchanged |

The print interval needs a derived value because the stock interval of 10 is
invalid for a packed cube with fewer than ten native lines. The backend also
repairs one malformed 6.00a5 comment marker in the isolated run copy; it does
not modify the source commands in the container.

## Interactive single-spectrum prompts

Interactive selection happens *after* setup and is separate from all of the
parameters above. A native 6.00 single-spectrum session is prepared with, for
example:

```text
cmd-setup-tetrun RUN_DIR aviris_1995 singlespectrum nofollow
cd RUN_DIR
tetracorder6.00single r1
<cmds.start.t6.00a.single
```

The Python API does not invoke this interactive executable or expose SPECPR
device/record locators. Caller-supplied reflectance, wavelength, FWHM, and mask
arrays are packed into the tested 6.00 cube workflow instead.

## What Python currently exposes

The public call deliberately exposes Python-level data and execution controls:

| Python argument | What it controls |
|---|---|
| `data`, `wavelength`, `fwhm`, `mask` | spectral values and validity |
| `spectral_axis`, `wavelength_unit` | array interpretation |
| `dims`, `coords`, `metadata` | labels and caller metadata |
| `profile` | native dataset preset and sampling validation |
| `version` | backend selection; only `"6.00"` is implemented |
| `container`, `runtime` | SIF and Apptainer/Singularity executable |
| `output_dir` | retain the otherwise temporary native work tree |
| `timeout` | maximum native process duration |
| `backend` | advanced backend substitution |
| `scratch_dir` | parent for deleted per-call native work |

Temperature, pressure, geology, native thresholds, identifiers, quick-look
images, and true interactive mode are not public keyword arguments today. If
they become necessary, they should be added through a typed options model with
unit validation, backend capability checks, provenance recording, and
container integration tests—not as an unvalidated string appended to the
native command.

## Source trail

- The original project is the
  [PSI-edu spectroscopy-tetracorder repository](https://github.com/PSI-edu/spectroscopy-tetracorder).
- The setup grammar described here is implemented in the fork's
  [`cmd-setup-tetrun`](https://github.com/autonlab/spectroscopy-tetracorder/blob/fanurs/a-more-standalone-example/tetracorder.cmds/tetracorder6.00a.cmds/cmd-setup-tetrun).
- Python command assembly is in
  [`tetracorderpy/backends/v600.py`](https://github.com/autonlab/spectroscopy-tetracorder/blob/fanurs/a-more-standalone-example/tetracorderpy/backends/v600.py).
- Public arguments and temporary-directory behavior are in
  [`tetracorderpy/api.py`](https://github.com/autonlab/spectroscopy-tetracorder/blob/fanurs/a-more-standalone-example/tetracorderpy/api.py).
