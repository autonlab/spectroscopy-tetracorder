# ENVI

ENVI is a common raster representation for imaging spectroscopy: a flat binary
data stream accompanied by a small ASCII `.hdr` file. The header records
shape, type, byte order, interleave, and often spectral metadata.

The vendor's [ENVI image-file documentation](https://www.nv5geospatialsoftware.com/docs/ENVIImageFiles.html)
defines the three interleaves:

- **BIP** — all bands for one pixel are adjacent;
- **BIL** — bands are interleaved within each image line; and
- **BSQ** — each complete band is stored sequentially.

The adapter presents all three as `(lines, samples, bands)`.

## Read a cube

```python
from tetracorderpy.formats import read_envi

data = read_envi("scene/reflectance")

print(data.values.shape)
print(data.wavelength.shape)
print(data.fwhm)
print(data.dims)  # ("y", "x", "band")
```

Pass either the binary path or its `.hdr` sidecar. The reader recognizes both
`cube` + `cube.hdr` and common sibling pairs such as `cube.img` + `cube.hdr`
or `cube.raw` + `cube.hdr`. If no wavelength list is in the header, supply one
explicitly:

```python
data = read_envi(
    "scene/reflectance",
    wavelength=wavelength_um,
    fwhm=fwhm_um,
    wavelength_unit="um",
)
```

Then use the same analysis API as an in-memory tensor:

```python
result = analyze(data, profile="aviris_1995")
```

## Header fields used

| ENVI field | Behavior |
|---|---|
| `samples`, `lines`, `bands` | required storage shape |
| `data type`, `byte order` | translated to a NumPy dtype |
| `header offset` | skipped before raster data |
| `interleave` | BIP, BIL, or BSQ |
| `wavelength` | band centers, unless overridden |
| `fwhm` or `bandwidth` | bandpass width, unless overridden |
| `wavelength units` | converted to canonical micrometers |
| `data ignore value` | converted to a Boolean mask |
| `bbl` | zero-valued bad bands are masked |
| `reflectance scale factor` | divided out by default |

The official [ENVI header reference](https://www.nv5geospatialsoftware.com/docs/enviheaderfiles.html)
contains many additional fields. The current adapter preserves all raw fields
under `data.metadata["header"]`, but it does not yet turn map projection or
geolocation fields into typed Python coordinates.

Real headers can omit scientifically important metadata. The Pittsburgh
Supercomputing Center (PSC) AVIRIS Classic 2024 example lists wavelengths
numerically in nanometers without a `wavelength units` field and stores
`-9999` edge pixels without a
`data ignore value`. The reader cannot safely guess either fact; pass the unit
and construct a bounded mask explicitly. See
[PSC shared dataset examples](psc-shared-datasets.md#aviris-classic-2024-envi-pair).

## Memory behavior

`read_envi_array()` creates a NumPy `memmap` and transposes it as a view when
needed. Merely opening an unscaled cube does not read the full binary file into
RAM.

```python
from tetracorderpy.formats import read_envi_array

array, header = read_envi_array("scene/reflectance")
block = array[0:64]  # pages only the requested lines from storage
```

`read_envi()` can retain that mapped backing, but some header operations
materialize arrays:

- applying a non-unit reflectance scale creates a float32 cube;
- comparing every value with a `data ignore value` creates a full mask; and
- analysis creates an invalid-value mask and in-memory result tensors.

Therefore the adapter is memory-map aware, not an end-to-end lazy execution
engine. Use [Large cubes & memory](../guides/large-cubes.md) before processing a
scene that cannot fit comfortably in memory.

## Write a simple cube

```python
from tetracorderpy.formats import write_envi

binary_path, header_path = write_envi(
    "export/reflectance",
    cube,
    wavelength=wavelength_um,
    fwhm=fwhm_um,
    mask=invalid,
)
```

The writer emits a three-dimensional little-endian float32 BIP cube and an
ENVI header. Invalid values use the requested deleted-point marker.

## Command line

For a complete ENVI scene:

```bash
uv run tetracorderpy scene/reflectance --profile aviris_1995
```

The command prints a compact JSON summary. Add `--output-dir` when native maps
and logs must be retained.
