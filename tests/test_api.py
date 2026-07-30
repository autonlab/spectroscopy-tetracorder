from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from tetracorderpy import (
    AnalysisResult,
    Decision,
    Material,
    SpectralData,
    SpectralDataError,
    SpectralProfile,
    analyze,
)
from tetracorderpy.backends.base import BackendCapabilities


class FakeBackend:
    version = "6.00"
    capabilities = BackendCapabilities(max_bands=710, max_samples_per_line=32765)

    def __init__(self) -> None:
        self.work_dir: Path | None = None
        self.data: SpectralData | None = None

    def analyze(
        self,
        data: SpectralData,
        profile: SpectralProfile,
        *,
        work_dir: Path,
        timeout: float,
    ) -> AnalysisResult:
        self.work_dir = work_dir
        self.data = data
        work_dir.mkdir(parents=True, exist_ok=True)
        (work_dir / "backend-marker").write_text("ran\n", encoding="ascii")
        decision = Decision("group", 1, "synthetic-feature")
        shape = data.sample_shape + (1,)
        return AnalysisResult(
            material_id=np.full(shape, 41, dtype=np.int32),
            fit=np.full(shape, 0.8, dtype=np.float32),
            depth=np.full(shape, 0.2, dtype=np.float32),
            fit_depth=np.full(shape, 0.16, dtype=np.float32),
            matched=np.ones(shape, dtype=np.bool_),
            decisions=(decision,),
            materials={41: Material(41, "made_up_material")},
            sample_shape=data.sample_shape,
            profile=profile,
            backend_version=self.version,
            provenance={"timeout": timeout},
        )


def _profile(bands: int) -> SpectralProfile:
    return SpectralProfile(
        "synthetic",
        backend_profile="synthetic",
        expected_bands=bands,
    )


@pytest.mark.parametrize("sample_shape", [(), (4,), (2, 3), (2, 1, 3)])
def test_one_api_preserves_any_leading_tensor_shape(
    sample_shape: tuple[int, ...],
    synthetic_spectrum: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    spectrum, wavelength, fwhm = synthetic_spectrum
    values = np.broadcast_to(spectrum, sample_shape + spectrum.shape).copy()
    backend = FakeBackend()

    result = analyze(
        values,
        wavelength=wavelength,
        fwhm=fwhm,
        profile=_profile(wavelength.size),
        backend=backend,
    )

    assert backend.data is not None
    assert backend.data.sample_shape == sample_shape
    assert result.sample_shape == sample_shape
    assert result.shape == sample_shape + (1,)
    assert result.material_name(41) == "made_up_material"
    assert result.artifacts_path is None


def test_default_artifacts_are_temporary(
    synthetic_spectrum: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    spectrum, wavelength, _ = synthetic_spectrum
    backend = FakeBackend()

    analyze(
        spectrum,
        wavelength=wavelength,
        profile=_profile(wavelength.size),
        backend=backend,
    )

    assert backend.work_dir is not None
    assert not backend.work_dir.exists()


def test_output_dir_retains_native_artifacts(
    tmp_path: Path,
    synthetic_spectrum: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    spectrum, wavelength, _ = synthetic_spectrum
    backend = FakeBackend()
    output = tmp_path / "native-output"

    result = analyze(
        spectrum,
        wavelength=wavelength,
        profile=_profile(wavelength.size),
        output_dir=output,
        backend=backend,
    )

    assert result.artifacts_path == output.resolve()
    assert (output / "backend-marker").read_text(encoding="ascii") == "ran\n"


def test_nonempty_output_dir_is_not_overwritten(
    tmp_path: Path,
    synthetic_spectrum: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    spectrum, wavelength, _ = synthetic_spectrum
    output = tmp_path / "occupied"
    output.mkdir()
    (output / "owned-by-user").write_text("keep", encoding="ascii")

    with pytest.raises(FileExistsError, match="must be empty"):
        analyze(
            spectrum,
            wavelength=wavelength,
            profile=_profile(wavelength.size),
            output_dir=output,
            backend=FakeBackend(),
        )


def test_input_labels_are_carried_to_the_result(
    synthetic_spectrum: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    spectrum, wavelength, _ = synthetic_spectrum
    values = np.broadcast_to(spectrum, (2, spectrum.size)).copy()
    data = SpectralData(
        values,
        wavelength,
        dims=("sample", "band"),
        coords={"flight_line": "synthetic-01"},
        metadata={"processing_level": "made-up reflectance"},
    )

    result = analyze(
        data,
        profile=_profile(wavelength.size),
        backend=FakeBackend(),
    )

    assert result.dims == ("sample", "decision")
    assert result.coords == {"flight_line": "synthetic-01"}
    assert result.input_metadata == {"processing_level": "made-up reflectance"}
    with pytest.raises(TypeError):
        result.coords["flight_line"] = "changed"  # type: ignore[index]


def test_temporary_work_can_use_an_explicit_scratch_parent(
    tmp_path: Path,
    synthetic_spectrum: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    spectrum, wavelength, _ = synthetic_spectrum
    backend = FakeBackend()
    scratch = tmp_path / "job-scratch"

    result = analyze(
        spectrum,
        wavelength=wavelength,
        profile=_profile(wavelength.size),
        scratch_dir=scratch,
        backend=backend,
    )

    assert backend.work_dir is not None
    assert backend.work_dir.parent == scratch.resolve()
    assert not backend.work_dir.exists()
    assert list(scratch.iterdir()) == []
    assert result.artifacts_path is None


def test_spectral_data_metadata_cannot_be_resupplied(
    synthetic_spectrum: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    spectrum, wavelength, _ = synthetic_spectrum
    data = SpectralData(spectrum, wavelength)

    with pytest.raises(SpectralDataError, match="not again"):
        analyze(
            data,
            wavelength=wavelength,
            profile=_profile(wavelength.size),
            backend=FakeBackend(),
        )


def test_retained_output_and_temporary_scratch_are_mutually_exclusive(
    tmp_path: Path,
    synthetic_spectrum: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    spectrum, wavelength, _ = synthetic_spectrum

    with pytest.raises(ValueError, match="cannot be combined"):
        analyze(
            spectrum,
            wavelength=wavelength,
            profile=_profile(wavelength.size),
            output_dir=tmp_path / "retained",
            scratch_dir=tmp_path / "temporary",
            backend=FakeBackend(),
        )
