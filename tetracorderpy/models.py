"""Python-native spectral input and Tetracorder result models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .errors import ProfileMismatchError, SpectralDataError

_WAVELENGTH_FACTORS_TO_UM = {
    "um": 1.0,
    "micron": 1.0,
    "microns": 1.0,
    "micrometer": 1.0,
    "micrometers": 1.0,
    "µm": 1.0,
    "nm": 1.0e-3,
    "nanometer": 1.0e-3,
    "nanometers": 1.0e-3,
}


def _as_micrometers(
    values: ArrayLike,
    unit: str,
    *,
    name: str,
) -> NDArray[np.float64]:
    normalized_unit = unit.strip().lower()
    try:
        factor = _WAVELENGTH_FACTORS_TO_UM[normalized_unit]
    except KeyError as exc:
        supported = ", ".join(sorted(_WAVELENGTH_FACTORS_TO_UM))
        raise SpectralDataError(
            f"unsupported {name} unit {unit!r}; supported units are {supported}"
        ) from exc

    result = np.asarray(values, dtype=np.float64)
    return result * factor


def _normalize_axis(axis: int, ndim: int) -> int:
    try:
        normalized = int(axis)
    except (TypeError, ValueError) as exc:
        raise SpectralDataError(
            f"spectral_axis must be an integer, got {axis!r}"
        ) from exc
    if normalized < 0:
        normalized += ndim
    if normalized < 0 or normalized >= ndim:
        raise SpectralDataError(
            f"spectral_axis {axis!r} is invalid for a {ndim}-dimensional array"
        )
    return normalized


@dataclass(frozen=True, slots=True)
class SpectralData:
    """A reflectance tensor with a shared spectral coordinate.

    Values are stored with the spectral axis last. Wavelengths and FWHM are
    canonicalized to micrometers. Leading axes may represent samples, a
    spatial grid, or any other collection of spectra.
    """

    values: NDArray[np.generic]
    wavelength: NDArray[np.float64]
    fwhm: NDArray[np.float64] | None = None
    mask: NDArray[np.bool_] | None = None
    dims: tuple[str, ...] | None = None
    coords: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    quantity: str = "reflectance"
    wavelength_unit: str = "um"

    def __init__(
        self,
        values: ArrayLike,
        wavelength: ArrayLike,
        *,
        fwhm: ArrayLike | float | None = None,
        mask: ArrayLike | None = None,
        spectral_axis: int = -1,
        dims: tuple[str, ...] | None = None,
        coords: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        quantity: str = "reflectance",
        wavelength_unit: str = "um",
    ) -> None:
        array = np.asanyarray(values)
        if array.ndim < 1:
            raise SpectralDataError("spectral values must have at least one dimension")
        if not np.issubdtype(array.dtype, np.number) or np.iscomplexobj(array):
            raise SpectralDataError("spectral values must be real numeric data")

        axis = _normalize_axis(spectral_axis, array.ndim)
        if axis != array.ndim - 1:
            array = np.moveaxis(array, axis, -1)

        wave = _as_micrometers(wavelength, wavelength_unit, name="wavelength")
        if wave.ndim != 1:
            raise SpectralDataError("wavelength must be a one-dimensional array")
        if wave.size != array.shape[-1]:
            raise SpectralDataError(
                f"wavelength has {wave.size} bands but values have {array.shape[-1]}"
            )
        if wave.size == 0:
            raise SpectralDataError("a spectrum must contain at least one band")
        if not np.all(np.isfinite(wave)):
            raise SpectralDataError("wavelength must contain only finite values")
        if not np.all(wave > 0.0):
            raise SpectralDataError("wavelength values must be positive")

        width: NDArray[np.float64] | None
        if fwhm is None:
            width = None
        else:
            raw_width = np.asarray(fwhm, dtype=np.float64)
            if raw_width.ndim == 0:
                raw_width = np.full(wave.shape, raw_width.item(), dtype=np.float64)
            width = _as_micrometers(raw_width, wavelength_unit, name="FWHM")
            if width.ndim != 1 or width.size != wave.size:
                raise SpectralDataError(
                    "fwhm must be a scalar or a one-dimensional array matching wavelength"
                )
            if not np.all(np.isfinite(width)) or not np.all(width > 0.0):
                raise SpectralDataError("fwhm values must be finite and positive")

        normalized_mask: NDArray[np.bool_] | None
        if mask is None:
            normalized_mask = None
        else:
            raw_mask = np.asarray(mask, dtype=np.bool_)
            if raw_mask.ndim == array.ndim and axis != array.ndim - 1:
                raw_mask = np.moveaxis(raw_mask, axis, -1)
            try:
                normalized_mask = np.broadcast_to(raw_mask, array.shape)
            except ValueError as exc:
                raise SpectralDataError(
                    f"mask shape {raw_mask.shape} is not broadcastable "
                    f"to values {array.shape}"
                ) from exc

        normalized_dims = dims
        if dims is not None:
            if len(dims) != array.ndim:
                raise SpectralDataError(
                    f"dims has {len(dims)} entries but values have "
                    f"{array.ndim} dimensions"
                )
            if len(set(dims)) != len(dims):
                raise SpectralDataError("dimension names must be unique")
            if axis != array.ndim - 1:
                dims_list = list(dims)
                spectral_name = dims_list.pop(axis)
                dims_list.append(spectral_name)
                normalized_dims = tuple(dims_list)

        normalized_quantity = quantity.strip().lower()
        if normalized_quantity != "reflectance":
            raise SpectralDataError(
                f"Tetracorder analysis currently accepts reflectance, not {quantity!r}"
            )

        object.__setattr__(self, "values", array)
        object.__setattr__(self, "wavelength", wave)
        object.__setattr__(self, "fwhm", width)
        object.__setattr__(self, "mask", normalized_mask)
        object.__setattr__(self, "dims", normalized_dims)
        object.__setattr__(self, "coords", MappingProxyType(dict(coords or {})))
        object.__setattr__(self, "metadata", MappingProxyType(dict(metadata or {})))
        object.__setattr__(self, "quantity", normalized_quantity)
        object.__setattr__(self, "wavelength_unit", "um")

    @property
    def sample_shape(self) -> tuple[int, ...]:
        """The shape excluding the spectral axis."""

        return self.values.shape[:-1]

    @property
    def bands(self) -> int:
        """Number of spectral bands."""

        return self.values.shape[-1]

    @property
    def spectra(self) -> int:
        """Total number of spectra in the tensor."""

        return (
            int(np.prod(self.sample_shape, dtype=np.int64)) if self.sample_shape else 1
        )

    def invalid_mask(self) -> NDArray[np.bool_]:
        """Return the explicit mask combined with NaN and infinity detection."""

        invalid = ~np.isfinite(self.values)
        if self.mask is not None:
            invalid = np.logical_or(invalid, self.mask)
        return invalid


@dataclass(frozen=True, slots=True)
class SpectralProfile:
    """A spectral response paired with a backend-specific dataset preset."""

    name: str
    backend_profile: str | None = None
    backend_version: str = "6.00"
    wavelength: NDArray[np.float64] | None = None
    fwhm: NDArray[np.float64] | None = None
    expected_bands: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        name: str,
        *,
        backend_profile: str | None = None,
        backend_version: str = "6.00",
        wavelength: ArrayLike | None = None,
        fwhm: ArrayLike | float | None = None,
        expected_bands: int | None = None,
        wavelength_unit: str = "um",
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        normalized_name = name.strip()
        if not normalized_name:
            raise SpectralDataError("profile name must not be empty")

        wave: NDArray[np.float64] | None = None
        width: NDArray[np.float64] | None = None
        if wavelength is not None:
            wave = _as_micrometers(wavelength, wavelength_unit, name="wavelength")
            if wave.ndim != 1 or wave.size == 0:
                raise SpectralDataError("profile wavelength must be one-dimensional")
            if not np.all(np.isfinite(wave)) or not np.all(wave > 0.0):
                raise SpectralDataError(
                    "profile wavelengths must be finite and positive"
                )
            if expected_bands is not None and expected_bands != wave.size:
                raise SpectralDataError(
                    "expected_bands does not match profile wavelength length"
                )
            expected_bands = int(wave.size)

        if fwhm is not None:
            if wave is None:
                raise SpectralDataError("profile fwhm requires profile wavelength")
            raw_width = np.asarray(fwhm, dtype=np.float64)
            if raw_width.ndim == 0:
                raw_width = np.full(wave.shape, raw_width.item(), dtype=np.float64)
            width = _as_micrometers(raw_width, wavelength_unit, name="FWHM")
            if width.ndim != 1 or width.size != wave.size:
                raise SpectralDataError("profile fwhm must match profile wavelength")
            if not np.all(np.isfinite(width)) or not np.all(width > 0.0):
                raise SpectralDataError("profile fwhm must be finite and positive")

        if expected_bands is not None and expected_bands < 1:
            raise SpectralDataError("expected_bands must be positive")

        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "backend_profile", backend_profile or normalized_name)
        object.__setattr__(self, "backend_version", backend_version)
        object.__setattr__(self, "wavelength", wave)
        object.__setattr__(self, "fwhm", width)
        object.__setattr__(self, "expected_bands", expected_bands)
        object.__setattr__(self, "metadata", MappingProxyType(dict(metadata or {})))

    def validate(self, data: SpectralData, *, wavelength_atol: float = 1.0e-6) -> None:
        """Validate that *data* is compatible with this spectral profile."""

        if self.expected_bands is not None and data.bands != self.expected_bands:
            raise ProfileMismatchError(
                f"profile {self.name!r} expects {self.expected_bands} bands; "
                f"data have {data.bands}"
            )
        if self.wavelength is not None and not np.allclose(
            data.wavelength, self.wavelength, rtol=0.0, atol=wavelength_atol
        ):
            max_error = float(np.max(np.abs(data.wavelength - self.wavelength)))
            raise ProfileMismatchError(
                f"data wavelengths do not match profile {self.name!r}; "
                f"maximum difference is {max_error:.6g} um"
            )
        if (
            self.fwhm is not None
            and data.fwhm is not None
            and not np.allclose(data.fwhm, self.fwhm, rtol=0.0, atol=wavelength_atol)
        ):
            max_error = float(np.max(np.abs(data.fwhm - self.fwhm)))
            raise ProfileMismatchError(
                f"data FWHM does not match profile {self.name!r}; "
                f"maximum difference is {max_error:.6g} um"
            )


@dataclass(frozen=True, slots=True)
class Decision:
    """One Tetracorder group or conditional case in the result tensor."""

    kind: str
    number: int
    name: str


@dataclass(frozen=True, slots=True)
class Material:
    """Metadata for a Tetracorder material identifier."""

    id: int
    name: str


@dataclass(slots=True)
class AnalysisResult:
    """Compact, aligned arrays decoded from native Tetracorder output."""

    material_id: NDArray[np.int32]
    fit: NDArray[np.float32]
    depth: NDArray[np.float32]
    fit_depth: NDArray[np.float32]
    matched: NDArray[np.bool_]
    decisions: tuple[Decision, ...]
    materials: Mapping[int, Material]
    sample_shape: tuple[int, ...]
    profile: SpectralProfile
    backend_version: str
    dims: tuple[str, ...] | None = None
    coords: Mapping[str, Any] = field(default_factory=dict)
    input_metadata: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    artifacts_path: Path | None = None

    def __post_init__(self) -> None:
        expected_shape = self.sample_shape + (len(self.decisions),)
        arrays = {
            "material_id": self.material_id,
            "fit": self.fit,
            "depth": self.depth,
            "fit_depth": self.fit_depth,
            "matched": self.matched,
        }
        for name, array in arrays.items():
            if array.shape != expected_shape:
                raise ValueError(
                    f"{name} has shape {array.shape}; expected {expected_shape}"
                )
        if self.dims is not None and len(self.dims) != len(expected_shape):
            raise ValueError(
                f"dims has {len(self.dims)} entries; expected {len(expected_shape)}"
            )
        self.materials = MappingProxyType(dict(self.materials))
        self.coords = MappingProxyType(dict(self.coords))
        self.input_metadata = MappingProxyType(dict(self.input_metadata))
        self.provenance = MappingProxyType(dict(self.provenance))

    @property
    def shape(self) -> tuple[int, ...]:
        """Shape of each result variable, including the decision axis."""

        return self.material_id.shape

    def material_name(self, material_id: int) -> str | None:
        """Resolve a material identifier to its stable output name."""

        material = self.materials.get(int(material_id))
        return material.name if material is not None else None
