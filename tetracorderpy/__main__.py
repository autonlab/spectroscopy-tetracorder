"""Command-line adapter for ENVI inputs."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from .api import analyze
from .errors import TetracorderError
from .formats import read_envi


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tetracorderpy",
        description=(
            "Analyze an ENVI reflectance image with Tetracorder 6.00. "
            "The ENVI header must contain wavelengths."
        ),
    )
    parser.add_argument("input", type=Path, help="ENVI data file or .hdr sidecar")
    parser.add_argument("--profile", required=True, help="Bundled sensor preset")
    parser.add_argument("--container", type=Path, help="Tetracorder 6.00 .sif")
    parser.add_argument("--runtime", help="apptainer or singularity executable")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="keep raw native artifacts here (must be absent or empty)",
    )
    parser.add_argument("--timeout", type=float, default=300.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        data = read_envi(args.input)
        result = analyze(
            data,
            profile=args.profile,
            container=args.container,
            runtime=args.runtime,
            output_dir=args.output_dir,
            timeout=args.timeout,
        )
    except (TetracorderError, FileNotFoundError, OSError) as exc:
        print(f"tetracorderpy: {exc}", file=sys.stderr)
        log_tail = getattr(exc, "log_tail", "")
        if log_tail:
            print(log_tail, file=sys.stderr)
        return 1

    matched_ids = result.material_id[result.matched]
    unique_ids, counts = np.unique(matched_ids, return_counts=True)
    summary = {
        "input_sample_shape": list(data.sample_shape),
        "result_shape": list(result.shape),
        "matched_cells": int(result.matched.sum()),
        "materials": [
            {
                "id": int(material_id),
                "name": result.material_name(int(material_id)),
                "count": int(count),
            }
            for material_id, count in zip(unique_ids, counts, strict=True)
        ],
        "decisions": [
            {
                "kind": decision.kind,
                "number": decision.number,
                "name": decision.name,
            }
            for decision in result.decisions
        ],
        "artifacts_path": (
            str(result.artifacts_path) if result.artifacts_path is not None else None
        ),
    }
    json.dump(summary, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
