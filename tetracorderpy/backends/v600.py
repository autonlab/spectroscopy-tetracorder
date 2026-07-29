"""Tetracorder 6.00 native-cube backend."""

from __future__ import annotations

import gzip
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from numpy.typing import NDArray

from ..errors import (
    BackendCapabilityError,
    BackendUnavailableError,
    TetracorderExecutionError,
    UnsupportedProfileError,
)
from ..formats.envi import (
    PackedLayout,
    read_envi_array,
    read_envi_header,
    write_packed_envi,
)
from ..models import (
    AnalysisResult,
    Decision,
    Material,
    SpectralData,
    SpectralProfile,
)
from ..profiles import profile_deleted_value
from ..runtime import discover_container
from .base import BackendCapabilities


_PROFILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]*$")
_SCALE_LINE = re.compile(
    r"^material=\s*(?P<material>\d+)\s+"
    r"(?P<kind>group|case)\s*(?P<decision>-?\d+)\s+"
    r"(?P<name>.*?)\s+DN=\s*(?P<dn>-?\d+)\s*=\s*"
    r"(?P<physical>[-+0-9.eEdD]+)\s+(?P<status>enable|DISABLE)\s*$"
)
_DECISION_ALIAS = re.compile(
    r"^==\[DIR(?P<kind>[gc])(?P<number>\d+)\](?P<path>\S+)"
)


@dataclass(frozen=True, slots=True)
class _ScaleEntry:
    material_id: int
    kind: str
    decision: int
    name: str
    dn: int
    physical: float
    enabled: bool


@dataclass(frozen=True, slots=True)
class _Candidate:
    decision: Decision
    entry: _ScaleEntry
    base_path: Path


def _tail(path: Path, *, characters: int = 12000) -> str:
    if not path.is_file():
        return ""
    text = path.read_bytes().decode("utf-8", errors="replace")
    return text[-characters:]


def _discover_runtime(explicit: str | Path | None) -> str:
    if explicit is not None:
        requested = str(explicit)
        found = shutil.which(requested)
        if found is None:
            raise BackendUnavailableError(
                f"container runtime executable not found: {requested}"
            )
        return found
    for candidate in ("apptainer", "singularity"):
        found = shutil.which(candidate)
        if found is not None:
            return found
    raise BackendUnavailableError(
        "neither Apptainer nor Singularity is available on PATH"
    )


def _parse_scale_entries(path: Path) -> tuple[_ScaleEntry, ...]:
    if not path.is_file():
        raise TetracorderExecutionError(
            f"Tetracorder did not produce scaling metadata: {path}"
        )
    entries: list[_ScaleEntry] = []
    for line in path.read_text(encoding="ascii", errors="replace").splitlines():
        match = _SCALE_LINE.match(line)
        if match is None:
            continue
        entries.append(
            _ScaleEntry(
                material_id=int(match.group("material")),
                kind=match.group("kind"),
                decision=int(match.group("decision")),
                name=match.group("name").strip(),
                dn=int(match.group("dn")),
                physical=float(
                    match.group("physical").replace("D", "E").replace("d", "e")
                ),
                enabled=match.group("status") == "enable",
            )
        )
    if not entries:
        raise TetracorderExecutionError(
            f"no material scales could be parsed from {path}"
        )
    return tuple(entries)


def _parse_decision_paths(start_file: Path) -> dict[tuple[str, int], str]:
    paths: dict[tuple[str, int], str] = {}
    for line in start_file.read_text(encoding="ascii", errors="replace").splitlines():
        match = _DECISION_ALIAS.match(line.strip())
        if match is None:
            continue
        kind = "group" if match.group("kind") == "g" else "case"
        paths[(kind, int(match.group("number")))] = match.group("path").rstrip("/")
    if not paths:
        raise TetracorderExecutionError(
            f"no group or case directory aliases could be parsed from {start_file}"
        )
    return paths


