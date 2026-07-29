"""Spectral-profile discovery and validation."""

from __future__ import annotations

import re
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

import numpy as np

from .errors import ProfileMismatchError, UnsupportedProfileError
from .models import SpectralData, SpectralProfile


_SAFE_PROFILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]*$")


def repository_root() -> Path:
    """Return the source checkout containing the installed package."""

    return Path(__file__).resolve().parent.parent


def _packaged_metadata_root() -> Traversable:
    return resources.files("tetracorderpy").joinpath(
        "_data", "tetracorder6.00a"
    )


def _dataset_directory() -> Traversable:
    source = (
        repository_root()
        / "tetracorder.cmds"
        / "tetracorder6.00a.cmds"
        / "DATASETS"
    )
    if source.is_dir():
        return source
    return _packaged_metadata_root().joinpath("DATASETS")


def _restart_directory() -> Traversable:
    source = (
        repository_root()
        / "tetracorder.cmds"
        / "tetracorder6.00a.cmds"
        / "restart_files"
    )
    if source.is_dir():
        return source
    return _packaged_metadata_root().joinpath("restart_files")


def _response_directory() -> Traversable:
    source = repository_root() / "sl1" / "usgs" / "library06.conv"
    if (source / "waves.txt").is_file() and (source / "resol.txt").is_file():
        return source
    return _packaged_metadata_root().joinpath("aviris_1995")


def _read_ascii(path: Traversable) -> str:
    with path.open("r", encoding="ascii", errors="ignore") as stream:
        return stream.read()


def available_profiles(*, version: str = "6.00") -> tuple[str, ...]:
    """List dataset presets bundled with the local Tetracorder checkout."""

    if version != "6.00":
        return ()
    dataset_dir = _dataset_directory()
    if not dataset_dir.is_dir():
        return ()
    return tuple(
        sorted(
            path.name
            for path in dataset_dir.iterdir()
            if path.is_file() and path.name != "AAA.readme.txt"
        )
    )


def _expected_bands(profile_name: str) -> int | None:
    dataset_path = _dataset_directory().joinpath(profile_name)
    if not dataset_path.is_file():
        return None
    dataset_text = _read_ascii(dataset_path)
    restart_match = re.search(r"^restart=\s+(\S+)", dataset_text, re.MULTILINE)
    if restart_match is None:
        return None
    restart_path = _restart_directory().joinpath(restart_match.group(1))
    if not restart_path.is_file():
        return None
    restart_text = _read_ascii(restart_path)
    bands_match = re.search(r"^nchans=\s*(\d+)", restart_text, re.MULTILINE)
    return int(bands_match.group(1)) if bands_match is not None else None


def profile_deleted_value(profile_name: str) -> float:
    """Return the native deleted-point marker for a dataset preset."""

    dataset_path = _dataset_directory().joinpath(profile_name)
    if dataset_path.is_file():
        match = re.search(
            r"^deletedpoint=\s*([-+0-9.eEdD]+)",
            _read_ascii(dataset_path),
            re.MULTILINE,
        )
        if match is not None:
            return float(match.group(1).replace("D", "E").replace("d", "e"))
    return -32767.0


def get_profile(name: str, *, version: str = "6.00") -> SpectralProfile:
    """Load metadata for a bundled profile.

    The AVIRIS-1995 calibration arrays are available as upstream ASCII files.
    Other bundled presets are still usable by explicit name and are validated
    by their restart-file channel count.
    """

    normalized = name.strip()
    if not _SAFE_PROFILE.fullmatch(normalized):
        raise UnsupportedProfileError(f"invalid profile name {name!r}")
    if version != "6.00":
        raise UnsupportedProfileError(
            f"profile discovery is not implemented for Tetracorder {version}"
        )

    profiles = available_profiles(version=version)
    if profiles and normalized not in profiles:
        raise UnsupportedProfileError(
            f"profile {normalized!r} is not bundled with Tetracorder {version}"
        )

    expected_bands = _expected_bands(normalized)
    if normalized == "aviris_1995":
        data_dir = _response_directory()
        wavelength_path = data_dir.joinpath("waves.txt")
        fwhm_path = data_dir.joinpath("resol.txt")
        if wavelength_path.is_file() and fwhm_path.is_file():
            with wavelength_path.open("r", encoding="ascii") as wavelength_stream:
                wavelength = np.loadtxt(wavelength_stream, dtype=np.float64)
            with fwhm_path.open("r", encoding="ascii") as fwhm_stream:
                fwhm = np.loadtxt(fwhm_stream, dtype=np.float64)
            if wavelength.size == 224 and fwhm.size == 224:
                return SpectralProfile(
                    normalized,
                    backend_profile=normalized,
                    backend_version=version,
                    wavelength=wavelength,
                    fwhm=fwhm,
                    metadata={"source": "USGS s06av95a calibration records"},
                )

    return SpectralProfile(
        normalized,
        backend_profile=normalized,
        backend_version=version,
        expected_bands=expected_bands,
    )


def resolve_profile(
    profile: str | SpectralProfile | None,
    data: SpectralData,
    *,
    version: str = "6.00",
) -> SpectralProfile:
    """Resolve and validate a profile for *data*."""

    resolved: SpectralProfile
    if isinstance(profile, SpectralProfile):
        resolved = profile
    elif isinstance(profile, str):
        resolved = get_profile(profile, version=version)
    elif profile is None:
        candidates: list[SpectralProfile] = []
        for known_name in ("aviris_1995",):
            try:
                candidate = get_profile(known_name, version=version)
                candidate.validate(data)
            except (UnsupportedProfileError, ProfileMismatchError):
                continue
            candidates.append(candidate)
        if len(candidates) != 1:
            raise UnsupportedProfileError(
                "no unique bundled profile matches this wavelength grid; "
                "pass profile= explicitly"
            )
        resolved = candidates[0]
    else:
        raise TypeError("profile must be a name, SpectralProfile, or None")

    if resolved.backend_version != version:
        raise UnsupportedProfileError(
            f"profile {resolved.name!r} targets Tetracorder "
            f"{resolved.backend_version}, not {version}"
        )
    if resolved.backend_profile is None:
        raise UnsupportedProfileError(
            f"profile {resolved.name!r} has no Tetracorder {version} dataset preset"
        )
    resolved.validate(data)
    return resolved
