# PSC shared dataset examples

The shared directory at the Pittsburgh Supercomputing Center (**PSC**) is a
useful format laboratory:

```text
/ocean/projects/cis250251p/shared/datasets/hyperspectral-datasets
```

It contains several sensor generations and several *product levels*. Some
files are reflectance cubes that could be Tetracorder inputs; others are
uncertainties, masks, quick looks, or mineral maps that have already been
derived from spectra.

!!! info "A shared snapshot, not package data"

    These files are not installed with `tetracorderpy`, and the package tests
    do not depend on them. The observations below describe the files inspected
    on **2026-07-29**. The shared collection can evolve independently of this
    repository.

## Start by asking what the pixels mean

The extension alone is not enough. A NetCDF file can contain reflectance or a
classification; a GeoTIFF can contain an RGB preview or integer mineral IDs.

| Representative file | On-disk representation | Pixel payload | Direct Tetracorder input? |
|---|---|---|---|
| `mica_example/.../measurement.raw` + `.hdr` | ENVI BIL, float32, 224 bands | AVIRIS Classic 2024 reflectance | yes, with explicit unit and nodata handling |
| `mica_example/.../EMIT_L2A_RFL_....nc` | NetCDF-4/HDF5, float32, 285 bands | EMIT surface reflectance | scientifically compatible with the inspected `emit_c` response; no built-in NetCDF reader yet |
| `nasa_aviris/..._RFL_ORT.nc` | chunked NetCDF-4/HDF5, float32, 284 bands | AVIRIS-3 orthorectified surface reflectance | not yet; the native preset is incomplete |
| `nasa_aviris_cuprite/*.img` + `.hdr` | ENVI BSQ, int16, 188 bands | a reduced-band Cuprite benchmark cube | not with any current profile |
| `*_MIN_*.nc`, `*_COG.tif`, `measurement_prediction.raw` | NetCDF, COG, or ENVI | mineral IDs, depths, classes, or fit | no—these are already outputs |

The most important rule is:

> Feed `analyze()` a reflectance spectrum or reflectance cube, not a color
> image, uncertainty cube, mask, or previous classifier output.

## The `mica_example` directory

The directory name describes the worked mineral-mapping use case. It does not
mean that every file contains a mica spectrum. In particular, the collection
mixes EMIT science products, derived mineral maps, and a separate AVIRIS
Classic scene.

### EMIT L2A reflectance: the spectral input

One acquisition directory contains this product family:

```text
20231023T183842_2329612_007/
├── EMIT_L2A_RFL_001_20231023T183842_2329612_007.nc
├── EMIT_L2A_RFLUNCERT_001_20231023T183842_2329612_007.nc
├── EMIT_L2A_MASK_001_20231023T183842_2329612_007.nc
├── EMIT_L2B_MIN_001_20231023T183842_2329612_007.nc
└── EMIT_L2B_MINUNCERT_001_20231023T183842_2329612_007.nc
```

The L2A `RFL` file is the input-like product:

| Property | Inspected value |
|---|---|
| reflectance variable | `reflectance(downtrack, crosstrack, bands)` |
| shape | `(1280, 1242, 285)` |
| dtype | float32 |
| units | unitless reflectance fraction |
| fill value | `-9999.0` |
| wavelength metadata | 285 centers and FWHM values in nanometers |
| usable-band flag | `good_wavelengths`: 244 good, 41 bad |
| native geometry | instrument swath, with 2-D longitude/latitude/elevation |
| map lookup | `glt_x` and `glt_y` on a `(1993, 2300)` orthorectified grid |

The 285 wavelength and FWHM values in this exact file agree with the
repository's EMIT-C calibration tables within `1e-6 µm`, and the native
`emit_c` preset expects 285 channels. That is evidence for using
`profile="emit_c"` for this inspected acquisition; band count by itself would
not establish the match for a different EMIT processing generation.

`tetracorderpy` does not yet provide a NetCDF adapter. An ecosystem reader can
materialize bounded blocks and then hand the abstract arrays to the existing
API. For example, with optional `xarray`, `h5netcdf`, and `dask` dependencies
installed in the caller's project:

