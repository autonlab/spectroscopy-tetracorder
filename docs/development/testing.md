# Testing & documentation

The test suite separates fast Python behavior from opt-in tests that execute
the real Tetracorder image.

## Test groups

| Area | What it verifies |
|---|---|
| Data model | axis movement, unit conversion, masks, nonfinite values, invalid wavelength metadata, reflectance-only input |
| Profiles | four exact response grids, unique/ambiguous inference, count-only labels, mismatch errors, explicit 5.27 rejection |
| ENVI | BIP round trip, scale/ignore ordering, VICAR offset, deleted values, arbitrary layout restoration, bounded non-contiguous packing |
| API | scalar/batch/cube/higher shapes, metadata carry-through, scratch cleanup, retained artifacts, overwrite protection |
| Decoder | native material scales, winner collation, sparse output, stable empty decisions |
| Runtime/setup | search paths, PSC discovery, helpful missing-image failure, reuse, dry-run, incomplete checkout, CLI routing |
| Notebook | every code cell executed, no saved errors, plots and real single/batch outputs retained |
| Container integration | synthetic spectrum, locked quick-start matches, one 2×3 native batch, and corner equality against independent runs through the real 6.00a5 SIF |

The decoder and API unit tests use controlled fakes where isolating Python
logic is the goal. The integration tests are the end-to-end contract: they
write real input files, execute the container, parse native maps, and assert
result shape, dtypes, finite ranges, decision count, process packing, and
artifacts.

## Run fast tests

```bash
uv sync --group dev --group notebook
uv run pytest
```

For a branch-aware coverage report:

```bash
uv run --group dev pytest --cov=tetracorderpy --cov-branch --cov-report=term-missing
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
while the others verify execution, schema, native batch packing, and exact
batch-versus-single equality for two corner pixels. None
asserts geological correctness.

## Re-execute the tutorial

The notebook is committed with outputs from the real SIF:

```bash
uv sync --group notebook
uv run --group notebook jupyter execute docs/tutorials/python-api-tutorial.ipynb --inplace --timeout=1200
```

The fast suite checks that every code cell has an execution count, no saved
error, plots, and the expected single/batch summary.

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
`docs/`; Material supplies the theme, mkdocstrings renders signatures, and
mkdocs-jupyter renders the saved notebook without rerunning Tetracorder.

## Publish with GitHub Pages

The `.github/workflows/docs.yml` workflow builds pull requests and deploys
pushes to `main`. It uses a sparse checkout and does not install the project,
so the multi-gigabyte native and library trees are not materialized merely to
build the site. The saved notebook is rendered without executing Tetracorder.

After the workflow reaches the fork's default branch, select **GitHub Actions**
under **Settings → Pages → Build and deployment → Source**. The published
project site is:

```text
https://autonlab.github.io/spectroscopy-tetracorder/
```

## Build the SIF from source

```bash
./container/build-tetracorder6.sh
```

The build script refuses to replace an existing image and records the checkout
commit (plus a dirty suffix when applicable) in the new SIF. Give a distinct
destination when retaining multiple images:

```bash
./container/build-tetracorder6.sh /path/to/tetracorder-6.00a5.sif
```

After building:

```bash
apptainer test /path/to/tetracorder-6.00a5.sif
```