def _candidate_files(
    run_dir: Path,
    entries: Iterable[_ScaleEntry],
    decision_paths: dict[tuple[str, int], str],
) -> tuple[_Candidate, ...]:
    candidates: list[_Candidate] = []
    for entry in entries:
        if not entry.enabled:
            continue
        keys: list[tuple[str, int]]
        if entry.kind == "group" and entry.decision == 0:
            keys = [
                key for key in decision_paths if key[0] == "group" and key[1] > 0
            ]
        else:
            keys = [(entry.kind, entry.decision)]

        for key in keys:
            relative_dir = decision_paths.get(key)
            if relative_dir is None:
                continue
            base_path = run_dir / relative_dir / entry.name
            raw_fit = Path(f"{base_path}.fit")
            compressed_fit = Path(f"{base_path}.fit.gz")
            if not raw_fit.is_file() and not compressed_fit.is_file():
                continue
            candidates.append(
                _Candidate(
                    decision=Decision(
                        kind=key[0],
                        number=key[1],
                        name=Path(relative_dir).name,
                    ),
                    entry=entry,
                    base_path=base_path,
                )
            )
    return tuple(candidates)


def _compressed_envi_array(
    path: Path,
) -> tuple[NDArray[np.generic], int]:
    header = read_envi_header(path)
    try:
        with gzip.open(path, "rb") as stream:
            payload = stream.read()
    except (OSError, EOFError) as exc:
        raise TetracorderExecutionError(
            f"could not decompress native result raster {path}: {exc}"
        ) from exc

    match = re.match(rb"LBLSIZE\s*=\s*(\d+)", payload[:128])
    offset = int(match.group(1)) if match is not None else header.header_offset
    count = header.lines * header.samples * header.bands
    required_bytes = offset + count * header.dtype.itemsize
    if len(payload) < required_bytes:
        raise TetracorderExecutionError(
            f"decompressed native result is truncated: {path}"
        )

    flat = np.frombuffer(
        payload,
        dtype=header.dtype,
        count=count,
        offset=offset,
    )
    if header.interleave == "bip":
        values = flat.reshape(header.lines, header.samples, header.bands)
    elif header.interleave == "bil":
        values = flat.reshape(
            header.lines, header.bands, header.samples
        ).transpose(0, 2, 1)
    else:
        values = flat.reshape(
            header.bands, header.lines, header.samples
        ).transpose(1, 2, 0)
    return values, header.data_type


def _read_metric(
    path: Path,
    layout: PackedLayout,
) -> tuple[NDArray[np.generic], int]:
    resolved_path = path
    if not resolved_path.is_file():
        compressed_path = Path(f"{path}.gz")
        if compressed_path.is_file():
            resolved_path = compressed_path
        else:
            raise TetracorderExecutionError(
                f"native result raster is missing: {path}"
            )

    if resolved_path.suffix.lower() == ".gz":
        values, data_type = _compressed_envi_array(resolved_path)
    else:
        values, header = read_envi_array(resolved_path)
        data_type = header.data_type
    if values.shape != (layout.lines, layout.samples, 1):
        raise TetracorderExecutionError(
            f"unexpected result shape {values.shape} in {resolved_path}; expected "
            f"{(layout.lines, layout.samples, 1)}"
        )
    return np.asarray(values[:, :, 0]), data_type