```python
from pathlib import Path

import numpy as np
import xarray as xr

from tetracorderpy import SpectralData, analyze

path = Path(
    "/ocean/projects/cis250251p/shared/datasets/hyperspectral-datasets/"
    "mica_example/20231023T183842_2329612_007/"
    "EMIT_L2A_RFL_001_20231023T183842_2329612_007.nc"
)

rfl = xr.open_dataset(
    path,
    engine="h5netcdf",
    chunks={"downtrack": 64, "crosstrack": 128, "bands": -1},
)
sensor = xr.open_dataset(
    path,
    group="sensor_band_parameters",
    engine="h5netcdf",
)

# Only this spatial block is materialized.
values = rfl["reflectance"].isel(downtrack=slice(0, 64)).values
wavelength_nm = sensor["wavelengths"].values
fwhm_nm = sensor["fwhm"].values
good = sensor["good_wavelengths"].values.astype(bool)
invalid = (
    ~np.isfinite(values)
    | (values == -9999.0)
    | ~good[None, None, :]
)

block = SpectralData(
    values,
    wavelength_nm,
    fwhm=fwhm_nm,
    mask=invalid,
    wavelength_unit="nm",
    dims=("downtrack", "crosstrack", "band"),
)
result = analyze(block, profile="emit_c")
```

This is an integration pattern, not a built-in `open_emit()` function. Keep
blocks bounded: opening with Dask is lazy, but `.values` and `analyze()`
materialize the selected block.

### EMIT mask and uncertainty products: context, not reflectance

The sibling files answer different questions:

- `L2A_RFLUNCERT` describes uncertainty in the reflectance estimate;
- `L2A_MASK` contains eight mask/ancillary layers—cloud, cirrus, water,
  spacecraft, dilated cloud, AOD550, water vapor, and an aggregate flag—and a
  packed per-wavelength mask;
- neither should be passed to `analyze()` as the reflectance tensor.

Use them to construct masks, quality filters, uncertainty-aware validation, or
downstream metadata.

### EMIT L2B and COG files: existing mineral outputs

`EMIT_L2B_MIN_...nc` is already a mineral product. Its primary variables are:

```text
group_1_band_depth(downtrack, crosstrack)
group_1_mineral_id(downtrack, crosstrack)
group_2_band_depth(downtrack, crosstrack)
group_2_mineral_id(downtrack, crosstrack)
```

The file also carries a 294-entry mineral table with index, SPECPR record,
name, URL, group, and library. Its processing history records a Tetracorder
5.27c workflow plus a grouping stage. It is therefore valuable reference
output, but it is not expected to be numerically identical to raw decisions
from this wrapper's Tetracorder 6.00 backend.

The root-level TIFFs are map-ready derivatives:

| File pattern | Raster content |
|---|---|
| `*_COG.tif` | one uint8 palette-index band; 0 is nodata/unclassified and 1–84 are grouped mineral categories |
| `*_UNGROUPED_COG.tif` | one uint16 palette-index band; 0 is nodata and 1–294 index the ungrouped mineral table |
| `*.qml` | QGIS color/style rules |
| `*.tif.aux.xml` | GDAL category-name metadata |

The inspected COGs are `(1993, 2300)`, Deflate-compressed, and tiled in
`512 × 512` blocks. In the grouped product, category 5 is `Muscovite`, with
additional mixed categories such as `Kaolinite_Muscovite`. That is where the
folder's mica interpretation becomes visible. These TIFFs contain class IDs,
not 285-band spectra.

