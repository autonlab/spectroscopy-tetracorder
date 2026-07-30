# Installation on PSC

These instructions target the Pittsburgh Supercomputing Center (**PSC**)
allocation used by this project. The Python package and the native runtime have
separate lifecycles: your uv environment contains the wrapper, while a shared
SIF contains Tetracorder, Specpr, command files, and spectral libraries.

## Install into your uv project

Run the installation from the project that will call Tetracorder:

```bash
cd /ocean/projects/cis250251p/<username>/<your-project>
uv add /ocean/projects/cis250251p/shared/repos/spectroscopy-tetracorder
```

Use `uv add` so the dependency is recorded in your project's
`pyproject.toml` and lock file. The absolute path is intentional for this PSC
allocation.

uv builds a normal, non-editable wheel containing `tetracorderpy`, NumPy, the
command-line entry point, and compact profile metadata. It does **not** copy the
SIF or the multi-gigabyte native source and library trees into your
environment.

## Verify the shared runtime

```bash
uv run tetracorderpy setup --dry-run
```

Expected on this allocation:

```text
Would reuse existing image: /ocean/projects/cis250251p/shared/containers/tetracorder/6.00a5/tetracorder-6.00a5.sif
```

The dry run changes nothing. If it reports the shared image, installation is
complete. The first call to `analyze()` will select `apptainer`, then
`singularity`, from `PATH`.

You can also check the relevant commands directly:

```bash
command -v uv
command -v apptainer || command -v singularity
```

## If no shared image is available

The normal PSC path should be reused. If it is absent, the setup command can
build a new image from source:

```bash
uv run tetracorderpy setup
```

Setup refuses to overwrite an existing image, builds from the definition and
source tree rather than layering on an older SIF, records source provenance,
and runs the container test.

If you cannot write to the standard shared destination, choose a path you
control and export it for later calls:

```bash
uv run tetracorderpy setup \
  --output /ocean/projects/cis250251p/<username>/containers/tetracorder-6.00a5.sif

export TETRACORDER_CONTAINER=/ocean/projects/cis250251p/<username>/containers/tetracorder-6.00a5.sif
```

See [Runtime & containers](../guides/runtime.md) for the complete discovery
order, environment variables, and explicit function arguments.

## What lives where

| Location | Purpose |
|---|---|
| `/ocean/projects/cis250251p/<username>/<your-project>` | your application and uv environment |
| `/ocean/projects/cis250251p/shared/repos/spectroscopy-tetracorder` | group-readable package source used by `uv add` |
| `/ocean/projects/cis250251p/shared/containers/tetracorder/6.00a5/` | shared native SIF |
| [the autonlab fork](https://github.com/autonlab/spectroscopy-tetracorder) | durable source history and collaboration |
| [the PSI-edu repository](https://github.com/PSI-edu/spectroscopy-tetracorder) | authoritative upstream project |

The shared repository is a deployment checkout, not a development workspace.
Routine users install from it but do not edit it.

## Requirements

| Component | Needed for | Location |
|---|---|---|
| Python 3.12+ and uv | installing and calling the wrapper | your project environment |
| NumPy | the public tensor model | installed by uv |
| Apptainer or Singularity | launching native Tetracorder | PSC software environment |
| Tetracorder 6.00a5 SIF | programs, commands, and libraries | shared storage or `TETRACORDER_CONTAINER` |
| MkDocs and notebook dependencies | maintaining this website and tutorial only | optional dependency groups |

Maintainers should use [Maintaining the fork](../development/upstream-sync.md)
for upstream synchronization, testing, publication, and updating the shared
checkout.
