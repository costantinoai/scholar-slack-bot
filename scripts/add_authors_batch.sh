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

# Prepare the environment using shared helpers.
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
setup_env

# Loop through each non-empty line in the IDs file and add the author.
while IFS= read -r SCHOLAR_ID; do
    [[ -z "$SCHOLAR_ID" || "$SCHOLAR_ID" =~ ^# ]] && continue
    python -m scholar_slack_bot --add_scholar_id "$SCHOLAR_ID"
done < "$IDS_FILE"
