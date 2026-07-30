from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from tetracorderpy import analyze, get_profile


pytestmark = pytest.mark.integration


def _synthetic_aviris_reflectance(wavelength: np.ndarray) -> np.ndarray:
    """Create a plausible curve without copying any reference-library spectrum."""

    wavelength = np.asarray(wavelength, dtype=np.float64)
    continuum = 0.47 + 0.07 * (wavelength - wavelength.min()) / np.ptp(wavelength)
    reflectance = continuum + 0.006 * np.sin(15.0 * wavelength)
    for center, depth, width in (
        (0.66, 0.025, 0.025),
        (0.92, 0.11, 0.065),
        (2.20, 0.13, 0.035),
        (2.33, 0.055, 0.030),
    ):
        reflectance -= depth * np.exp(
            -0.5 * ((wavelength - center) / width) ** 2
        )
    return np.clip(reflectance, 0.02, 0.98).astype(np.float32)


def _documented_quickstart_reflectance(wavelength: np.ndarray) -> np.ndarray:
    """Reproduce the exact spectrum published in the documentation."""

    wavelength = np.asarray(wavelength, dtype=np.float64)
    continuum = 0.47 + 0.07 * (
        (wavelength - wavelength.min()) / np.ptp(wavelength)
    )
    reflectance = continuum.copy()
    for center, depth, width in (
        (0.92, 0.11, 0.065),
        (2.20, 0.13, 0.035),
        (2.33, 0.055, 0.030),
    ):
        reflectance -= depth * np.exp(
            -0.5 * ((wavelength - center) / width) ** 2
        )
    return np.clip(reflectance, 0.02, 0.98).astype(np.float32)


def test_numpy_generated_spectrum_runs_through_tetracorder_600(
    tmp_path: Path,
) -> None:
    if os.environ.get("TETRACORDER_RUN_INTEGRATION") != "1":
        pytest.skip("set TETRACORDER_RUN_INTEGRATION=1 to run the container")

    profile = get_profile("aviris_1995")
    assert profile.wavelength is not None
    spectrum = _synthetic_aviris_reflectance(profile.wavelength)
    output_dir = tmp_path / "native"

    result = analyze(
        spectrum,
        wavelength=profile.wavelength,
        fwhm=profile.fwhm,
        profile=profile,
        output_dir=output_dir,
        timeout=900.0,
    )

    assert result.sample_shape == ()
    assert result.decisions
    assert len(result.decisions) == 45
    assert result.shape == (len(result.decisions),)
    assert result.matched.any()
    assert result.material_id.dtype == np.int32
    assert result.fit.dtype == np.float32
    assert result.depth.dtype == np.float32
    assert result.fit_depth.dtype == np.float32
    assert result.matched.dtype == np.bool_
    assert np.all(np.isfinite(result.fit))
    assert np.all((result.fit >= 0.0) & (result.fit <= 1.0))
    assert result.artifacts_path == output_dir.resolve()
    assert (output_dir / "run" / "tetracorder.out").is_file()


def test_documented_quickstart_has_expected_600a5_output() -> None:
    if os.environ.get("TETRACORDER_RUN_INTEGRATION") != "1":
        pytest.skip("set TETRACORDER_RUN_INTEGRATION=1 to run the container")

    profile = get_profile("aviris_1995")
    assert profile.wavelength is not None
    spectrum = _documented_quickstart_reflectance(profile.wavelength)

    result = analyze(
        spectrum,
        wavelength=profile.wavelength,
        fwhm=profile.fwhm,
        profile=profile,
        timeout=900.0,
    )

    expected = {
        ("group", 1): (
            117,
            "fe2+fe3+_water_RTsludge",
            0.847059,
            0.207843,
            0.176471,
        ),
        ("group", 2): (
            196,
            "micagrp_muscovite-low-Al",
            0.956863,
            0.170588,
            0.162745,
        ),
        ("group", 4): (
            385,
            "g4-fe2+generic_nrw.cummingtonite",
            0.607843,
            0.137255,
            0.084314,
        ),
    }
    matched_indices = np.flatnonzero(result.matched)

    assert result.shape == (45,)
    assert matched_indices.size == len(expected)
    assert result.provenance["native_lines"] == 1
    assert result.provenance["native_samples"] == 1
    assert result.provenance["input_spectra"] == 1
    assert result.provenance["padded_spectra"] == 0

    for index in matched_indices:
        decision = result.decisions[index]
        key = (decision.kind, decision.number)
        assert key in expected
        material_id, name, fit, depth, fit_depth = expected[key]
        assert int(result.material_id[index]) == material_id
        assert result.material_name(material_id) == name
        assert float(result.fit[index]) == pytest.approx(fit, abs=1.0e-6)
        assert float(result.depth[index]) == pytest.approx(depth, abs=1.0e-6)
        assert float(result.fit_depth[index]) == pytest.approx(
            fit_depth, abs=1.0e-6
        )


def test_numpy_generated_cube_runs_as_one_native_batch(
    tmp_path: Path,
) -> None:
    if os.environ.get("TETRACORDER_RUN_INTEGRATION") != "1":
        pytest.skip("set TETRACORDER_RUN_INTEGRATION=1 to run the container")

    profile = get_profile("aviris_1995")
    assert profile.wavelength is not None
    base = _synthetic_aviris_reflectance(profile.wavelength)
    offsets = np.linspace(-0.015, 0.015, 6, dtype=np.float32).reshape(2, 3, 1)
    cube = np.clip(base[None, None, :] + offsets, 0.02, 0.98)
    output_dir = tmp_path / "native-cube"

    result = analyze(
        cube,
        wavelength=profile.wavelength,
        fwhm=profile.fwhm,
        profile=profile,
        output_dir=output_dir,
        timeout=900.0,
    )

    assert result.sample_shape == (2, 3)
    assert result.shape == (2, 3, 45)
    assert result.provenance["input_spectra"] == 6
    assert result.provenance["native_lines"] == 2
    assert result.provenance["native_samples"] == 3
    assert result.provenance["padded_spectra"] == 0
    assert np.all(np.isfinite(result.fit))
    assert (output_dir / "runner.log").is_file()
