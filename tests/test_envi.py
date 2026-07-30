from __future__ import annotations

from pathlib import Path

import numpy as np

from tetracorderpy import SpectralData
from tetracorderpy.formats import (
    read_envi,
    read_envi_array,
    write_envi,
    write_packed_envi,
)


def test_envi_round_trip(
    tmp_path: Path,
    synthetic_spectrum: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    spectrum, wavelength, fwhm = synthetic_spectrum
    values = np.broadcast_to(spectrum, (2, 3, spectrum.size)).copy()
    path = tmp_path / "cube"

    write_envi(path, values, wavelength=wavelength, fwhm=fwhm)
    loaded = read_envi(path)

    assert loaded.sample_shape == (2, 3)
    assert loaded.dims == ("y", "x", "band")
    np.testing.assert_allclose(loaded.values, values)
    np.testing.assert_allclose(loaded.wavelength, wavelength)
    np.testing.assert_allclose(loaded.fwhm, fwhm)


def test_ignore_value_is_detected_before_reflectance_scaling(tmp_path: Path) -> None:
    path = tmp_path / "scaled"
    raw = np.array([1000, -9999], dtype="<i2")
    path.write_bytes(raw.tobytes())
    Path(f"{path}.hdr").write_text(
        """ENVI
samples = 2
lines = 1
bands = 1
header offset = 0
data type = 2
interleave = bip
byte order = 0
wavelength units = Nanometers
wavelength = {500}
reflectance scale factor = 10000
data ignore value = -9999
""",
        encoding="ascii",
    )

    loaded = read_envi(path)

    assert loaded.values[0, 0, 0] == np.float32(0.1)
    assert loaded.mask is not None
    assert not loaded.mask[0, 0, 0]
    assert loaded.mask[0, 1, 0]
    np.testing.assert_allclose(loaded.wavelength, [0.5])


def test_reads_native_vicar_payload_with_gz_named_sidecar(tmp_path: Path) -> None:
    path = tmp_path / "native.fit"
    label = b"LBLSIZE=300".ljust(300, b" ")
    path.write_bytes(label + bytes([173]))
    Path(f"{path}.gz.hdr").write_text(
        """ENVI
samples = 1
lines = 1
bands = 1
header offset = 1
data type = 1
interleave = bsq
byte order = 0
""",
        encoding="ascii",
    )

    values, header = read_envi_array(path)

    assert header.header_path == Path(f"{path}.gz.hdr")
    assert header.header_offset == 300
    assert values.shape == (1, 1, 1)
    assert values[0, 0, 0] == 173

    values_from_header, header_from_header = read_envi_array(
        Path(f"{path}.gz.hdr")
    )
    assert header_from_header.data_path == path
    assert values_from_header[0, 0, 0] == 173


def test_reads_img_and_raw_with_shared_stem_headers(tmp_path: Path) -> None:
    expected = np.arange(12, dtype="<i2").reshape(2, 3, 2)
    cases = {
        ".img": ("bsq", expected.transpose(2, 0, 1)),
        ".raw": ("bil", expected.transpose(0, 2, 1)),
    }

    for suffix, (interleave, storage) in cases.items():
        directory = tmp_path / suffix.removeprefix(".")
        directory.mkdir()
        data_path = directory / f"cube{suffix}"
        header_path = directory / "cube.hdr"
        data_path.write_bytes(storage.tobytes())
        header_path.write_text(
            f"""ENVI
samples = 3
lines = 2
bands = 2
header offset = 0
data type = 2
interleave = {interleave}
byte order = 0
""",
            encoding="ascii",
        )

        from_data, data_header = read_envi_array(data_path)
        from_header, sidecar_header = read_envi_array(header_path)

        np.testing.assert_array_equal(from_data, expected)
        np.testing.assert_array_equal(from_header, expected)
        assert data_header.header_path == header_path
        assert sidecar_header.data_path == data_path


def test_packed_envi_preserves_cube_layout_and_deleted_values(
    tmp_path: Path,
    synthetic_spectrum: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    spectrum, wavelength, _ = synthetic_spectrum
    values = np.broadcast_to(spectrum, (2, 3, spectrum.size)).copy()
    values[1, 2, 5] = np.nan
    explicit_mask = np.zeros_like(values, dtype=bool)
    explicit_mask[0, 1, 8] = True
    data = SpectralData(values, wavelength, mask=explicit_mask)
    path = tmp_path / "packed"

    layout = write_packed_envi(
        path,
        data,
        max_samples_per_line=3,
        deleted_value=-32767.0,
    )
    packed, header = read_envi_array(path)

    assert layout.sample_shape == (2, 3)
    assert (layout.lines, layout.samples, layout.spectra) == (2, 3, 6)
    assert layout.padded_spectra == 0
    assert packed.shape == (2, 3, spectrum.size)
    assert packed[1, 2, 5] == np.float32(-32767.0)
    assert packed[0, 1, 8] == np.float32(-32767.0)
    assert header.fields.get("wavelength") is None


def test_packed_envi_flattens_and_restores_arbitrary_tensors(
    tmp_path: Path,
    synthetic_spectrum: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    spectrum, wavelength, _ = synthetic_spectrum
    sample_shape = (2, 2, 2)
    values = np.broadcast_to(spectrum, sample_shape + spectrum.shape).copy()
    data = SpectralData(values, wavelength)

    layout = write_packed_envi(
        tmp_path / "many",
        data,
        max_samples_per_line=3,
    )

    assert layout.sample_shape == sample_shape
    assert (layout.lines, layout.samples, layout.spectra) == (3, 3, 8)
    assert layout.padded_spectra == 1
    native = np.arange(3 * 3 * 2).reshape(3, 3, 2)
    restored = layout.restore(native)
    assert restored.shape == sample_shape + (2,)
    np.testing.assert_array_equal(
        restored.reshape(8, 2),
        native.reshape(9, 2)[:8],
    )


def test_single_spectrum_becomes_one_pixel_cube(
    tmp_path: Path,
    synthetic_spectrum: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> None:
    spectrum, wavelength, _ = synthetic_spectrum
    layout = write_packed_envi(
        tmp_path / "single",
        SpectralData(spectrum, wavelength),
        max_samples_per_line=10,
    )

    assert layout.sample_shape == ()
    assert (layout.lines, layout.samples, layout.spectra) == (1, 1, 1)
