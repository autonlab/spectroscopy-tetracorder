# Maintaining the fork and shared deployment

This page is for maintainers, not routine wrapper users. It separates source
development, upstream synchronization, and deployment on the Pittsburgh
Supercomputing Center (**PSC**).

## Repository roles

| Location or remote | Role | Policy |
|---|---|---|
| `/ocean/projects/cis250251p/<username>/spectroscopy-tetracorder` | personal development checkout | edit, test, commit, and push here |
| `origin` | `autonlab/spectroscopy-tetracorder` fork | maintained `main` branch |
| `upstream` | `PSI-edu/spectroscopy-tetracorder` | authoritative original project |
| `/ocean/projects/cis250251p/shared/repos/spectroscopy-tetracorder` | group-readable installation source | pull-only checkout of fork `main` |
| `/ocean/projects/cis250251p/shared/containers/tetracorder/6.00a5/` | native runtime deployment | versioned, tested SIF |

Do not develop in the shared checkout. It should contain no local commits or
uncommitted changes.

## Ownership boundary

Treat `specpr/`, `tetracorder6.00/`, `tetracorder.cmds/`, `sl1/`, the
original README and history, and inherited examples as upstream or
pre-existing content. Prefer incoming upstream bytes unless a scientifically
reviewed native change is genuinely required.

The maintained overlay is concentrated in `tetracorderpy/`, `tests/`,
`docs/`, `pyproject.toml`, `mkdocs.yml`, and the Tetracorder 6 container
definition and build script. When possible, adapt to upstream changes through
profiles, the container build, or copied per-run command files rather than
editing official command and library trees.

The wrapper and its tests support Tetracorder 6.00. Legacy 5.x files retained
in repository history do not imply Python support for those versions.

## Synchronize a new upstream commit

Begin on a clean personal `main`:

```bash
git status --short
git switch main
git pull --ff-only origin main
git fetch --prune upstream
git merge upstream/main
```

Inspect every conflict rather than selecting one side repository-wide:

```bash
git diff --name-only --diff-filter=U
git diff upstream/main -- specpr tetracorder6.00 tetracorder.cmds sl1
```

For native trees, first ask whether the wrapper can absorb the new layout
without modifying upstream-owned data. Keep version-specific assumptions
explicit and fail clearly when a supported profile or command layout no longer
satisfies its contract.

## Validate the overlay

Synchronize the development, documentation, and notebook groups:

```bash
uv sync --group dev --group docs --group notebook
```

Run the fast suite and render the site:

```bash
uv run pytest
uv run --group docs mkdocs build --strict
```

Then exercise the existing SIF:

```bash
TETRACORDER_RUN_INTEGRATION=1 uv run pytest -m integration
```

The integration suite uses an existing SIF; it does not rebuild one. If an
upstream commit changes compiled source, expert-system commands, or embedded
libraries, build a new candidate from scratch at a distinct path. Run
`apptainer test` and the full integration suite against the candidate before
promoting it.

## Publish main

After review and validation:

```bash
git push origin main
```

Direct writes to fork `main` are the current local policy. If branch
protection or a review policy is introduced later, use a short-lived branch
and pull request instead.

## Update the shared checkout

Only after the fork has the validated commit:

```bash
git -C /ocean/projects/cis250251p/shared/repos/spectroscopy-tetracorder \
  status --short

git -C /ocean/projects/cis250251p/shared/repos/spectroscopy-tetracorder \
  fetch origin

git -C /ocean/projects/cis250251p/shared/repos/spectroscopy-tetracorder \
  switch main

git -C /ocean/projects/cis250251p/shared/repos/spectroscopy-tetracorder \
  pull --ff-only origin main
```

The status output must be empty. Stop if the shared checkout has local changes
or cannot fast-forward; do not discard or force-rewrite unexplained work.

Existing consumer projects can rebuild their installed wheel from the updated
shared path with:

```bash
uv sync --reinstall-package spectroscopy-tetracorder
```

Promoting a SIF is a separate operation. Preserve the previous versioned image,
verify the candidate's labels and integration outputs, and change the stable
shared runtime only after that review.
