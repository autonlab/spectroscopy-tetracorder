"""Unified public analysis API."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Mapping

from numpy.typing import ArrayLike

from .backends.base import TetracorderBackend
from .backends.v600 import Tetracorder600Backend
from .errors import BackendUnavailableError, SpectralDataError
from .models import AnalysisResult, SpectralData, SpectralProfile
from .profiles import resolve_profile


def _make_backend(
    version: str,
    *,
    container: str | Path | None,
    runtime: str | Path | None,
) -> TetracorderBackend:
    if version == "6.00":
        return Tetracorder600Backend(container=container, runtime=runtime)
    raise BackendUnavailableError(
        f"no Python backend is implemented for Tetracorder {version!r}"
    )


def _coerce_data(
    data: SpectralData | ArrayLike,
    *,
    wavelength: ArrayLike | None,
    fwhm: ArrayLike | float | None,
    mask: ArrayLike | None,
    spectral_axis: int,
    wavelength_unit: str,
    dims: tuple[str, ...] | None,
    coords: Mapping[str, Any] | None,
    metadata: Mapping[str, Any] | None,
) -> SpectralData:
    if isinstance(data, SpectralData):
        conflicting = {
            "wavelength": wavelength,
            "fwhm": fwhm,
            "mask": mask,
            "dims": dims,
            "coords": coords,
            "metadata": metadata,
        }
        supplied = [name for name, value in conflicting.items() if value is not None]
        if supplied or spectral_axis != -1 or wavelength_unit != "um":
            names = ", ".join(supplied or ["spectral_axis/wavelength_unit"])
            raise SpectralDataError(
                f"{names} must be supplied when constructing SpectralData, "
                "not again to analyze()"
            )
        return data
    if wavelength is None:
        raise SpectralDataError(
            "wavelength= is required when analyzing a raw array"
        )
    return SpectralData(
        data,
        wavelength,
        fwhm=fwhm,
        mask=mask,
        spectral_axis=spectral_axis,
        dims=dims,
        coords=coords,
        metadata=metadata,
        wavelength_unit=wavelength_unit,
    )


def _prepare_output_directory(path: str | Path) -> Path:
    output = Path(path).expanduser().resolve()
    if output.exists():
        if not output.is_dir():
            raise NotADirectoryError(f"output_dir is not a directory: {output}")
        if any(output.iterdir()):
            raise FileExistsError(
                f"output_dir must be empty to avoid overwriting artifacts: {output}"
            )
    else:
        output.mkdir(parents=True)
    return output


def analyze(
    data: SpectralData | ArrayLike,
    *,
    wavelength: ArrayLike | None = None,
    fwhm: ArrayLike | float | None = None,
    mask: ArrayLike | None = None,
    spectral_axis: int = -1,
    wavelength_unit: str = "um",
    dims: tuple[str, ...] | None = None,
    coords: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    profile: str | SpectralProfile | None = None,
    version: str = "6.00",
    container: str | Path | None = None,
    runtime: str | Path | None = None,
    output_dir: str | Path | None = None,
    timeout: float = 300.0,
    backend: TetracorderBackend | None = None,
) -> AnalysisResult:
    """Analyze one spectrum or a tensor of spectra in one native cube run.

    Raw arrays may have shape (bands,), (samples, bands), (y, x, bands), or
    arbitrary leading dimensions. The final axis is spectral unless changed
    with spectral_axis. All spectra in one call must share the same wavelength
    and FWHM arrays.
    """

    spectral_data = _coerce_data(
        data,
        wavelength=wavelength,
        fwhm=fwhm,
        mask=mask,
        spectral_axis=spectral_axis,
        wavelength_unit=wavelength_unit,
        dims=dims,
        coords=coords,
        metadata=metadata,
    )
    resolved_profile = resolve_profile(profile, spectral_data, version=version)
    selected_backend = backend or _make_backend(
        version,
        container=container,
        runtime=runtime,
    )
    if selected_backend.version != version:
        raise BackendUnavailableError(
            f"backend version {selected_backend.version!r} does not match "
            f"requested version {version!r}"
        )

    if output_dir is not None:
        work_dir = _prepare_output_directory(output_dir)
        result = selected_backend.analyze(
            spectral_data,
            resolved_profile,
            work_dir=work_dir,
            timeout=timeout,
        )
        result.artifacts_path = work_dir
        return result

    with tempfile.TemporaryDirectory(prefix="tetracorderpy-") as temporary:
        result = selected_backend.analyze(
            spectral_data,
            resolved_profile,
            work_dir=Path(temporary),
            timeout=timeout,
        )
    result.artifacts_path = None
    return result
