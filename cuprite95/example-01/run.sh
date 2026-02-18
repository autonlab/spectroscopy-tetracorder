#!/bin/bash
# Run Tetracorder single-spectrum analysis on a known library spectrum.
#
# Usage:
#   ./run.sh [FILE_LETTER] [RECORD_NUMBER]
#
# Examples:
#   ./run.sh y 300    # Alunite GDS97 K Syn (150C)
#   ./run.sh y 7128   # Dry_Long_Grass AV87-2
#   ./run.sh w 654    # Muscovite GDS113 Ruby
#
# File letters:
#   y = convolved spectral library (s06av95a)
#   w = reference library (r06av95a)

set -uo pipefail

FILE_LETTER="${1:-y}"
RECORD="${2:-300}"

# Paths (relative to spectroscopy-tetracorder project root)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONTAINER="$PROJECT_ROOT/container/tetracoder5_27.sif"
CUPRITE_DIR="$PROJECT_ROOT/cuprite95"
WORK_DIR="$SCRIPT_DIR"

# Verify container exists
if [ ! -f "$CONTAINER" ]; then
    echo "ERROR: Container not found: $CONTAINER"
    exit 1
fi

# Create output directories if missing
DIRS=(
    group.1um group.2um group.veg group.1.5um-broad group.2um-broad
    group.2.5um group.3um group.2.8um group.zz group.3.5um_curve
    group.3.5um group.4um group.1.3-1.4um group.1.4um group.1.5um
    group.1.7um group.1.9um group.ree group.ree_neod group.ree_samar
    case.red-edge case.veg.type case.ep-cal-chl carbonate-2feat
)
for d in "${DIRS[@]}"; do
    mkdir -p "$WORK_DIR/$d"
done

# Clean previous outputs
rm -f "$WORK_DIR/results" "$WORK_DIR/history"

echo "Analyzing spectrum: file=$FILE_LETTER record=$RECORD"
echo "---"

# Run tetracorder single-spectrum mode.
# The stdin sequence:
#   1. Command file content (aliases, groups, library setup)
#   2. "s"       — enter single spectrum mode
#   3. "y 300"   — select spectrum (file letter + record)
#   4. "0 0"     — data thresholds (0 = none)
#   5. "4"       — output verbosity (4 = one-line screen + full results file)
#   6. ""        — press return after "Analysis Complete"
#   7. "e"       — exit
timeout 15 singularity exec \
    --bind "$CUPRITE_DIR:/t1/cuprite95" \
    "$CONTAINER" \
    bash -c "cd /t1/cuprite95/example-01 && \
        printf 's\n${FILE_LETTER} ${RECORD}\n0 0\n4\n\ne\n' | \
        cat cmds.start.t5.26a.single - | \
        tetracorder5.27single r1" > /dev/null 2>&1 \
    || true

echo ""

# Display results summary (lines 59-73 contain the CHOSEN OUTPUT section)
if [ -f "$WORK_DIR/results" ]; then
    echo "Results (best match per spectral group):"
    echo ""
    # Extract the CHOSEN OUTPUT block: Spectrum line through the group results
    strings "$WORK_DIR/results" | grep -E "^Spectrum:|^     grp|^     cse" | head -20
else
    echo "WARNING: No results file generated."
fi
