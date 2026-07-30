# Processing cubes larger than memory

## The current answer

`analyze()` is a native batch interface, but it is not an end-to-end lazy
array engine.

!!! important "Chunk large scenes along spatial or time axes"

    Keep the source storage-backed, select a bounded block of complete spectra,
    call `analyze()` once for that block, and write its results immediately to
    a disk-backed destination. Do not split the spectral axis: every spectrum
    in a call needs the complete band vector required by its sensor profile.

One block means one container launch. This preserves Tetracorder's native cube
batching without requiring the entire scene or the entire scene-wide result in
RAM. The wrapper does not currently choose block sizes, schedule workers, or
assemble blocks automatically.

## Where memory is used

| Stage | Current behavior |
|---|---|
| Source ENVI raster | `read_envi_array()` returns a `numpy.memmap` view for BIP, BIL, or BSQ |
| `SpectralData` | preserves NumPy arrays and memmap views when no conversion is required |
| Temporary native input | `write_packed_envi()` writes one native line at a time using a float32 line buffer |
| Native execution | Tetracorder creates working and result rasters in the per-call scratch directory |
| Result decoding | allocates the complete result tensors for the current block |
| Returned `AnalysisResult` | remains in memory until the caller stores or releases it |

The compact returned arrays use approximately **17 bytes per pixel per
decision**:

| Result | dtype | Bytes |
|---|---:|---:|
| `material_id` | int32 | 4 |
| `fit` | float32 | 4 |
| `depth` | float32 | 4 |
| `fit_depth` | float32 | 4 |
| `matched` | bool | 1 |

With 45 decisions, one million pixels require about 765 MB for those five
arrays alone. Native intermediate rasters, decompression buffers, the current
input block, and Python overhead require additional memory and scratch space.

## Avoid accidental full-cube copies

`read_envi()` is convenient, but two common header features can materialize a
scene-wide array:

- a non-unit `reflectance scale factor` creates a float32 scaled copy; and
- a `data ignore value` creates a Boolean mask over the cube.

For a file that is comfortably smaller than memory, that behavior is useful.
For a very large file, start with `read_envi_array()`, then convert, scale, and
mask only the current block.

Likewise, passing a Dask-backed xarray object to `SpectralData` does not create
a lazy Tetracorder graph. NumPy coercion may compute it. Select and compute a
bounded block first, then pass the resulting NumPy array.

## A bounded ENVI line loop

The following pattern assumes that the file has already been verified as
compatible with the `aviris_1995` profile. A matching band count by itself is
not enough; check the wavelength centers, FWHM, calibration, and product
generation before production use.

```python
from pathlib import Path

import numpy as np

from tetracorderpy import SpectralData, analyze, get_profile
from tetracorderpy.formats import read_envi_array

mapped, header = read_envi_array("scene/reflectance")
profile = get_profile("aviris_1995")
assert profile.wavelength is not None

if profile.expected_bands != header.bands:
    raise ValueError("scene and profile have different band counts")


def header_float(name, default=None):
    raw = header.fields.get(name)
    if raw is None:
        return default
    return float(raw.strip().strip("{}").strip())


scale = header_float("reflectance scale factor", 1.0)
ignore_value = header_float("data ignore value")

if scale == 0:
    raise ValueError("reflectance scale factor must not be zero")

lines, samples, _ = mapped.shape
block_lines = 128

destination = Path("decoded")
destination.mkdir(exist_ok=True)
stores = {}
decision_key = None

for start in range(0, lines, block_lines):
    stop = min(start + block_lines, lines)

    # This is the only input block materialized in RAM.
    raw = mapped[start:stop]
    values = np.array(raw, dtype=np.float32, copy=True)

    invalid = ~np.isfinite(values)
    if ignore_value is not None:
        invalid |= raw == ignore_value
    if scale != 1.0:
        values /= np.float32(scale)

    block = SpectralData(
        values,
        profile.wavelength,
        fwhm=profile.fwhm,
        mask=invalid,
        dims=("y", "x", "band"),
        metadata={"source_lines": (start, stop)},
    )

    result = analyze(
        block,
        profile=profile,
        scratch_dir="/path/to/job-scratch",
    )

    current_key = tuple(
        (item.kind, item.number, item.name)
        for item in result.decisions
    )
    if decision_key is None:
        decision_key = current_key
    elif current_key != decision_key:
        raise RuntimeError("decision axes changed between blocks")

    variables = {
        "material_id": result.material_id,
        "fit": result.fit,
        "depth": result.depth,
        "fit_depth": result.fit_depth,
        "matched": result.matched,
    }

    if not stores:
        output_shape = (lines, samples, len(result.decisions))
        stores = {
            name: np.lib.format.open_memmap(
                destination / f"{name}.npy",
                mode="w+",
                dtype=array.dtype,
                shape=output_shape,
            )
            for name, array in variables.items()
        }

    for name, array in variables.items():
        stores[name][start:stop] = array

for array in stores.values():
    array.flush()
```

Only one input block and one block-sized `AnalysisResult` are resident at a
time. The `.npy` outputs are disk-backed and can later be reopened with
`numpy.load(..., mmap_mode="r")`.

The example intentionally leaves geospatial metadata and product-specific
quality fields to the caller. Store enough provenance to reconstruct the
spatial placement, selected profile, preprocessing, decision axis, container
identity, and source line range.

## NetCDF, xarray, and Dask

For a chunked NetCDF or HDF5 product, xarray and Dask can remain responsible
for reading:

```python
block_values = (
    dataset["reflectance"]
    .isel(downtrack=slice(start, stop))
    .compute()
    .values
)
```

Pass `block_values` to `SpectralData`, run the native block, persist the
result, and release the block. Dask can orchestrate those outer tasks, but each
`analyze()` task is still a concrete native process with concrete input and
output arrays.

## Choosing a block size

Measure a representative subset and include:

1. `pixels × bands × 4 bytes` for a float32 input block;
2. `pixels × decisions × 17 bytes` for compact returned arrays;
3. transient native metric decompression;
4. Tetracorder scratch rasters;
5. all simultaneous workers; and
6. filesystem capacity and throughput.

Leave headroom. A block that only barely fits will be fragile when material
candidates, masks, or concurrent filesystem activity change.

## Concurrency

Independent blocks use separate temporary directories and a read-only SIF, so
bounded multiprocessing or scheduler job arrays are possible. At the
Pittsburgh Supercomputing Center (**PSC**):

- prefer one native call per reasonably sized spatial block;
- set worker count from measured peak RAM and scratch I/O;
- never launch one process per pixel; and
- keep preprocessing and profile selection identical across blocks.

The wrapper has no built-in worker pool, retry policy, `chunks=` parameter,
Dask collection, or result iterator today. Those would be reasonable future
features, but the explicit block loop is the supported bounded-memory pattern
now.
