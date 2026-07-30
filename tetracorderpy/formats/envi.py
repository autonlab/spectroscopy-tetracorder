"""Small, dependency-free ENVI reader/writer used by the wrapper."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..errors import SpectralDataError
from ..models import SpectralData

_ENVI_DTYPES = {
    1: np.dtype("u1"),
    2: np.dtype("i2"),
    3: np.dtype("i4"),
    4: np.dtype("f4"),
    5: np.dtype("f8"),
    6: np.dtype("c8"),
    9: np.dtype("c16"),
    12: np.dtype("u2"),
    13: np.dtype("u4"),
    14: np.dtype("i8"),
    15: np.dtype("u8"),
}

_ENVI_DATA_SUFFIXES = (".img", ".raw", ".dat", ".bil", ".bip", ".bsq")


def _header_and_data_paths(path: str | Path) -> tuple[Path, Path]:
    supplied = Path(path)
    if supplied.suffix.lower() == ".hdr":
        header_path = supplied
        stem_path = Path(str(supplied)[:-4])
        candidates = [stem_path]
        if stem_path.suffix.lower() == ".gz":
            candidates.append(stem_path.with_suffix(""))
        candidates.extend(
            Path(f"{stem_path}{suffix}") for suffix in _ENVI_DATA_SUFFIXES
        )
        existing = list(dict.fromkeys(p for p in candidates if p.is_file()))
        if stem_path in existing:
            data_path = stem_path
        elif len(existing) == 1:
            data_path = existing[0]
        elif len(existing) > 1:
            names = ", ".join(str(candidate) for candidate in existing)
            raise SpectralDataError(
                f"ENVI header {header_path} has multiple possible data files: {names}"
            )
        else:
            data_path = stem_path
    else:
        data_path = supplied
        direct_header = Path(f"{supplied}.hdr")
        sibling_header = supplied.with_suffix(".hdr")
        native_header = Path(f"{supplied}.gz.hdr")
        header_path = next(
            (
                candidate
                for candidate in dict.fromkeys(
                    (direct_header, sibling_header, native_header)
                )
                if candidate.is_file()
            ),
            direct_header,
        )
    return header_path, data_path


def _embedded_vicar_offset(data_path: Path) -> int | None:
    if not data_path.is_file():
        return None
    with data_path.open("rb") as stream:
        prefix = stream.read(128)
    match = re.match(rb"LBLSIZE\s*=\s*(\d+)", prefix)
    return int(match.group(1)) if match is not None else None


def _parse_envi_fields(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip().upper() != "ENVI":
        raise SpectralDataError("ENVI header must begin with 'ENVI'")

    fields: dict[str, str] = {}
    current_key: str | None = None
    current_value: list[str] = []
    brace_depth = 0

    for raw_line in lines[1:]:
        line = raw_line.strip()
        if not line:
            continue
        if current_key is None:
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            current_key = key.strip().lower()
            current_value = [value.strip()]
            brace_depth = value.count("{") - value.count("}")
        else:
            current_value.append(line)
            brace_depth += line.count("{") - line.count("}")

        if brace_depth <= 0:
            fields[current_key] = " ".join(current_value).strip()
            current_key = None
            current_value = []
            brace_depth = 0

    if current_key is not None:
        raise SpectralDataError(
            f"unterminated braced value for ENVI field {current_key!r}"
        )
    return fields


def _scalar(
    fields: Mapping[str, str], key: str, cast: type, default: Any = None
) -> Any:
    raw = fields.get(key)
    if raw is None:
        if default is not None:
            return default
        raise SpectralDataError(f"ENVI header is missing required field {key!r}")
    cleaned = raw.strip().strip("{}").strip()
    try:
        return cast(cleaned)
    except (TypeError, ValueError) as exc:
        raise SpectralDataError(f"invalid ENVI {key!r} value {raw!r}") from exc


def _numeric_list(raw: str | None) -> NDArray[np.float64] | None:
    if raw is None:
        return None
    cleaned = raw.strip().strip("{}").strip()
    if not cleaned:
        return np.empty(0, dtype=np.float64)
    try:
        return np.asarray(
            [float(part.strip()) for part in cleaned.split(",") if part.strip()],
            dtype=np.float64,
        )
    except ValueError as exc:
        raise SpectralDataError(f"invalid numeric ENVI list {raw!r}") from exc


@dataclass(frozen=True, slots=True)
class EnviHeader:
    """Parsed subset of an ENVI header."""

    samples: int
    lines: int
    bands: int
    header_offset: int
    data_type: int
    interleave: str
    byte_order: int
    fields: Mapping[str, str]
    header_path: Path
    data_path: Path

    @property
    def dtype(self) -> np.dtype:
        """NumPy dtype including the declared byte order."""

        try:
            base = _ENVI_DTYPES[self.data_type]
        except KeyError as exc:
            raise SpectralDataError(
                f"unsupported ENVI data type {self.data_type}"
            ) from exc
        if base.itemsize == 1:
            return base
        return base.newbyteorder("<" if self.byte_order == 0 else ">")


def read_envi_header(path: str | Path) -> EnviHeader:
    """Parse the ENVI sidecar associated with path."""

    header_path, data_path = _header_and_data_paths(path)
    if not header_path.is_file():
        raise FileNotFoundError(f"ENVI header not found: {header_path}")
    fields = _parse_envi_fields(
        header_path.read_text(encoding="ascii", errors="replace")
    )
    interleave = fields.get("interleave", "").strip().lower()
    if interleave not in {"bip", "bil", "bsq"}:
        raise SpectralDataError(f"unsupported ENVI interleave {interleave!r}")
    byte_order = _scalar(fields, "byte order", int, 0)
    if byte_order not in {0, 1}:
        raise SpectralDataError(f"unsupported ENVI byte order {byte_order}")

    declared_offset = _scalar(fields, "header offset", int, 0)
    embedded_offset = _embedded_vicar_offset(data_path)
    result = EnviHeader(
        samples=_scalar(fields, "samples", int),
        lines=_scalar(fields, "lines", int),
        bands=_scalar(fields, "bands", int),
        header_offset=(
            embedded_offset if embedded_offset is not None else declared_offset
        ),
        data_type=_scalar(fields, "data type", int),
        interleave=interleave,
        byte_order=byte_order,
        fields=MappingProxyType(fields),
        header_path=header_path,
        data_path=data_path,
    )
    if min(result.samples, result.lines, result.bands) < 1:
        raise SpectralDataError("ENVI samples, lines, and bands must be positive")
    if result.header_offset < 0:
        raise SpectralDataError("ENVI header offset must not be negative")
    return result


def read_envi_array(
    path: str | Path,
    *,
    mode: str = "r",
) -> tuple[NDArray[np.generic], EnviHeader]:
    """Memory-map an ENVI array as (lines, samples, bands)."""

    header = read_envi_header(path)
    if not header.data_path.is_file():
        raise FileNotFoundError(f"ENVI data file not found: {header.data_path}")

    required_bytes = (
        header.header_offset
        + header.lines * header.samples * header.bands * header.dtype.itemsize
    )
    actual_bytes = header.data_path.stat().st_size
    if actual_bytes < required_bytes:
        raise SpectralDataError(
            f"ENVI data file is truncated: expected at least {required_bytes} "
            f"bytes, found {actual_bytes}"
        )

    if header.interleave == "bip":
        storage_shape = (header.lines, header.samples, header.bands)
    elif header.interleave == "bil":
        storage_shape = (header.lines, header.bands, header.samples)
    else:
        storage_shape = (header.bands, header.lines, header.samples)

    mapped = np.memmap(
        header.data_path,
        dtype=header.dtype,
        mode=mode,
        offset=header.header_offset,
        shape=storage_shape,
        order="C",
    )
    if header.interleave == "bip":
        array = mapped
    elif header.interleave == "bil":
        array = mapped.transpose(0, 2, 1)
    else:
        array = mapped.transpose(1, 2, 0)
    return array, header


def read_envi(
    path: str | Path,
    *,
    wavelength: ArrayLike | None = None,
    fwhm: ArrayLike | float | None = None,
    wavelength_unit: str | None = None,
    apply_reflectance_scale: bool = True,
) -> SpectralData:
    """Read an ENVI cube into the canonical SpectralData model."""

    array, header = read_envi_array(path)
    header_wavelength = _numeric_list(header.fields.get("wavelength"))
    header_fwhm = _numeric_list(
        header.fields.get("fwhm") or header.fields.get("bandwidth")
    )
    resolved_wavelength = wavelength if wavelength is not None else header_wavelength
    resolved_fwhm = fwhm if fwhm is not None else header_fwhm
    if resolved_wavelength is None:
        raise SpectralDataError(
            "ENVI header has no wavelength list; pass wavelength= explicitly"
        )

    unit = wavelength_unit or header.fields.get("wavelength units", "um").strip().strip(
        "{}"
    )

    mask: NDArray[np.bool_] | None = None
    ignore_raw = header.fields.get("data ignore value")
    if ignore_raw is not None:
        ignore_value = _scalar(header.fields, "data ignore value", float)
        mask = np.asarray(array == ignore_value)

    values: NDArray[np.generic] = array
    scale = _scalar(header.fields, "reflectance scale factor", float, 1.0)
    if apply_reflectance_scale and scale not in {0.0, 1.0}:
        values = np.asarray(array, dtype=np.float32) / np.float32(scale)

    bad_bands = _numeric_list(header.fields.get("bbl"))
    if bad_bands is not None:
        if bad_bands.size != header.bands:
            raise SpectralDataError("ENVI bbl length does not match bands")
        band_mask = bad_bands == 0
        mask = band_mask if mask is None else np.logical_or(mask, band_mask)

    return SpectralData(
        values,
        resolved_wavelength,
        fwhm=resolved_fwhm,
        mask=mask,
        dims=("y", "x", "band"),
        metadata={
            "format": "ENVI",
            "header": dict(header.fields),
            "data_path": str(header.data_path),
        },
        wavelength_unit=unit,
    )


def _format_list(values: NDArray[np.generic], *, values_per_line: int = 6) -> str:
    formatted = [f"{float(value):.10g}" for value in np.ravel(values)]
    rows = [
        ", ".join(formatted[index : index + values_per_line])
        for index in range(0, len(formatted), values_per_line)
    ]
    return "{\n  " + ",\n  ".join(rows) + "\n}"


def _write_header(
    data_path: Path,
    *,
    lines: int,
    samples: int,
    bands: int,
    wavelength: NDArray[np.float64] | None,
    fwhm: NDArray[np.float64] | None,
    description: str,
) -> Path:
    header_path = Path(f"{data_path}.hdr")
    fields = [
        "ENVI",
        f"description = {{{description}}}",
        f"samples = {samples}",
        f"lines = {lines}",
        f"bands = {bands}",
        "header offset = 0",
        "file type = ENVI Standard",
        "data type = 4",
        "interleave = bip",
        "byte order = 0",
    ]
    if wavelength is not None:
        fields.extend(
            [
                "wavelength units = Micrometers",
                f"wavelength = {_format_list(wavelength)}",
            ]
        )
    if fwhm is not None:
        fields.append(f"fwhm = {_format_list(fwhm)}")
    header_path.write_text("\n".join(fields) + "\n", encoding="ascii")
    return header_path


def write_envi(
    path: str | Path,
    values: ArrayLike,
    *,
    wavelength: ArrayLike | None = None,
    fwhm: ArrayLike | None = None,
    mask: ArrayLike | None = None,
    deleted_value: float = -32767.0,
    description: str = "spectral data",
) -> tuple[Path, Path]:
    """Write a three-dimensional float32 BIP ENVI cube."""

    data_path = Path(path)
    array = np.asarray(values)
    if array.ndim != 3:
        raise SpectralDataError(
            f"ENVI cube must have shape (lines, samples, bands), got {array.shape}"
        )
    invalid = ~np.isfinite(array)
    if mask is not None:
        try:
            invalid = np.logical_or(invalid, np.broadcast_to(mask, array.shape))
        except ValueError as exc:
            raise SpectralDataError("mask is not broadcastable to ENVI cube") from exc
    output = np.asarray(array, dtype="<f4").copy()
    output[invalid] = np.float32(deleted_value)
    data_path.parent.mkdir(parents=True, exist_ok=True)
    with data_path.open("wb") as stream:
        output.tofile(stream)

    wave = None if wavelength is None else np.asarray(wavelength, dtype=np.float64)
    width = None if fwhm is None else np.asarray(fwhm, dtype=np.float64)
    header_path = _write_header(
        data_path,
        lines=array.shape[0],
        samples=array.shape[1],
        bands=array.shape[2],
        wavelength=wave,
        fwhm=width,
        description=description,
    )
    return data_path, header_path


@dataclass(frozen=True, slots=True)
class PackedLayout:
    """Mapping between an arbitrary spectral tensor and a native image cube."""

    sample_shape: tuple[int, ...]
    lines: int
    samples: int
    spectra: int

    @property
    def padded_spectra(self) -> int:
        return self.lines * self.samples - self.spectra

    def restore(self, values: NDArray[np.generic]) -> NDArray[np.generic]:
        """Remove cube padding and restore the original leading dimensions."""

        if values.shape[:2] != (self.lines, self.samples):
            raise ValueError(
                f"native array shape {values.shape[:2]} does not match packed "
                f"layout {(self.lines, self.samples)}"
            )
        trailing_shape = values.shape[2:]
        flattened = np.asarray(values).reshape(
            self.lines * self.samples, *trailing_shape
        )
        return flattened[: self.spectra].reshape(self.sample_shape + trailing_shape)


def _packed_layout(data: SpectralData, max_samples_per_line: int) -> PackedLayout:
    if max_samples_per_line < 1:
        raise ValueError("max_samples_per_line must be positive")
    if data.spectra < 1:
        raise SpectralDataError("spectral tensor must contain at least one spectrum")

    if not data.sample_shape:
        return PackedLayout((), 1, 1, 1)
    if len(data.sample_shape) == 1 and data.sample_shape[0] <= max_samples_per_line:
        return PackedLayout(data.sample_shape, 1, data.sample_shape[0], data.spectra)
    if len(data.sample_shape) == 2 and data.sample_shape[1] <= max_samples_per_line:
        return PackedLayout(
            data.sample_shape,
            data.sample_shape[0],
            data.sample_shape[1],
            data.spectra,
        )

    samples = min(data.spectra, max_samples_per_line)
    lines = (data.spectra + samples - 1) // samples
    return PackedLayout(data.sample_shape, lines, samples, data.spectra)


def _spectra_slice(
    values: NDArray[np.generic],
    start: int,
    stop: int,
    sample_shape: tuple[int, ...],
) -> NDArray[np.generic]:
    """Select a bounded range without flattening the complete tensor."""

    if not sample_shape:
        return values[np.newaxis, :]
    if len(sample_shape) == 1:
        return values[start:stop, :]

    # Preserve the common image-cube fast path, including non-contiguous
    # BIL/BSQ memmap views returned by read_envi_array().
    if len(sample_shape) == 2:
        samples = sample_shape[1]
        first_line, first_sample = divmod(start, samples)
        if first_sample == 0 and stop - start <= samples:
            return values[first_line, : stop - start, :]

    flat_indices = np.arange(start, stop, dtype=np.intp)
    coordinates = np.unravel_index(flat_indices, sample_shape)
    return values[coordinates]


def write_packed_envi(
    path: str | Path,
    data: SpectralData,
    *,
    max_samples_per_line: int,
    deleted_value: float = -32767.0,
    include_spectral_metadata: bool = False,
) -> PackedLayout:
    """Stream an arbitrary spectral tensor into a native float32 BIP cube."""

    layout = _packed_layout(data, max_samples_per_line)
    data_path = Path(path)
    data_path.parent.mkdir(parents=True, exist_ok=True)

    with data_path.open("wb") as stream:
        for line_index in range(layout.lines):
            start = line_index * layout.samples
            stop = min(start + layout.samples, layout.spectra)
            line = np.full(
                (layout.samples, data.bands),
                np.float32(deleted_value),
                dtype="<f4",
            )
            count = stop - start
            if count > 0:
                target = line[:count]
                source = _spectra_slice(data.values, start, stop, data.sample_shape)
                np.copyto(target, source, casting="unsafe")
                invalid = ~np.isfinite(target)
                if data.mask is not None:
                    invalid = np.logical_or(
                        invalid,
                        _spectra_slice(data.mask, start, stop, data.sample_shape),
                    )
                target[invalid] = np.float32(deleted_value)
            line.tofile(stream)

    _write_header(
        data_path,
        lines=layout.lines,
        samples=layout.samples,
        bands=data.bands,
        wavelength=data.wavelength if include_spectral_metadata else None,
        fwhm=data.fwhm if include_spectral_metadata else None,
        description="tetracorderpy temporary reflectance cube",
    )
    return layout
