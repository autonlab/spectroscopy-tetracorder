from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import tetracorderpy.__main__ as cli
from tetracorderpy import (
    AnalysisResult,
    Decision,
    Material,
    SpectralData,
    SpectralProfile,
)
from tetracorderpy.errors import TetracorderExecutionError


def _data_and_result() -> tuple[SpectralData, AnalysisResult]:
    data = SpectralData(
        np.full((2, 3), 0.5, dtype=np.float32),
        np.array([0.45, 1.0, 2.2]),
    )
    decisions = (
        Decision("group", 1, "iron-bearing"),
        Decision("case", 2, "hydration"),
    )
    result = AnalysisResult(
        material_id=np.array([[7, -1], [7, 11]], dtype=np.int32),
        fit=np.array([[0.8, 0.0], [0.7, 0.6]], dtype=np.float32),
        depth=np.array([[0.2, 0.0], [0.1, 0.3]], dtype=np.float32),
        fit_depth=np.array([[0.16, 0.0], [0.07, 0.18]], dtype=np.float32),
        matched=np.array([[True, False], [True, True]]),
        decisions=decisions,
        materials={
            7: Material(7, "made_up_iron"),
            11: Material(11, "made_up_water"),
        },
        sample_shape=(2,),
        profile=SpectralProfile("synthetic", expected_bands=3),
        backend_version="6.00",
    )
    return data, result


def test_cli_emits_json_summary_and_forwards_runtime_controls(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    data, result = _data_and_result()
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli, "read_envi", lambda path: data)

    def fake_analyze(received: SpectralData, **kwargs: object) -> AnalysisResult:
        captured["data"] = received
        captured.update(kwargs)
        return result

    monkeypatch.setattr(cli, "analyze", fake_analyze)
    scratch = tmp_path / "scratch"

    return_code = cli.main(
        [
            "scene.hdr",
            "--profile",
            "emit_c",
            "--container",
            "image.sif",
            "--runtime",
            "apptainer",
            "--scratch-dir",
            str(scratch),
            "--timeout",
            "42",
        ]
    )

    assert return_code == 0
    assert captured["data"] is data
    assert captured["profile"] == "emit_c"
    assert captured["container"] == Path("image.sif")
    assert captured["runtime"] == "apptainer"
    assert captured["scratch_dir"] == scratch
    assert captured["timeout"] == 42.0

    summary = json.loads(capsys.readouterr().out)
    assert summary["input_sample_shape"] == [2]
    assert summary["result_shape"] == [2, 2]
    assert summary["matched_cells"] == 3
    assert summary["materials"] == [
        {"id": 7, "name": "made_up_iron", "count": 2},
        {"id": 11, "name": "made_up_water", "count": 1},
    ]
    assert summary["decisions"][1] == {
        "kind": "case",
        "number": 2,
        "name": "hydration",
    }
    assert summary["artifacts_path"] is None


def test_cli_reports_native_log_tail(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    data, _ = _data_and_result()
    monkeypatch.setattr(cli, "read_envi", lambda path: data)

    def fail_analysis(*args: object, **kwargs: object) -> AnalysisResult:
        raise TetracorderExecutionError("native run failed", log_tail="last log line")

    monkeypatch.setattr(cli, "analyze", fail_analysis)

    return_code = cli.main(["scene.hdr", "--profile", "emit_c"])

    assert return_code == 1
    assert capsys.readouterr().err == (
        "tetracorderpy: native run failed\nlast log line\n"
    )
