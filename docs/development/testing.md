# Testing & documentation

The test suite separates fast Python behavior from opt-in tests that execute
the real Tetracorder image.

## Test groups

| Area | What it verifies |
|---|---|
| Data model | axis movement, unit conversion, masks, nonfinite values, invalid wavelength metadata, reflectance-only input |
| Profiles | bundled preset discovery, exact AVIRIS arrays, automatic matching, wrong-band and unknown-profile errors |
| ENVI | BIP round trip, scale/ignore ordering, native VICAR offset, deleted values, arbitrary tensor packing and restoration |
| API | one interface over scalar/batch/cube/higher shapes, temporary cleanup, retained artifacts, overwrite protection |
| Decoder | native material scales, winner collation, sparse output, stable empty decisions |
| Runtime/setup | search paths, PSC discovery, helpful missing-image failure, reuse, dry-run, incomplete checkout, CLI routing |
| Container integration | synthetic one-spectrum execution, the documented expected-match fixture, and a synthetic 2×3 cube through the real 6.00a5 SIF |

The decoder and API unit tests use controlled fakes where isolating Python
logic is the goal. The integration tests are the end-to-end contract: they
write real input files, execute the container, parse native maps, and assert
result shape, dtypes, finite ranges, decision count, process packing, and
artifacts.

## Run fast tests

```bash
uv sync --group dev
uv run pytest
```

Container tests carry the `integration` marker and skip unless explicitly
enabled.

## Run the real SIF tests

```bash
TETRACORDER_RUN_INTEGRATION=1 uv run pytest -m integration
```

These tests use automatic container discovery, so on PSC they find the stable
shared SIF. They do not build an image. To test a specific image:

```bash
TETRACORDER_CONTAINER=/path/to/tetracorder-6.00a5.sif \
TETRACORDER_RUN_INTEGRATION=1 \
uv run pytest -m integration
```

The synthetic curves are created from smooth continua and Gaussian absorption
features; one also adds a small sinusoidal ripple. Neither is copied from a
reference library. One test locks the match table published in the quick start,
while the others verify execution, schema, and native batch packing. None
asserts geological correctness.

## Build the website

```bash
uv sync --group docs
uv run --group docs mkdocs build --strict
```

Preview with live reload:

```bash
uv run --group docs mkdocs serve
```

No npm toolchain is required. MkDocs reads `mkdocs.yml` and Markdown under
`docs/`; Material supplies the theme, and mkdocstrings renders signatures
from the installed source package.

## Build the SIF from source

```bash
./container/build-tetracorder6.sh
```

The build script refuses to replace an existing image. Give a new explicit
destination when retaining multiple images:

```bash
./container/build-tetracorder6.sh /path/to/tetracorder-6.00a5.sif
```

After building:

```bash
apptainer test /path/to/tetracorder-6.00a5.sif
```
