from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tetracorderpy.backends import v600


def test_container_provenance_reads_identity_labels(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    image = tmp_path / "tetracorder-6.00a5.sif"
    image.write_bytes(b"synthetic image")
    payload = {
        "data": {
            "attributes": {
                "labels": {
                    "Version": "6.00a5",
                    "BuildMethod": "clean-source-build",
                    "SourceCommit": "abc123",
                    "UpstreamCommit": "84f8d7e0",
                    "UpstreamRepository": "https://example.invalid/upstream.git",
                    "ignored": {"not": "a scalar"},
                }
            }
        }
    }
    completed = subprocess.CompletedProcess(
        args=["apptainer", "inspect"],
        returncode=0,
        stdout=json.dumps(payload),
        stderr="",
    )
    monkeypatch.setattr(v600.subprocess, "run", lambda *args, **kwargs: completed)
    v600._container_provenance.cache_clear()

    provenance = v600._container_provenance(image, "apptainer")

    v600._container_provenance.cache_clear()
    assert provenance["container_size_bytes"] == len(b"synthetic image")
    assert isinstance(provenance["container_mtime_ns"], int)
    assert provenance["container_label_version"] == "6.00a5"
    assert provenance["container_label_build_method"] == "clean-source-build"
    assert provenance["container_label_source_commit"] == "abc123"
    assert provenance["container_label_upstream_commit"] == "84f8d7e0"
    assert provenance["container_label_upstream_repository"] == (
        "https://example.invalid/upstream.git"
    )


def test_container_provenance_ignores_unexpected_inspect_shape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    image = tmp_path / "unexpected.sif"
    image.write_bytes(b"image")
    completed = subprocess.CompletedProcess(
        args=["apptainer", "inspect"],
        returncode=0,
        stdout='{"data": []}',
        stderr="",
    )
    monkeypatch.setattr(v600.subprocess, "run", lambda *args, **kwargs: completed)
    v600._container_provenance.cache_clear()

    provenance = v600._container_provenance(image, "apptainer")

    v600._container_provenance.cache_clear()
    assert provenance["container_size_bytes"] == len(b"image")
    assert not any(key.startswith("container_label_") for key in provenance)
