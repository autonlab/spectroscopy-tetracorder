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


# Native response grids used by shared PSC products and the synthetic tutorial.
# Paths are relative to the official repository checkout. Scale factors convert
# each ASCII source to micrometers before constructing a SpectralProfile.
_PROFILE_RESPONSES: dict[
    str,
    tuple[str, str, float, float, str],
] = {
    "aviris_1995": (
        "sl1/usgs/library06.conv/waves.txt",
        "sl1/usgs/library06.conv/resol.txt",
        1.0,
        1.0,
        "USGS s06av95a calibration records",
    ),
    "aviris_2024": (
        "sl1/usgs/library06.conv/waves.ascii.files/aviris-classic-2024-waves.txt",
        "sl1/usgs/library06.conv/waves.ascii.files/aviris-classic-2024-fwhm.txt",
        1.0,
        1.0,
        "USGS AVIRIS Classic 2024 response tables",
    ),
    "emit_c": (
        "sl1/usgs/library06.conv/waves.ascii.files/waves-emit_wl_20220813.txt",
        "sl1/usgs/library06.conv/waves.ascii.files/resol-emit_fwhm_20220813.txt",
        1.0,
        1.0,
        "USGS EMIT-C 2022 response tables",
    ),
    "aviris5_2025": (
        "sl1/usgs/library06.conv/waves.ascii.files/aviris-5-2025_waves.txt",
        "sl1/usgs/library06.conv/waves.ascii.files/aviris-5-2025_fwhm-nm.txt",
        1.0,
        1.0e-3,
        "USGS AVIRIS-5 2025 response tables",
    ),
}


def repository_root() -> Path:
    """Return the source checkout containing the installed package."""

    return Path(__file__).resolve().parent.parent


def _packaged_metadata_root() -> Traversable:
    return resources.files("tetracorderpy").joinpath("_data", "tetracorder6.00a")


def _dataset_directory() -> Traversable:
    source = (
        repository_root() / "tetracorder.cmds" / "tetracorder6.00a.cmds" / "DATASETS"
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


def _response_paths(
    profile_name: str,
) -> tuple[Path | Traversable, Path | Traversable, float, float, str] | None:
    specification = _PROFILE_RESPONSES.get(profile_name)
    if specification is None:
        return None
    wavelength_relative, fwhm_relative, wavelength_scale, fwhm_scale, source = (
        specification
    )
    checkout = repository_root()
    wavelength_path = checkout / wavelength_relative
    fwhm_path = checkout / fwhm_relative
    if wavelength_path.is_file() and fwhm_path.is_file():
        return wavelength_path, fwhm_path, wavelength_scale, fwhm_scale, source

    packaged = _packaged_metadata_root().joinpath("responses", profile_name)
    return (
        packaged.joinpath("wavelength.txt"),
        packaged.joinpath("fwhm.txt"),
        wavelength_scale,
        fwhm_scale,
        source,
    )


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

    Exact response arrays are packaged for selected profiles used by the
    Python tutorial and PSC shared datasets. Other native presets remain
    available by explicit name and validate their restart-file channel count.
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
    response = _response_paths(normalized)
    if response is not None:
        wavelength_path, fwhm_path, wavelength_scale, fwhm_scale, source = response
        if not wavelength_path.is_file() or not fwhm_path.is_file():
            raise UnsupportedProfileError(
                f"calibration metadata for profile {normalized!r} is missing"
            )
        with wavelength_path.open("r", encoding="ascii") as wavelength_stream:
            wavelength = (
                np.loadtxt(wavelength_stream, dtype=np.float64) * wavelength_scale
            )
        with fwhm_path.open("r", encoding="ascii") as fwhm_stream:
            fwhm = np.loadtxt(fwhm_stream, dtype=np.float64) * fwhm_scale
        if wavelength.ndim != 1 or fwhm.shape != wavelength.shape:
            raise UnsupportedProfileError(
                f"invalid calibration arrays for profile {normalized!r}"
            )
        if expected_bands is not None and wavelength.size != expected_bands:
            raise UnsupportedProfileError(
                f"profile {normalized!r} expects {expected_bands} bands but its "
                f"calibration contains {wavelength.size}"
            )
        return SpectralProfile(
            normalized,
            backend_profile=normalized,
            backend_version=version,
            wavelength=wavelength,
            fwhm=fwhm,
            metadata={
                "source": source,
                "validation": "wavelength_and_fwhm",
            },
        )

    return SpectralProfile(
        normalized,
        backend_profile=normalized,
        backend_version=version,
        expected_bands=expected_bands,
        metadata={"validation": "band_count_only"},
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
        for known_name in _PROFILE_RESPONSES:
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
