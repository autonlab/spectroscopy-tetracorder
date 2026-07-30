# Runtime & containers

Each `analyze()` call is a one-shot native workflow. Python prepares an ENVI
cube, launches Tetracorder inside Apptainer/Singularity, decodes the maps, and
returns. There is no persistent Tetracorder server.

## Process boundary

```text
Python process
  ├─ creates work directory and packed input
  ├─ apptainer/singularity exec --bind <work>:/work <image>
  │    └─ Tetracorder 6.00a5 cube workflow
  ├─ reads native result maps
  └─ returns AnalysisResult
```

All spectra supplied to one call share this process. A `(y, x, bands)` cube is
one launch, not `y × x` launches.

The SIF embeds compiled programs, commands, and `sl1` libraries. Only the
per-call work directory is mounted at `/work`; the source checkout is not
required beside an installed Python package.

For the exact cube-mode command, fixed settings, and profile-derived values,
see [Native modes & parameters](../concepts/native-modes.md).

## Container discovery

An explicit function argument has highest priority:

```python
result = analyze(data, profile=profile, container="/path/to/image.sif")
```

Without it, candidates are checked in this order:

1. `TETRACORDER_CONTAINER`;
2. files or directories in the colon-separated
   `TETRACORDER_CONTAINER_PATH`;
3. matching images in a source checkout's `container/` directory;
4. the stable PSC 6.00a5 shared path;
5. other versioned images under the PSC shared container root; and
6. images under the standard PSC shared source checkout.

The first existing file wins. Set a specific `container=` when exact image
selection is part of a reproducibility requirement.

## Runtime executable

Pass an executable name or path explicitly:

```python
result = analyze(data, profile=profile, runtime="apptainer")
```

Otherwise the backend searches `PATH` for `apptainer`, then `singularity`.
The image itself is the same SIF in either case.

## Provisioning

```bash
uv run tetracorderpy setup --dry-run
uv run tetracorderpy setup
```

Setup reuses an existing image. If none exists, it selects the installed or
shared compatible source checkout; an explicit repository/revision is the
fallback when no checkout is available. It then calls
`container/build-tetracorder6.sh`. The build starts from the definition's base
image and source tree, not another SIF, and labels the source commit.

Useful controls:

```bash
uv run tetracorderpy setup --source /path/to/checkout --output /path/to/new.sif
uv run tetracorderpy setup --repository URL --revision BRANCH_OR_COMMIT
uv run tetracorderpy setup --no-verify
```

Existing outputs are never overwritten. `--no-verify` skips
`apptainer test` and should be reserved for cases where verification is
deliberately handled elsewhere.

## Versions

The public API exposes `version=` and the backend interface leaves room for
other implementations, but only:

```python
analyze(data, profile=profile, version="6.00")
```

is implemented. The concrete supported image is Tetracorder **6.00a5**.
Tetracorder 5.x is not emulated or routed through the 6.00 backend.

## Temporary scratch

Use `scratch_dir=` to choose the parent of a per-call temporary work directory,
or set `TETRACORDER_TMPDIR` for a whole job. The wrapper deletes the child
directory after decoding:

```python
result = analyze(data, profile=profile, scratch_dir="/path/to/job-scratch")
```

`output_dir=` is different: it retains native files and must be new or empty.

## Failure behavior

The wrapper raises typed exceptions for missing images/runtimes, invalid data,
profile mismatch, backend limits, setup failure, timeout, or malformed native
output. `TetracorderExecutionError.log_tail` includes the end of relevant
native logs when available.

Use an `output_dir` on a failing minimal reproduction when deeper inspection
is needed. For routine successful calls, automatic temporary cleanup is the
safer default.
