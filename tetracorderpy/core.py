"""
Core module for running Tetracorder single-spectrum analysis.

Wraps the USGS Tetracorder Fortran program via a Singularity container,
feeds it a known library spectrum, and parses the results.
"""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GroupMatch:
    group_num: int
    group_name: str
    material_id: int
    material_name: str
    fit: float
    depth: float
    fd: float


@dataclass
class SpectrumResult:
    file_letter: str
    record: int
    title: str
    matches: list  # list of GroupMatch
    no_match_groups: list  # list of (group_num, group_name)


# Required output directories (created inside work_dir before each run)
OUTPUT_DIRS = [
    "group.1um", "group.2um", "group.veg", "group.1.5um-broad",
    "group.2um-broad", "group.2.5um", "group.3um", "group.2.8um",
    "group.zz", "group.3.5um_curve", "group.3.5um", "group.4um",
    "group.1.3-1.4um", "group.1.4um", "group.1.5um", "group.1.7um",
    "group.1.9um", "group.ree", "group.ree_neod", "group.ree_samar",
    "case.red-edge", "case.veg.type", "case.ep-cal-chl", "carbonate-2feat",
]

# Config files that must be present in work_dir
CONFIG_FILES = [
    "r1", "cmds.start.t5.26a.single",
    "cmd.lib.setup.t5.2e1", "cmd.lib.setup.nots-ratios",
]


def _find_container() -> Path:
    """Auto-discover container/*.sif relative to repo root."""
    repo_root = Path(__file__).resolve().parent.parent
    container_dir = repo_root / "container"
    sifs = list(container_dir.glob("*.sif"))
    if not sifs:
        raise FileNotFoundError(
            f"No .sif container found in {container_dir}. "
            "Pass container= explicitly or place a .sif file there."
        )
    return sifs[0]


def run(file_letter: str, record: int, work_dir, container=None,
        timeout: int = 15) -> SpectrumResult:
    """
    Run Tetracorder single-spectrum mode on a library spectrum.

    Args:
        file_letter: SPECPR file letter ('y' for convolved library,
                     'w' for reference library)
        record: Record number in the SPECPR file
        work_dir: Directory containing the 4 config files (r1,
                  cmds.start.t5.26a.single, cmd.lib.setup.t5.2e1,
                  cmd.lib.setup.nots-ratios)
        container: Path to .sif container file. If None, auto-discovers
                   container/*.sif relative to the repo root.
        timeout: Timeout in seconds (default 15). Tetracorder loops after
                 analysis so a timeout is expected.

    Returns:
        SpectrumResult with matches per spectral group.
    """
    work_dir = Path(work_dir).resolve()

    if container is None:
        container = _find_container()
    else:
        container = Path(container).resolve()

    # Create output directories if missing
    for d in OUTPUT_DIRS:
        (work_dir / d).mkdir(exist_ok=True)

    # Clean previous outputs
    for f in ["results", "history"]:
        p = work_dir / f
        if p.exists():
            p.unlink()

    # Stdin sequence for tetracorder:
    #   1. Command file (aliases, groups, library setup via include)
    #   2. s           - enter single spectrum mode
    #   3. y 300       - file letter + record number
    #   4. 0 0         - data thresholds (none)
    #   5. 4           - verbosity (one-line screen + full results file)
    #   6. (blank)     - press return after "Analysis Complete"
    #   7. e           - exit
    stdin_suffix = f"s\n{file_letter} {record}\n0 0\n4\n\ne\n"

    cmd = [
        "singularity", "exec",
        "--bind", f"{work_dir}:/work",
        str(container),
        "bash", "-c",
        f"cd /work && "
        f"printf '{stdin_suffix}' | "
        f"cat cmds.start.t5.26a.single - | "
        f"tetracorder5.27single r1",
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        pass  # Expected — tetracorder loops after analysis; results are on disk

    results_path = work_dir / "results"
    if not results_path.exists():
        raise RuntimeError("Tetracorder did not produce a results file")

    return parse_results(results_path)


def parse_results(results_path: Path) -> SpectrumResult:
    """Parse the tetracorder results file for the CHOSEN OUTPUT block."""
    results_path = Path(results_path)
    raw = results_path.read_bytes()
    text = raw.decode("ascii", errors="ignore")
    lines = text.splitlines()

    spectrum_line = None
    matches = []
    no_match = []
    file_letter = ""
    record = 0
    title = ""

    in_chosen = False
    for line in lines:
        if "CHOSEN OUTPUT" in line:
            in_chosen = True
            continue

        if in_chosen and line.startswith("Spectrum:"):
            parts = line.split()
            spectrum_line = line
            file_letter = parts[1] if len(parts) > 1 else ""
            record = int(parts[2]) if len(parts) > 2 else 0
            title = " ".join(parts[3:]) if len(parts) > 3 else ""
            continue

        if in_chosen and spectrum_line:
            grp_match = re.match(
                r"\s+(grp|cse)\s*(\d+)\s+(\S.*?)\s+(\d+)\s+MATCHES:\s+(\S+)"
                r"\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)",
                line,
            )
            if grp_match:
                matches.append(GroupMatch(
                    group_num=int(grp_match.group(2)),
                    group_name=grp_match.group(3).strip(),
                    material_id=int(grp_match.group(4)),
                    material_name=grp_match.group(5),
                    fit=float(grp_match.group(6)),
                    depth=float(grp_match.group(7)),
                    fd=float(grp_match.group(8)),
                ))
                continue

            none_match = re.match(
                r"\s+(grp|cse)\s*(\d+)\s+(\S.*?)\s+none",
                line,
            )
            if none_match:
                no_match.append((
                    int(none_match.group(2)),
                    none_match.group(3).strip(),
                ))
                continue

            if line.strip() == "" and matches:
                break

    return SpectrumResult(
        file_letter=file_letter,
        record=record,
        title=title,
        matches=matches,
        no_match_groups=no_match,
    )
