"""CLI entry point: python -m tetracorderpy --work-dir DIR FILE_LETTER RECORD"""

import argparse
import sys

from tetracorderpy.core import run


def main():
    parser = argparse.ArgumentParser(
        prog="tetracorderpy",
        description="Run Tetracorder single-spectrum analysis",
    )
    parser.add_argument("file_letter", help="SPECPR file letter (e.g. 'y' or 'w')")
    parser.add_argument("record", type=int, help="Record number in the SPECPR file")
    parser.add_argument("--work-dir", required=True,
                        help="Directory containing the 4 config files")
    parser.add_argument("--container", default=None,
                        help="Path to .sif container (default: auto-discover)")
    parser.add_argument("--timeout", type=int, default=15,
                        help="Timeout in seconds (default: 15)")
    args = parser.parse_args()

    print(f"Running Tetracorder on spectrum: file={args.file_letter} record={args.record}")
    print()

    result = run(
        args.file_letter,
        args.record,
        work_dir=args.work_dir,
        container=args.container,
        timeout=args.timeout,
    )

    print(f"Spectrum: {result.title}")
    print(f"  Source: file '{result.file_letter}' record {result.record}")
    print()

    if result.matches:
        print("Matches:")
        for m in sorted(result.matches, key=lambda x: x.fd, reverse=True):
            print(f"  grp {m.group_num:2d} {m.group_name:16s}  "
                  f"{m.material_name:45s}  "
                  f"Fit={m.fit:.4f}  Depth={m.depth:.4f}  F*D={m.fd:.4f}")
    else:
        print("No matches found.")

    if result.no_match_groups:
        print()
        no_grps = ", ".join(f"grp {g}" for g, _ in result.no_match_groups)
        print(f"No match in: {no_grps}")


if __name__ == "__main__":
    main()
