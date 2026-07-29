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


def test_exact_wavelength_grid_can_resolve_profile_automatically() -> None:
    profile = get_profile("aviris_1995")
    assert profile.wavelength is not None
    synthetic = np.full(profile.wavelength.shape, 0.5, dtype=np.float32)
    data = SpectralData(synthetic, profile.wavelength)

    resolved = resolve_profile(None, data)

    assert resolved.name == "aviris_1995"


def test_profile_rejects_wrong_band_count() -> None:
    data = SpectralData(np.full(10, 0.5), np.linspace(0.4, 0.9, 10))

    with pytest.raises(ProfileMismatchError, match="expects 224 bands"):
        resolve_profile("aviris_1995", data)


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(UnsupportedProfileError, match="not bundled"):
        get_profile("not_a_sensor")
