from __future__ import annotations

from pathlib import Path

import pytest

from tetracorderpy import runtime
from tetracorderpy.__main__ import main
from tetracorderpy.errors import BackendUnavailableError, RuntimeSetupError
from tetracorderpy.setup_runtime import setup_runtime


def _isolate_automatic_locations(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("TETRACORDER_CONTAINER", raising=False)
    monkeypatch.delenv("TETRACORDER_CONTAINER_PATH", raising=False)
    monkeypatch.setattr(runtime, "repository_root", lambda: tmp_path / "missing-repo")
    monkeypatch.setattr(
        runtime,
        "PSC_SHARED_CONTAINER_ROOT",
        tmp_path / "missing-shared-containers",
    )
    monkeypatch.setattr(
        runtime,
        "PSC_SHARED_SOURCE_CHECKOUT",
        tmp_path / "missing-shared-source",
    )


def test_container_search_path_accepts_directories(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_automatic_locations(monkeypatch, tmp_path)
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    image = image_dir / "tetracorder-6.00a5.sif"
    image.write_bytes(b"synthetic-sif-placeholder")
    monkeypatch.setenv("TETRACORDER_CONTAINER_PATH", str(image_dir))

    assert runtime.discover_container() == image.resolve()


def test_psc_stable_image_is_discovered(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_automatic_locations(monkeypatch, tmp_path)
    shared = tmp_path / "shared-containers"
    monkeypatch.setattr(runtime, "PSC_SHARED_CONTAINER_ROOT", shared)
    image = shared / runtime.TETRACORDER_IMAGE_VERSION / (
        f"tetracorder-{runtime.TETRACORDER_IMAGE_VERSION}.sif"
    )
    image.parent.mkdir(parents=True)
    image.write_bytes(b"synthetic-sif-placeholder")

    assert runtime.discover_container() == image.resolve()


def test_missing_container_points_to_setup_command(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _isolate_automatic_locations(monkeypatch, tmp_path)

    with pytest.raises(BackendUnavailableError, match="tetracorderpy setup"):
        runtime.discover_container()


def test_setup_reuses_an_existing_image_without_building(tmp_path: Path) -> None:
    image = tmp_path / "already-built.sif"
    image.write_bytes(b"synthetic-sif-placeholder")

    assert setup_runtime(output=image, verify=False) == image


def test_setup_dry_run_does_not_create_an_image(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source"
    for relative in ("specpr", "tetracorder6.00", "tetracorder.cmds", "sl1"):
        (source / relative).mkdir(parents=True)
    script = source / "container" / "build-tetracorder6.sh"
    script.parent.mkdir()
    script.write_text("#!/bin/bash\nexit 99\n", encoding="ascii")
    output = tmp_path / "images" / "new.sif"

    result = setup_runtime(
        source=source,
        output=output,
        verify=False,
        dry_run=True,
    )

    assert result == output
    assert not output.exists()
    rendered = capsys.readouterr().out
    assert str(source) in rendered
    assert str(output) in rendered


def test_setup_rejects_an_incomplete_explicit_checkout(tmp_path: Path) -> None:
    with pytest.raises(RuntimeSetupError, match="incomplete"):
        setup_runtime(
            source=tmp_path / "not-a-checkout",
            output=tmp_path / "new.sif",
            verify=False,
            dry_run=True,
        )


def test_main_routes_setup_subcommand_without_building(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    image = tmp_path / "existing.sif"
    image.write_bytes(b"synthetic-sif-placeholder")

    return_code = main(
        ["setup", "--output", str(image), "--no-verify", "--dry-run"]
    )

    assert return_code == 0
    assert "Would reuse existing image" in capsys.readouterr().out
