from __future__ import annotations

import numpy as np
import pytest

from tetracorderpy import (
    ProfileMismatchError,
    SpectralData,
    UnsupportedProfileError,
    available_profiles,
    get_profile,
)
from tetracorderpy.profiles import resolve_profile


def test_bundled_600_profiles_are_discoverable() -> None:
    profiles = available_profiles()

    assert "aviris_1995" in profiles
    assert "emit_a" in profiles
    assert "prisma01a" in profiles


def test_aviris_1995_has_exact_response_arrays() -> None:
    profile = get_profile("aviris_1995")

    assert profile.backend_version == "6.00"
    assert profile.backend_profile == "aviris_1995"
    assert profile.wavelength is not None
    assert profile.fwhm is not None
    assert profile.wavelength.shape == (224,)
    assert profile.fwhm.shape == (224,)
    assert np.all(np.isfinite(profile.wavelength))
    assert np.all(profile.wavelength > 0)
    assert np.count_nonzero(np.diff(profile.wavelength) < 0) == 3


@pytest.mark.parametrize(
    ("name", "bands"),
    [
        ("aviris_1995", 224),
        ("aviris_2024", 224),
        ("emit_c", 285),
        ("aviris5_2025", 424),
    ],
)
def test_shared_profiles_have_exact_response_arrays(name: str, bands: int) -> None:
    profile = get_profile(name)

    assert profile.wavelength is not None
    assert profile.fwhm is not None
    assert profile.wavelength.shape == (bands,)
    assert profile.fwhm.shape == (bands,)
    assert np.all(np.isfinite(profile.wavelength))
    assert np.all(np.isfinite(profile.fwhm))
    assert np.all((profile.wavelength > 0.3) & (profile.wavelength < 3.0))
    assert np.all((profile.fwhm > 0.0) & (profile.fwhm < 0.02))
    assert profile.metadata["validation"] == "wavelength_and_fwhm"


@pytest.mark.parametrize("name", ["emit_c", "aviris5_2025"])
def test_exact_wavelength_grid_can_resolve_profile_automatically(name: str) -> None:
    profile = get_profile(name)
    assert profile.wavelength is not None
    synthetic = np.full(profile.wavelength.shape, 0.5, dtype=np.float32)
    data = SpectralData(synthetic, profile.wavelength)

    resolved = resolve_profile(None, data)

    assert resolved.name == name


@pytest.mark.parametrize("name", ["aviris_1995", "aviris_2024"])
def test_shared_aviris_grid_requires_explicit_profile(name: str) -> None:
    profile = get_profile(name)
    assert profile.wavelength is not None
    data = SpectralData(np.full(profile.wavelength.shape, 0.5), profile.wavelength)

    with pytest.raises(UnsupportedProfileError, match="no unique bundled profile"):
        resolve_profile(None, data)


def test_count_only_profile_is_labeled() -> None:
    profile = get_profile("prisma01a")

    assert profile.wavelength is None
    assert profile.metadata["validation"] == "band_count_only"


def test_profile_rejects_wrong_band_count() -> None:
    data = SpectralData(np.full(10, 0.5), np.linspace(0.4, 0.9, 10))

    with pytest.raises(ProfileMismatchError, match="expects 224 bands"):
        resolve_profile("aviris_1995", data)


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(UnsupportedProfileError, match="not bundled"):
        get_profile("not_a_sensor")


def test_tetracorder_527_is_not_a_supported_backend() -> None:
    assert available_profiles(version="5.27") == ()
    with pytest.raises(
        UnsupportedProfileError, match="not implemented for Tetracorder 5.27"
    ):
        get_profile("aviris_1995", version="5.27")
