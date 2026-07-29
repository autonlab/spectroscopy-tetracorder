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
mkdir -p "$APPTAINER_CACHEDIR"

cd "$repo_dir"
exec apptainer build --fakeroot "$output_image" "$definition"
