# Large cubes & memory

Batching many spectra into one `analyze()` call avoids launching a container
per pixel. It does not make native Tetracorder streaming or memory-free.
Choose a batch size from memory and scratch-space constraints, not only process
startup cost.

## What is lazy today

The ENVI reader uses `numpy.memmap`, so unscaled BIP/BIL/BSQ raster values can
remain storage-backed. The temporary native input cube is written one line at a
time.

## What is materialized

During analysis, the current implementation may allocate:

- one float32 line buffer and one line-sized Boolean validity buffer while
  writing the packed native cube;
- Tetracorder's native working rasters on disk;
- decompressed native metric rasters during decoding; and
- five final result tensors over `sample_shape + (decisions,)`.

The compact result alone uses approximately **17 bytes per pixel per decision**
before Python/container overhead:

| Result | dtype | Bytes |
|---|---:|---:|
| `material_id` | int32 | 4 |
| `fit` | float32 | 4 |
| `depth` | float32 | 4 |
| `fit_depth` | float32 | 4 |
| `matched` | bool | 1 |

At 45 decisions, one million pixels need about 765 MB for those five arrays.
Native intermediate maps and transient decoder data require additional RAM and
scratch storage.

!!! warning "Memory-mapped input is not end-to-end lazy execution"

    Passing a compatible memmap and writing the temporary cube are line-bounded,
    including validity checks. Native result decoding still materializes output
    tensors. There is no built-in Dask graph, result iterator, or `chunks=`
    parameter yet.

## A bounded line-chunk pattern

For a scene that is already float reflectance and whose ENVI metadata does not
trigger a full-cube scale or ignore-value copy, process bounded ranges of
lines:

```python
from pathlib import Path

import numpy as np

from tetracorderpy import SpectralData, analyze, get_profile
from tetracorderpy.formats import read_envi

scene = read_envi(
    "scene/reflectance",
    apply_reflectance_scale=False,
)
profile = get_profile("aviris_1995")

lines, samples, _ = scene.values.shape
block_lines = 128
destination = Path("decoded")
destination.mkdir(exist_ok=True)

stores = {}

for start in range(0, lines, block_lines):
    stop = min(start + block_lines, lines)
    block_mask = (
        None if scene.mask is None else scene.mask[start:stop]
    )
    block = SpectralData(
        scene.values[start:stop],
        scene.wavelength,
        fwhm=scene.fwhm,
        mask=block_mask,
        dims=("y", "x", "band"),
        metadata={"line_range": (start, stop)},
    )
    result = analyze(
        block,
        profile=profile,
        scratch_dir="/path/to/job-scratch",
    )

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
```

This example intentionally leaves product-specific scaling and geospatial
metadata to the caller. If the ENVI file stores scaled integer DNs, apply that
scale per chunk before constructing `SpectralData`.

Each chunk launches a new native process. Keep the profile, preprocessing,
decision metadata, and output schema identical across chunks, and validate
chunked output against an unchunked subset before production use.

## Concurrency

Independent calls can use separate temporary working directories, and the SIF
is read-only. Bounded multiprocessing is therefore possible, but it multiplies
RAM, decompression, and scratch I/O. On PSC:

- prefer one native batch per reasonably sized cube block;
- cap worker count from measured peak memory and filesystem load;
- never launch one process per pixel; and
- consider scheduler job arrays for independently managed scenes.

The wrapper does not currently coordinate a worker pool. The caller owns
chunking, retries, output assembly, and resource requests.

## Choosing a block size

Measure on a representative subset. Account for:

1. `pixels × bands` for the selected input block and conversion work;
2. `pixels × decisions × 17 bytes` for compact results;
3. native rasters and decompression peaks;
4. any simultaneous workers; and
5. scratch capacity for temporary native maps, or larger retained artifacts
   when `output_dir` is used.

Leave headroom rather than choosing a block that barely fits.
