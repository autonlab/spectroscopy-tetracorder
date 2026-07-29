from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np

from tetracorderpy import SpectralProfile
from tetracorderpy.backends.v600 import _decode_results
from tetracorderpy.formats import PackedLayout


def _write_metric(
    base: Path,
    suffix: str,
    values: np.ndarray,
    *,
    compressed: bool = False,
) -> None:
    path = Path(f"{base}.{suffix}")
    path.parent.mkdir(parents=True, exist_ok=True)
    array = np.asarray(values, dtype=np.uint8)
    payload = array.reshape(*array.shape, 1).tobytes()
    if compressed:
        path = Path(f"{path}.gz")
        payload = b"LBLSIZE=300".ljust(300, b" ") + payload
        with gzip.open(path, "wb") as stream:
            stream.write(payload)
    else:
        path.write_bytes(payload)
    Path(f"{path}.hdr").write_text(
        f"""ENVI
samples = {array.shape[1]}
lines = {array.shape[0]}
bands = 1
header offset = {1 if compressed else 0}
data type = 1
interleave = bip
byte order = 0
""",
        encoding="ascii",
    )


def test_decodes_compact_winners_and_native_scales(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    info_dir = run_dir / "AAA.info"
    info_dir.mkdir(parents=True)
    info_dir.joinpath("material-DN-scalling.txt").write_text(
        """material=    11  group     1  madeup_a  DN= 1000 =  0.50000    enable
material=    22  group     1  madeup_b  DN= 2000 =  1.00000    enable
material=    33  group     1  disabled  DN= 1000 =  1.00000       DISABLE
""",
        encoding="ascii",
    )
    run_dir.joinpath("cmds.start.t6.00a").write_text(
        "==[DIRg1]group.1um/\n",
        encoding="ascii",
    )

    fit_a = np.array([[200, 0], [100, 10]], dtype=np.uint8)
    fit_b = np.array([[100, 190], [150, 0]], dtype=np.uint8)
    depth_a = np.array([[100, 0], [50, 2]], dtype=np.uint8)
    depth_b = np.array([[60, 80], [90, 0]], dtype=np.uint8)
    fd_a = np.array([[80, 0], [40, 1]], dtype=np.uint8)
    fd_b = np.array([[50, 70], [75, 0]], dtype=np.uint8)
    for name, fit, depth, fit_depth in (
        ("madeup_a", fit_a, depth_a, fd_a),
        ("madeup_b", fit_b, depth_b, fd_b),
    ):
        compressed = name == "madeup_b"
        base = run_dir / "group.1um" / name
        _write_metric(base, "fit", fit, compressed=compressed)
        _write_metric(base, "depth", depth, compressed=compressed)
        _write_metric(base, "fd", fit_depth, compressed=compressed)

    layout = PackedLayout(sample_shape=(2, 2), lines=2, samples=2, spectra=4)
    profile = SpectralProfile(
        "synthetic",
        backend_profile="synthetic",
        expected_bands=64,
    )
    result = _decode_results(
        run_dir,
        layout,
        profile,
        container=Path("/container/tetracorder6.sif"),
        runtime="/usr/bin/apptainer",
    )

    assert result.shape == (2, 2, 1)
    assert result.decisions[0].kind == "group"
    assert result.decisions[0].number == 1
    assert result.decisions[0].name == "group.1um"
    np.testing.assert_array_equal(
        result.material_id[:, :, 0],
        [[11, 22], [22, 11]],
    )
    np.testing.assert_allclose(
        result.fit[:, :, 0],
        np.array([[200, 190], [150, 10]], dtype=np.float32) / 255.0,
    )
    np.testing.assert_allclose(
        result.depth[:, :, 0],
        np.array([[100, 80], [90, 2]], dtype=np.float32) * 0.0005,
    )
    np.testing.assert_allclose(
        result.fit_depth[:, :, 0],
        np.array([[80, 70], [75, 1]], dtype=np.float32) * 0.0005,
    )
    assert result.matched.all()
    assert result.material_name(11) == "madeup_a"
    assert result.material_name(22) == "madeup_b"
    assert 33 not in result.materials


def test_sparse_native_output_keeps_empty_decisions(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    info_dir = run_dir / "AAA.info"
    info_dir.mkdir(parents=True)
    info_dir.joinpath("material-DN-scalling.txt").write_text(
        """material=    77  group     1  madeup_empty  DN= 1000 =  0.50000    enable
""",
        encoding="ascii",
    )
    run_dir.joinpath("cmds.start.t6.00a").write_text(
        """==[DIRg1]group.1um/
==[DIRc3]case.veg/
""",
        encoding="ascii",
    )

    result = _decode_results(
        run_dir,
        PackedLayout(sample_shape=(), lines=1, samples=1, spectra=1),
        SpectralProfile(
            "synthetic",
            backend_profile="synthetic",
            expected_bands=64,
        ),
        container=Path("/container/tetracorder6.sif"),
        runtime="/usr/bin/apptainer",
    )

    assert result.shape == (2,)
    assert [(item.kind, item.number) for item in result.decisions] == [
        ("group", 1),
        ("case", 3),
    ]
    np.testing.assert_array_equal(result.material_id, [-1, -1])
    np.testing.assert_array_equal(result.fit, [0.0, 0.0])
    assert not result.matched.any()
    assert result.material_name(77) == "madeup_empty"
