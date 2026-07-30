# Upstream sync & PSC deployment

This fork is a small Python/container overlay on a much larger scientific
repository. Keep upstream synchronization separate from PSC deployment:

- `upstream` is `PSI-edu/spectroscopy-tetracorder`, the original project;
- `origin` is the `autonlab` fork used to publish this branch;
- a personal checkout is the only development workspace; and
- `/ocean/projects/cis250251p/shared/repos/spectroscopy-tetracorder` is a
  pull-only, group-readable deployment checkout.

## Ownership boundary

Treat `specpr/`, `tetracorder6.00/`, `tetracorder.cmds/`, `sl1/`, the original
README/history, and inherited examples as upstream or pre-existing content.
Prefer the incoming upstream bytes during a merge unless a scientifically
reviewed native change is genuinely required.

The maintained overlay is concentrated in `tetracorderpy/`, `tests/`, `docs/`,
`pyproject.toml`, `mkdocs.yml`, and the Tetracorder 6 container definition and
build script. Known defects in the current 6.00a5 command snapshot are
normalized inside a newly built SIF or an isolated per-run command copy. This
keeps corrective edits out of the official command/library trees and reduces
future conflicts.

The legacy files already present on the fork's main branch are retained as
history. They are not evidence of Python support for Tetracorder 5.27; the
wrapper and its tests support only 6.00.

## Merge a new official commit

Start in a clean personal checkout:

```bash
git status --short
git fetch --prune upstream origin
git switch fanurs/a-more-standalone-example
git merge upstream/main
```

Inspect every conflict rather than choosing one side repository-wide:

```bash
git diff --name-only --diff-filter=U
git diff upstream/main -- specpr tetracorder6.00 tetracorder.cmds sl1
```

For native trees, first ask whether the wrapper can adapt through profiles,
the container build, or a copied run file. Keep wrapper code version-specific
and fail clearly when an upstream layout or preset no longer satisfies its
contract.

## Validate the overlay

Run the Python, notebook, and site checks:

```bash
uv sync --group dev --group docs --group notebook
uv run pytest
uv run --group docs mkdocs build --strict
TETRACORDER_RUN_INTEGRATION=1 uv run pytest -m integration
```

The integration suite uses an existing SIF; it does not rebuild one. If the
official commit changes compiled source, expert-system commands, or embedded
libraries, the old SIF cannot validate those new native bytes. Build a new
candidate from scratch at a distinct path, then run `apptainer test` and the
full integration suite against it. Do not overwrite or silently repoint the
known-good shared image while evaluating a candidate.

## Publish, then deploy

After review and validation, publish the development branch:

```bash
git push origin fanurs/a-more-standalone-example
```

Only then fast-forward the group checkout:

```bash
git -C /ocean/projects/cis250251p/shared/repos/spectroscopy-tetracorder status --short
git -C /ocean/projects/cis250251p/shared/repos/spectroscopy-tetracorder fetch origin
git -C /ocean/projects/cis250251p/shared/repos/spectroscopy-tetracorder switch fanurs/a-more-standalone-example
git -C /ocean/projects/cis250251p/shared/repos/spectroscopy-tetracorder pull --ff-only origin fanurs/a-more-standalone-example
```

The first command must be empty. Stop if the shared checkout has local changes
or cannot fast-forward; do not repair it by force. Existing consumer projects
can rebuild their installed wheel from the advanced shared path with:

```bash
uv sync --reinstall-package spectroscopy-tetracorder
```

Promoting a new SIF is a separate operation: preserve the versioned candidate,
verify its labels and integration outputs, and update the stable shared link
only after that review.
