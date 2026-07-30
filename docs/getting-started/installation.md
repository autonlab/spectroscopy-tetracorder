# Installation on PSC

The Python package and the Tetracorder runtime have separate lifecycles. The
package is small and belongs in your uv project; the SIF is large, shared, and
discovered at execution time.

## Add the Python package

From the project that will call Tetracorder:

```bash
uv add /ocean/projects/cis250251p/shared/repos/spectroscopy-tetracorder
```

The absolute path is intentional for this PSC allocation. uv builds a normal,
non-editable wheel in the consumer project, containing `tetracorderpy`, NumPy,
the command-line entry point, and compact sensor-profile metadata. It does
**not** copy the SIF or the multi-gigabyte source/library checkout into the
consumer environment. The resulting lock entry is PSC-specific and should not
be expected to install on an unrelated machine.

!!! info "No Node environment is involved"

    The documentation uses Python packages from a uv `docs` group. Building
    or using the wrapper does not require npm, `env_nodejs`, or a
    documentation container.

## Deployment roles

| Location | Role | Update policy |
|---|---|---|
| a personal checkout such as `/ocean/projects/cis250251p/cteh/spectroscopy-tetracorder` | development, tests, commits | edit here |
| `https://github.com/autonlab/spectroscopy-tetracorder` | fork publication and branch history | push reviewed commits from a personal checkout |
| `/ocean/projects/cis250251p/shared/repos/spectroscopy-tetracorder` | group-readable install source | never develop here; maintainers only fast-forward it from the fork |
| `/ocean/projects/cis250251p/shared/containers/tetracorder/6.00a5/` | versioned SIF deployment | promote a tested, clean source build |

Consumers install from the shared checkout because it is already beside the
large source and library trees and is under the lab's control. GitHub remains
the durable collaboration remote, but it is not the routine PSC install URL.
After the fork branch is pushed and validated, a maintainer updates the shared
checkout with `git fetch`, `git switch`, and `git pull --ff-only`; local edits
or divergent commits are not made there.

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
2. prefers the installed/shared compatible source checkout on PSC;
3. uses an explicitly requested repository/revision only if no checkout is available;
4. performs a clean source build, never layering on another SIF;
5. records the source commit in new image labels; and
6. runs `apptainer test` on the result.

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
uv sync --group dev --group docs --group notebook
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

Re-execute the committed tutorial through the real SIF with:

```bash
uv run --group notebook jupyter execute docs/tutorials/python-api-tutorial.ipynb --inplace --timeout=1200
```

## What must be available

| Component | Required for | Where it lives |
|---|---|---|
| Python 3.12+ and uv | installing and calling the wrapper | your Python project |
| NumPy | the public tensor model | the uv environment |
| Apptainer or Singularity | launching native Tetracorder | PSC software environment |
| Tetracorder 6.00a5 SIF | compiled programs, commands, libraries | shared storage or an override path |
| MkDocs dependencies | building this website only | optional uv `docs` group |
| Shared source checkout | package installation and emergency clean builds | pull-only PSC group storage |
| Notebook dependencies | executing the tutorial | optional uv `notebook` group |