def _decode_results(
    run_dir: Path,
    layout: PackedLayout,
    profile: SpectralProfile,
    *,
    container: Path,
    runtime: str,
) -> AnalysisResult:
    entries = _parse_scale_entries(
        run_dir / "AAA.info" / "material-DN-scalling.txt"
    )
    decision_paths = _parse_decision_paths(run_dir / "cmds.start.t6.00a")
    decisions = tuple(
        sorted(
            (
                Decision(
                    kind=kind,
                    number=number,
                    name=Path(relative_path).name,
                )
                for (kind, number), relative_path in decision_paths.items()
            ),
            key=lambda item: (item.kind != "group", item.number, item.name),
        )
    )
    decision_index = {decision: index for index, decision in enumerate(decisions)}
    candidates = _candidate_files(run_dir, entries, decision_paths)

    native_shape = (layout.lines, layout.samples, len(decisions))
    material_id = np.full(native_shape, -1, dtype=np.int32)
    fit = np.zeros(native_shape, dtype=np.float32)
    depth = np.zeros(native_shape, dtype=np.float32)
    fit_depth = np.zeros(native_shape, dtype=np.float32)
    materials = {
        entry.material_id: Material(entry.material_id, entry.name)
        for entry in entries
        if entry.enabled
    }

    for candidate in candidates:
        entry = candidate.entry
        if entry.dn == 0:
            raise TetracorderExecutionError(
                f"material {entry.material_id} has an invalid zero DN scale"
            )
        raw_fit, fit_type = _read_metric(
            Path(f"{candidate.base_path}.fit"), layout
        )
        raw_depth, depth_type = _read_metric(
            Path(f"{candidate.base_path}.depth"), layout
        )
        raw_fd, fd_type = _read_metric(
            Path(f"{candidate.base_path}.fd"), layout
        )
        if fit_type not in {1, 2} or depth_type != fit_type or fd_type != fit_type:
            raise TetracorderExecutionError(
                f"unsupported or inconsistent output data types for {candidate.base_path}"
            )

        fit_divisor = 255.0 if fit_type == 1 else 32767.0
        candidate_fit = np.asarray(raw_fit, dtype=np.float32) / fit_divisor
        depth_factor = np.float32(entry.physical / entry.dn)
        candidate_depth = np.asarray(raw_depth, dtype=np.float32) * depth_factor
        candidate_fd = np.asarray(raw_fd, dtype=np.float32) * depth_factor

        # Tetracorder has already applied material-class rules and zeroed every
        # non-winner before writing these maps. Collating by fit reconstructs
        # the chosen-output tensor and defensively resolves any overlapping
        # nonzero rasters.
        index = decision_index[candidate.decision]
        take = candidate_fit > fit[:, :, index]
        if np.any(take):
            fit[:, :, index][take] = candidate_fit[take]
            depth[:, :, index][take] = candidate_depth[take]
            fit_depth[:, :, index][take] = candidate_fd[take]
            material_id[:, :, index][take] = entry.material_id

    epsilon = np.float32(1.0e-5)
    group_axis = np.asarray(
        [decision.kind == "group" for decision in decisions],
        dtype=np.bool_,
    ).reshape(1, 1, -1)
    # Mirror wrtspcrdrout/tp1cse: groups require nonzero absolute depth,
    # while cases accept either positive depth or positive fit-depth.
    has_signal = np.where(
        group_axis,
        np.abs(depth) >= epsilon,
        (depth >= epsilon) | (fit_depth >= epsilon),
    )
    matched = (fit >= epsilon) & has_signal
    material_id[~matched] = -1

    return AnalysisResult(
        material_id=np.asarray(layout.restore(material_id), dtype=np.int32),
        fit=np.asarray(layout.restore(fit), dtype=np.float32),
        depth=np.asarray(layout.restore(depth), dtype=np.float32),
        fit_depth=np.asarray(layout.restore(fit_depth), dtype=np.float32),
        matched=np.asarray(layout.restore(matched), dtype=np.bool_),
        decisions=decisions,
        materials=materials,
        sample_shape=layout.sample_shape,
        profile=profile,
        backend_version="6.00",
        provenance={
            "container": str(container),
            "runtime": runtime,
            "native_lines": layout.lines,
            "native_samples": layout.samples,
            "input_spectra": layout.spectra,
            "padded_spectra": layout.padded_spectra,
        },
    )


