from __future__ import annotations

import numpy as np
import pytest

from tetracorderpy import (
    ProfileMismatchError,
    SpectralData,
    SpectralDataError,
    SpectralProfile,
)


def test_spectral_data_canonicalizes_axis_units_and_mask(
    synthetic_spectrum: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    spectrum, wavelength_um, _ = synthetic_spectrum
    values = np.stack((spectrum, spectrum + 0.01, spectrum - 0.01), axis=1)
    mask = np.zeros_like(values, dtype=bool)
    mask[10, 1] = True

    data = SpectralData(
        values,
        wavelength_um * 1000.0,
        fwhm=10.0,
        mask=mask,
        spectral_axis=0,
        dims=("band", "sample"),
        wavelength_unit="nm",
    )

    assert data.values.shape == (3, 64)
    assert data.sample_shape == (3,)
    assert data.bands == 64
    assert data.spectra == 3
    assert data.dims == ("sample", "band")
    np.testing.assert_allclose(data.wavelength, wavelength_um)
    np.testing.assert_allclose(data.fwhm, 0.01)
    assert data.invalid_mask()[1, 10]


def test_nonfinite_values_are_invalid(
    synthetic_spectrum: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    spectrum, wavelength, _ = synthetic_spectrum
    spectrum = spectrum.copy()
    spectrum[3] = np.nan
    spectrum[7] = np.inf

    invalid = SpectralData(spectrum, wavelength).invalid_mask()

    assert invalid.sum() == 2
    assert invalid[3]
    assert invalid[7]


@pytest.mark.parametrize(
    ("wavelength", "message"),
    [
        ([0.5, np.nan], "finite"),
        ([0.5, 0.0], "positive"),
        ([0.4], "bands"),
    ],
)
def test_rejects_invalid_wavelength_metadata(
    wavelength: list[float],
    message: str,
) -> None:
    with pytest.raises(SpectralDataError, match=message):
        SpectralData(np.ones(2), wavelength)


def test_rejects_non_reflectance_quantity(
    synthetic_spectrum: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    spectrum, wavelength, _ = synthetic_spectrum
    with pytest.raises(SpectralDataError, match="reflectance"):
        SpectralData(spectrum, wavelength, quantity="radiance")


def test_profile_validates_band_count_and_wavelength(
    synthetic_spectrum: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    spectrum, wavelength, fwhm = synthetic_spectrum
    data = SpectralData(spectrum, wavelength, fwhm=fwhm)
    exact = SpectralProfile(
        "synthetic",
        wavelength=wavelength,
        fwhm=fwhm,
        backend_profile="synthetic",
    )
    exact.validate(data)

    wrong = SpectralProfile(
        "wrong",
        wavelength=wavelength + 0.002,
        backend_profile="wrong",
    )
    with pytest.raises(ProfileMismatchError, match="wavelengths"):
        wrong.validate(data)
