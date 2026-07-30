"""Container discovery for source checkouts and installed PSC packages."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from .errors import BackendUnavailableError
from .profiles import repository_root

TETRACORDER_IMAGE_VERSION = "6.00a5"
PSC_SHARED_CONTAINER_ROOT = Path(
    "/ocean/projects/cis250251p/shared/containers/tetracorder"
)
PSC_SHARED_SOURCE_CHECKOUT = Path(
    "/ocean/projects/cis250251p/shared/repos/spectroscopy-tetracorder"
)


def default_shared_container() -> Path:
    """Return the stable PSC path for the supported image version."""

    version = TETRACORDER_IMAGE_VERSION
    return PSC_SHARED_CONTAINER_ROOT / version / f"tetracorder-{version}.sif"


def _images_in(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    if not path.is_dir():
        return
    for pattern in (
        "tetracorder6_*.sif",
        "tetracorder6*.sif",
        "tetracorder-6*.sif",
        "*/tetracorder-6*.sif",
    ):
        yield from sorted(path.glob(pattern), reverse=True)


def container_candidates() -> tuple[Path, ...]:
    """Return automatic SIF candidates in precedence order."""

    candidates: list[Path] = []
    environment_path = os.environ.get("TETRACORDER_CONTAINER")
    if environment_path:
        candidates.append(Path(environment_path).expanduser())

    search_path = os.environ.get("TETRACORDER_CONTAINER_PATH", "")
    for entry in search_path.split(os.pathsep):
        if entry:
            candidates.extend(_images_in(Path(entry).expanduser()))

    candidates.extend(_images_in(repository_root() / "container"))
    candidates.append(default_shared_container())
    candidates.extend(_images_in(PSC_SHARED_CONTAINER_ROOT))
    candidates.extend(_images_in(PSC_SHARED_SOURCE_CHECKOUT / "container"))
    return tuple(candidates)


def discover_container(explicit: str | Path | None = None) -> Path:
    """Locate a readable Tetracorder 6 SIF.

    An explicit argument always wins. Automatic discovery then checks the
    single-file environment override, a path-list override, a development
    checkout, and the shared PSC deployment locations.
    """

    candidates = (
        (Path(explicit).expanduser(),)
        if explicit is not None
        else container_candidates()
    )
    seen: set[Path] = set()
    searched: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        searched.append(candidate)
        if resolved.is_file():
            return resolved

    if explicit is not None:
        raise BackendUnavailableError(f"Tetracorder container not found: {explicit}")

    rendered = "\n".join(f"  - {path}" for path in searched[:12])
    if not rendered:
        rendered = "  - no candidate paths were configured"
    raise BackendUnavailableError(
        "no Tetracorder 6.00 SIF was found; pass container=, set "
        "TETRACORDER_CONTAINER, add a directory to "
        "TETRACORDER_CONTAINER_PATH, or run `tetracorderpy setup`.\n"
        f"Searched:\n{rendered}"
    )