NASA's official [EMIT L2A user guide](https://lpdaac.usgs.gov/documents/1569/EMITL2ARFL_User_Guide_v1.pdf)
describes the reflectance products, while the
[EMIT L2B release note](https://www.earthdata.nasa.gov/data/alerts-outages/emitl2bmin-data-product-released)
describes the mineral-identification and band-depth product.

### AVIRIS Classic 2024 ENVI pair

The large `f240513t01p00r07_rfl` subdirectory contains another workflow:

```text
measurement.hdr                 # reflectance metadata
measurement.raw                 # 20.45 GB reflectance cube
measurement_prediction.hdr      # two-band result metadata
measurement_prediction.raw      # type and fit rasters
measurement.jpg                 # visualization
measurement.xml                 # application-specific metadata
```

The reflectance header declares:

| ENVI field | Value |
|---|---|
| interleave | BIL |
| spatial shape | 19,095 lines × 1,195 samples |
| bands | 224 |
| data type | 4: little-endian float32 |
| map | WGS-84 / UTM zone 11N, 15.9 m pixels |
| wavelengths | 378.929810–2498.33569 nm in native channel order |

The wavelength array exactly matches the repository's AVIRIS Classic 2024
table, and the native `aviris_2024` preset expects 224 bands. Two metadata
omissions still matter:

- the header lists nanometer values but has no `wavelength units` field, so
  pass `wavelength_unit="nm"` explicitly;
- edge pixels contain `-9999.0`, but the header has no `data ignore value`, so
  construct the mask per block rather than comparing the entire 20 GB cube at
  once.

The ENVI reader resolves either `measurement.raw` or `measurement.hdr` and
keeps the unscaled raster memory-mapped:

```python
import numpy as np

from tetracorderpy import SpectralData, analyze
from tetracorderpy.formats import read_envi

scene = read_envi(
    "/ocean/projects/cis250251p/shared/datasets/hyperspectral-datasets/"
    "mica_example/f240513t01p00r07_rfl/measurement.raw",
    wavelength_unit="nm",
    apply_reflectance_scale=False,
)

# Start with a small line block; do not materialize a scene-wide mask.
values = scene.values[1000:1016]
invalid = ~np.isfinite(values) | (values == -9999.0)
block = SpectralData(
    values,
    scene.wavelength,
    mask=invalid,
    dims=("y", "x", "band"),
    metadata={"source_lines": (1000, 1016)},
)
result = analyze(block, profile="aviris_2024")
```

#### Observed one-pixel smoke test

The existing shared SIF was used to analyze line `9547`, sample `597` from
this file. Only that memory-mapped 224-value spectrum was read. Its reflectance
range was approximately `0.0000379–0.344528`; the native packing was `1 × 1`,
each result array had shape `(45,)`, and six decisions matched:

| Decision | Chosen native material | Fit | Depth | Fit × depth |
|---|---|---:|---:|---:|
| group 1 | `fe2+generic_carbonate_siderite1` | 0.701961 | 0.050980 | 0.035294 |
| group 2 | `carbonate_calcite+0.3muscovite` | 0.917647 | 0.058824 | 0.052941 |
| group 3 | `vegetation.weak.map` | 0.419608 | 0.003922 | 0.003922 |
| case 1 | `red.edge.shift.2` | 0.862745 | 0.121600 | 0.103867 |
| case 4 | `veg1.2um.band` | 0.733333 | 0.013725 | 0.011765 |
| case 5 | `veg1.4um.band` | 0.807843 | 0.035294 | 0.027451 |

!!! warning "A reproducibility check, not field validation"

    This demonstrates that the local header interpretation, `aviris_2024`
    preset, container, and result decoder agree. It does not establish the
    geological truth of that arbitrarily selected pixel.

The prediction pair is not a spectrum. It is a two-band float32 BIL raster
whose labels identify a USGS type/class band and a fit band. Inspect it with
`read_envi_array()` rather than `read_envi()`, because its two band labels are
categorical strings, not numeric wavelengths:

```python
from tetracorderpy.formats import read_envi_array

prediction, _ = read_envi_array("measurement_prediction.raw")
predicted_type = prediction[..., 0]
predicted_fit = prediction[..., 1]
```

See [Large cubes & memory](../guides/large-cubes.md) before increasing the
block size.

## NASA AVIRIS-3 L2A NetCDF products

The `nasa_aviris` directory contains many four-file scene families. For one
inspected prefix:

```text
AV320240905t204343_000_L2A_OE_f576f24d_RFL_ORT.nc
AV320240905t204343_000_L2A_OE_f576f24d_UNC_ORT.nc
AV320240905t204343_000_L2A_OE_f576f24d_RFL_ORT_QL.tif
AV320240905t204343_000_L2A_OE_f576f24d.yaml
```

The suffixes carry the product meaning:

| Suffix | Meaning |
|---|---|
| `RFL_ORT.nc` | orthorectified L2A surface reflectance—the spectral cube |
| `UNC_ORT.nc` | orthorectified reflectance uncertainty |
| `RFL_ORT_QL.tif` | three-band RGB quick-look GeoTIFF |
| `.yaml` | processing inputs, parameters, software versions, timing, and spatial extent |

The inspected reflectance file is a UTM-zone-11N grid:

```text
reflectance(wavelength=284, northing=1815, easting=1693)
```

It uses float32 values, `-9999.0` fill, nanometer wavelength/FWHM coordinates,
and NetCDF chunks of `(10, 256, 256)` with compression. That layout supports
bounded or lazy spatial access. The spectral axis is first, unlike the EMIT
file and the wrapper's default spectral-last convention, so an adapter must
transpose it or pass `spectral_axis=0`.

The file's 284 center/FWHM arrays agree within `6e-7 µm` with the repository's
`waves-aviris3_2025a.txt` and `resol-aviris3_2025a_fwhm.txt`. However, those
are preparatory response files only: the 6.00 command tree has no matching
AVIRIS-3 `DATASETS` entry, restart file, and convolved reference-library
package. Consequently there is no usable Python profile yet.

!!! warning "Do not substitute another AVIRIS profile"

    `aviris_1995` and `aviris_2024` are 224-band AVIRIS Classic responses.
    `aviris5_2025` is a different 424-band sensor response. None is a valid
    alias for this 284-band AVIRIS-3 product.

The official [ORNL DAAC AVIRIS-3 L2A guide](https://daac.ornl.gov/AVIRIS/guides/AV3_L2A_RFL.html)
defines the NetCDF, uncertainty, quick-look, YAML, filename, and UTM
conventions represented by these local files.

## The 188-band Cuprite ENVI benchmark

`nasa_aviris_cuprite` contains a compact detached ENVI pair:

```text
Cuprite_S1_R188.hdr
Cuprite_S1_R188.img
```

The header describes a `(250, 190, 188)` cube in canonical
`(lines, samples, bands)` order. On disk it is BSQ, little-endian int16, with
188 wavelength and FWHM entries in nanometers. The 17.86 MB binary size exactly
matches that declaration.

This is a reduced-band benchmark, not a full native AVIRIS cube. Its stored
values range from approximately `-50` to `8929`, but the header declares
neither a reflectance scale factor nor an ignore value. The file alone does not
justify assuming a scale. It also cannot validate against the 224-band
`aviris_1995` profile.

The reader can safely inspect the storage without making a scientific profile
claim:

```python
from tetracorderpy.formats import read_envi_array

cube, header = read_envi_array(
    "/ocean/projects/cis250251p/shared/datasets/hyperspectral-datasets/"
    "nasa_aviris_cuprite/Cuprite_S1_R188.img"
)

print(cube.shape)       # (250, 190, 188)
print(cube.dtype)       # int16
print(header.interleave)  # bsq
```

To analyze this particular reduced product with Tetracorder, one would need
documented radiometric scaling and a native dataset/reference library prepared
for the exact retained 188-channel response. Padding, sorting, or pretending
it is a 224-band calibration would not supply that scientific model.

## What is supported today

| Product | Storage reader | Matching 6.00 native profile | Recommended use now |
|---|---|---|---|
| AVIRIS Classic 2024 `measurement.raw` | built-in ENVI reader | `aviris_2024`; exact local wavelength match verified | analyze bounded blocks with explicit nm and `-9999` mask |
| EMIT L2A `RFL.nc` | optional ecosystem NetCDF reader | `emit_c`; exact inspected calibration match verified | convert bounded blocks to `SpectralData` |
| AVIRIS-3 `RFL_ORT.nc` | optional ecosystem NetCDF reader | incomplete | inspect/preprocess only until native resources exist |
| Cuprite 188-band `.img` | built-in ENVI reader | none | storage/benchmark inspection only |
| EMIT L2B, COG, prediction, uncertainty, mask, quick look | format-specific ecosystem reader | not applicable | treat as outputs, QA, metadata, or comparison targets |

This separation is intentional: **format support** tells us how to recover
arrays and metadata, while **profile support** tells us whether Tetracorder has
the matching sensor response and convolved libraries. Both are required for a
scientifically meaningful analysis.
