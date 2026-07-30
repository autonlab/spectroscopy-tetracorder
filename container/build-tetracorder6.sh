#!/bin/bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_dir=$(cd -- "$script_dir/.." && pwd)
definition="$script_dir/tetracorder6.def"
output_image=${1:-"$script_dir/tetracorder6_00a5.sif"}

if ! command -v apptainer >/dev/null 2>&1; then
    echo "apptainer is required to build the image" >&2
    exit 1
fi

if [[ -e "$output_image" ]]; then
    echo "Refusing to overwrite existing output: $output_image" >&2
    exit 1
fi

export APPTAINER_TMPDIR=${APPTAINER_TMPDIR:-/tmp}
export APPTAINER_CACHEDIR=${APPTAINER_CACHEDIR:-/tmp/tetracorder6-apptainer-cache}
mkdir -p "$APPTAINER_TMPDIR" "$APPTAINER_CACHEDIR"

cd "$repo_dir"
source_commit=unknown
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    source_commit=$(git rev-parse HEAD)
    if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
        source_commit="${source_commit}-dirty"
    fi
fi

rendered_definition=$(mktemp "${APPTAINER_TMPDIR%/}/tetracorder6-def.XXXXXX")
trap 'rm -f -- "$rendered_definition"' EXIT
sed "s/TETRACORDER_SOURCE_COMMIT/$source_commit/g" \
    "$definition" > "$rendered_definition"

apptainer build --fakeroot "$output_image" "$rendered_definition"