class Tetracorder600Backend:
    """Execute Tetracorder 6.00a5 through its native cube workflow."""

    version = "6.00"
    capabilities = BackendCapabilities(
        max_bands=710,
        max_samples_per_line=32765,
    )

    def __init__(
        self,
        *,
        container: str | Path | None = None,
        runtime: str | Path | None = None,
    ) -> None:
        self.container = discover_container(container)
        self.runtime = _discover_runtime(runtime)

    def analyze(
        self,
        data: SpectralData,
        profile: SpectralProfile,
        *,
        work_dir: Path,
        timeout: float,
    ) -> AnalysisResult:
        if data.bands > self.capabilities.max_bands:
            raise BackendCapabilityError(
                f"Tetracorder {self.version} cube mode supports at most "
                f"{self.capabilities.max_bands} bands; data have {data.bands}"
            )
        profile_name = profile.backend_profile
        if profile_name is None or not _PROFILE_NAME.fullmatch(profile_name):
            raise UnsupportedProfileError(
                f"profile {profile.name!r} has no safe Tetracorder 6.00 dataset key"
            )
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        work_dir.mkdir(parents=True, exist_ok=True)
        input_path = work_dir / "input"
        deleted_value = profile_deleted_value(profile_name)
        layout = write_packed_envi(
            input_path,
            data,
            max_samples_per_line=self.capabilities.max_samples_per_line,
            deleted_value=deleted_value,
            include_spectral_metadata=False,
        )

        driver_path = work_dir / "run-tetracorder.sh"
        driver_path.write_text(
            """#!/bin/sh
set -eu
profile=$1
diagnostic_interval=$2
setup=/t1/tetracorder.cmds/tetracorder6.00a.cmds/cmd-setup-tetrun
"$setup" /work/run "$profile" cube /work/input 1.0 \
    image none noredoverlayimages nodualimages
cd /work/run
# Tetracorder 6.00a5 has one malformed comment marker in group 21.
# Fix only the isolated run copy; this also supports pre-fix container images.
sed -i 's@^|#$@\\\\#@' cmd.lib.setup.t6.00a5
# The stock interval of 10 is invalid when a packed cube has fewer lines.
sed -i "/print every/s/^[[:space:]]*[0-9][0-9]*/  $diagnostic_interval/" \
    cmds.start.t6.00a
/usr/local/bin/tetracorder6.00 r1 > tetracorder.out 2>&1 <<'EOF'
<cmds.start.t6.00a
e
EOF
""",
            encoding="ascii",
        )

        runner_log = work_dir / "runner.log"
        command = [
            self.runtime,
            "exec",
            "--cleanenv",
            "--bind",
            f"{work_dir.resolve()}:/work",
            str(self.container),
            "/bin/sh",
            "/work/run-tetracorder.sh",
            profile_name,
            str(min(10, layout.lines)),
        ]
        try:
            with runner_log.open("wb") as log_stream:
                completed = subprocess.run(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=log_stream,
                    stderr=subprocess.STDOUT,
                    timeout=timeout,
                    check=False,
                )
        except subprocess.TimeoutExpired as exc:
            raise TetracorderExecutionError(
                f"Tetracorder {self.version} exceeded the {timeout:g}s timeout",
                log_tail=_tail(runner_log),
            ) from exc
        except OSError as exc:
            raise BackendUnavailableError(
                f"could not launch container runtime {self.runtime}: {exc}"
            ) from exc

        run_dir = work_dir / "run"
        if completed.returncode != 0:
            combined_tail = "\n".join(
                part
                for part in (
                    _tail(runner_log),
                    _tail(run_dir / "tetracorder.out"),
                )
                if part
            )
            raise TetracorderExecutionError(
                f"Tetracorder {self.version} exited with status "
                f"{completed.returncode}",
                log_tail=combined_tail,
            )

        try:
            return _decode_results(
                run_dir,
                layout,
                profile,
                container=self.container,
                runtime=self.runtime,
            )
        except TetracorderExecutionError as exc:
            if not exc.log_tail:
                exc.log_tail = "\n".join(
                    part
                    for part in (
                        _tail(runner_log),
                        _tail(run_dir / "tetracorder.out"),
                    )
                    if part
                )
            raise
