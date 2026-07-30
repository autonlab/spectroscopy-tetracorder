# Installation on PSC

The Python package and the Tetracorder runtime have separate lifecycles. The
package is small and belongs in your uv project; the SIF is large, shared, and
discovered at execution time.

## Add the Python package

From the project that will call Tetracorder:

```bash
uv add 'spectroscopy-tetracorder @ git+https://github.com/autonlab/spectroscopy-tetracorder.git@fanurs/a-more-standalone-example'
```

This installs `tetracorderpy`, NumPy, the command-line entry point, and bundled
sensor-profile metadata. It does **not** put a SIF or the multi-gigabyte
spectral-library tree in the wheel.

!!! info "No Node environment is involved"

    The documentation uses Python packages from a uv `docs` group. Building
    or using the wrapper does not require npm, `env_nodejs`, or a
    documentation container.

## Use the shared image

On this PSC allocation, automatic discovery includes:

```text
/ocean/projects/cis250251p/shared/containers/tetracorder/6.00a5/tetracorder-6.00a5.sif
```

Check what setup would do without changing anything:

```bash
uv run tetracorderpy setup --dry-run
```

Expected on this PSC allocation:

```text
Would reuse existing image: /ocean/projects/cis250251p/shared/containers/tetracorder/6.00a5/tetracorder-6.00a5.sif
```

If it reports that it would reuse the shared image, installation is complete.
The first call to `analyze()` will use `apptainer` or `singularity` from
`PATH`.

## Build only when necessary

If no usable shared image exists:

```bash
uv run tetracorderpy setup
```

The setup command:

1. refuses to overwrite an existing image;
2. prefers a compatible source checkout already on PSC;
3. otherwise shallow-clones the Git revision recorded by `uv add`;
4. performs a clean source build, never layering on another SIF; and
5. runs `apptainer test` on the result.

Use an explicit destination when you do not have permission to create the
standard shared path:

```bash
uv run tetracorderpy setup --output /path/you/control/tetracorder-6.00a5.sif
export TETRACORDER_CONTAINER=/path/you/control/tetracorder-6.00a5.sif
```

See [Runtime & containers](../guides/runtime.md) for the complete discovery
order and override variables.

## Work on this checkout

Developers can synchronize only the groups they need:

```bash
uv sync --group dev
uv sync --group docs
```

Preview this website with:

```bash
uv run --group docs mkdocs serve
```

MkDocs prints a local URL and rebuilds pages when Markdown changes. Generate
the static site in `site/` with:

```bash
uv run --group docs mkdocs build --strict
```

The generated directory is intentionally ignored by Git; the Markdown,
configuration, theme styling, and artwork are versioned.

## What must be available

| Component | Required for | Where it lives |
|---|---|---|
| Python 3.12+ and uv | installing and calling the wrapper | your Python project |
| NumPy | the public tensor model | the uv environment |
| Apptainer or Singularity | launching native Tetracorder | PSC software environment |
| Tetracorder 6.00a5 SIF | compiled programs, commands, libraries | shared storage or an override path |
| MkDocs dependencies | building this website only | optional uv `docs` group |
