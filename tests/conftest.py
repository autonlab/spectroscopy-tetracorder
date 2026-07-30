from __future__ import annotations

import numpy as np
import pytest


def made_up_reflectance(
    wavelength: np.ndarray,
    *,
    offset: float = 0.0,
) -> np.ndarray:
    """Return a smooth, plausible-looking but entirely synthetic spectrum."""

    wavelength = np.asarray(wavelength, dtype=np.float64)
    span = np.ptp(wavelength)
    continuum = 0.52 + 0.06 * (wavelength - wavelength.min()) / span
    ripple = 0.008 * np.sin(11.0 * wavelength + offset)
    absorption = np.zeros_like(wavelength)
    for center, depth, width in ((0.92, 0.09, 0.055), (2.20, 0.14, 0.035)):
        absorption += depth * np.exp(-0.5 * ((wavelength - center) / width) ** 2)
    return np.clip(continuum + ripple - absorption, 0.02, 0.98).astype(np.float32)


@pytest.fixture
def synthetic_spectrum() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    wavelength = np.linspace(0.4, 2.5, 64, dtype=np.float64)
    fwhm = np.full(64, 0.9 * np.diff(wavelength).mean(), dtype=np.float64)
    return made_up_reflectance(wavelength), wavelength, fwhm
