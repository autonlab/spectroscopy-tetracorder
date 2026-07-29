"""Explicit provisioning command for the Tetracorder SIF."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from importlib import metadata
from pathlib import Path
from typing import Iterator
from urllib.parse import unquote, urlparse

from .errors import RuntimeSetupError
from .profiles import repository_root
from .runtime import (
    PSC_SHARED_SOURCE_CHECKOUT,
    default_shared_container,
)


_DISTRIBUTION = "spectroscopy-tetracorder"
_DEFAULT_REPOSITORY = "https://github.com/autonlab/spectroscopy-tetracorder.git"
_DEFAULT_REVISION = "fanurs/a-more-standalone-example"
_COMMIT = re.compile(r"^[0-9a-fA-F]{40}$")
_REQUIRED_SOURCE_PATHS = (
    "specpr",
    "tetracorder6.00",
    "tetracorder.cmds",
    "sl1",
    "container/build-tetracorder6.sh",
)


def _absolute(path: str | Path) -> Path:
    expanded = Path(path).expanduser()
    return expanded if expanded.is_absolute() else Path.cwd() / expanded


def _is_source_checkout(path: Path) -> bool:
    return all((path / relative).exists() for relative in _REQUIRED_SOURCE_PATHS)


def _validate_source(path: Path) -> Path:
    source = _absolute(path)
    missing = [
        relative
        for relative in _REQUIRED_SOURCE_PATHS
        if not (source / relative).exists()
    ]
    if missing:
        rendered = ", ".join(missing)
        raise RuntimeSetupError(
            f"source checkout {source} is incomplete; missing: {rendered}"
        )
    return source


def _installed_direct_url() -> tuple[str, str | None, str | None] | None:
    try:
        distribution = metadata.distribution(_DISTRIBUTION)
        raw = distribution.read_text("direct_url.json")
    except metadata.PackageNotFoundError:
        return None
    if not raw:
        return None
    try:
        direct = json.loads(raw)
    except json.JSONDecodeError:
        return None

    url = direct.get("url")
    if not isinstance(url, str):
        return None
    vcs = direct.get("vcs_info") or {}
    requested = vcs.get("requested_revision")
    commit = vcs.get("commit_id")
    return (
        url,
        requested if isinstance(requested, str) else None,
        commit if isinstance(commit, str) else None,
    )


def _local_direct_url_path(url: str) -> Path | None:
    parsed = urlparse(url)
    if parsed.scheme != "file":
        return None
    return Path(unquote(parsed.path))


def _git_head(path: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip()


def _existing_source(
    explicit: str | Path | None,
    *,
    expected_commit: str | None,
    direct_url: str | None,
) -> Path | None:
    if explicit is not None:
        return _validate_source(Path(explicit))

    candidates = [repository_root(), PSC_SHARED_SOURCE_CHECKOUT]
    if direct_url:
        local = _local_direct_url_path(direct_url)
        if local is not None:
            candidates.append(local)

    for candidate in candidates:
        if not _is_source_checkout(candidate):
            continue
        if (
            expected_commit
            and candidate == PSC_SHARED_SOURCE_CHECKOUT
            and _git_head(candidate) != expected_commit
        ):
            continue
        return candidate
    return None


def _run(command: list[str], *, cwd: Path | None = None) -> None:
    try:
        subprocess.run(command, cwd=cwd, check=True)
    except FileNotFoundError as exc:
        raise RuntimeSetupError(f"required executable not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeSetupError(
            f"command failed with status {exc.returncode}: {' '.join(command)}"
        ) from exc


@contextmanager
def _cloned_source(
    repository: str,
    revision: str | None,
    expected_commit: str | None,
) -> Iterator[Path]:
    configured_temporary_root = os.environ.get("TETRACORDER_SETUP_TMPDIR")
    temporary_root: str | None = None
    if configured_temporary_root:
        expanded_root = Path(configured_temporary_root).expanduser()
        expanded_root.mkdir(parents=True, exist_ok=True)
        temporary_root = str(expanded_root)
    with tempfile.TemporaryDirectory(
        prefix="tetracorderpy-source-",
        dir=temporary_root or None,
    ) as temporary:
        checkout = Path(temporary) / "spectroscopy-tetracorder"
        command = ["git", "clone", "--depth", "1", "--single-branch"]
        if revision and not _COMMIT.fullmatch(revision):
            command.extend(("--branch", revision))
        command.extend((repository, str(checkout)))
        _run(command)

        target_commit = expected_commit or (
            revision if revision and _COMMIT.fullmatch(revision) else None
        )
        if target_commit and _git_head(checkout) != target_commit:
            _run(
                [
                    "git",
                    "-C",
                    str(checkout),
                    "fetch",
                    "--depth",
                    "1",
                    "origin",
                    target_commit,
                ]
            )
            _run(
                ["git", "-C", str(checkout), "checkout", "--detach", target_commit]
            )
        if target_commit and _git_head(checkout) != target_commit:
            raise RuntimeSetupError(
                f"cloned source does not match requested commit {target_commit}"
            )
        yield _validate_source(checkout)


def _runtime_executable() -> str:
    runtime = shutil.which("apptainer")
    if runtime is None:
        raise RuntimeSetupError("apptainer is required to build or verify the SIF")
    return runtime


def setup_runtime(
    *,
    source: str | Path | None = None,
    output: str | Path | None = None,
    repository: str | None = None,
    revision: str | None = None,
    verify: bool = True,
    dry_run: bool = False,
) -> Path:
    """Reuse or build the supported SIF and return its stable path.

    Existing images are never overwritten. Without ``source``, the command
    prefers the current checkout and the standard PSC shared checkout, then
    shallow-clones the exact Git revision recorded by ``uv add``.
    """

    configured_output = output or os.environ.get("TETRACORDER_CONTAINER")
    output_path = _absolute(configured_output or default_shared_container())
    if output_path.is_symlink() and not output_path.exists():
        raise RuntimeSetupError(f"output is a dangling symlink: {output_path}")
    if output_path.exists():
        if not output_path.is_file():
            raise RuntimeSetupError(f"container output is not a file: {output_path}")
        if dry_run:
            print(f"Would reuse existing image: {output_path}")
        elif verify:
            _run([_runtime_executable(), "test", str(output_path)])
        return output_path

    direct = _installed_direct_url()
    direct_url = direct[0] if direct else None
    requested_revision = direct[1] if direct else None
    expected_commit = direct[2] if direct else None
    source_path = _existing_source(
        source,
        expected_commit=expected_commit,
        direct_url=direct_url,
    )
    repository_url = repository or direct_url or _DEFAULT_REPOSITORY
    selected_revision = revision or requested_revision or expected_commit or _DEFAULT_REVISION

    if dry_run:
        if source_path is not None:
            source_description = str(source_path)
        else:
            source_description = f"{repository_url} @ {selected_revision}"
        print(f"Would build source: {source_description}")
        print(f"Would create image: {output_path}")
        return output_path

    _runtime_executable()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if source_path is not None:
        script = source_path / "container" / "build-tetracorder6.sh"
        _run(["bash", str(script), str(output_path)], cwd=source_path)
    else:
        with _cloned_source(
            repository_url,
            selected_revision,
            expected_commit,
        ) as cloned:
            script = cloned / "container" / "build-tetracorder6.sh"
            _run(["bash", str(script), str(output_path)], cwd=cloned)

    if not output_path.is_file():
        raise RuntimeSetupError(
            f"container build completed without creating {output_path}"
        )
    if verify:
        _run([_runtime_executable(), "test", str(output_path)])
    return output_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tetracorderpy setup",
        description="Reuse or build the shared Tetracorder 6.00a5 SIF on PSC.",
    )
    parser.add_argument("--source", type=Path, help="existing source checkout")
    parser.add_argument("--output", type=Path, help="new SIF output path")
    parser.add_argument("--repository", help="Git repository used if cloning is needed")
    parser.add_argument("--revision", help="Git branch, tag, or commit to clone")
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="do not run `apptainer test` after locating or building the image",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show the selected source and output without cloning or building",
    )
    return parser


def setup_main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        image = setup_runtime(
            source=args.source,
            output=args.output,
            repository=args.repository,
            revision=args.revision,
            verify=not args.no_verify,
            dry_run=args.dry_run,
        )
    except RuntimeSetupError as exc:
        print(f"tetracorderpy setup: {exc}", file=sys.stderr)
        return 1
    if not args.dry_run:
        print(f"Tetracorder image ready: {image}")
    return 0
