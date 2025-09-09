#!/usr/bin/env bash
# Add multiple Google Scholar IDs from a file to the authors database.
# Usage: ./scripts/add_authors_batch.sh path/to/ids.txt

set -euo pipefail

# Verify that an input file was provided.
if [[ $# -ne 1 ]]; then
    echo "Usage: $0 path/to/ids.txt" >&2
    exit 1
fi

IDS_FILE="$1"

# Optionally activate a Conda environment if available.
if command -v conda >/dev/null 2>&1; then
    # shellcheck disable=SC1091  # Location is determined dynamically.
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate "${CONDA_ENV:-scholarbot}"
fi

# Navigate to the repository root regardless of the invocation location and
# ensure Python can locate the package in ``src`` when executed without
# installation.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

# Loop through each non-empty line in the IDs file and add the author.
while IFS= read -r SCHOLAR_ID; do
    [[ -z "$SCHOLAR_ID" || "$SCHOLAR_ID" =~ ^# ]] && continue
    python -m scholar_slack_bot --add_scholar_id "$SCHOLAR_ID"
done < "$IDS_FILE"
