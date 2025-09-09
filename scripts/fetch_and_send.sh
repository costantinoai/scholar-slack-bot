#!/usr/bin/env bash
# Fetch publications for tracked authors and send updates to Slack.
# Additional arguments are forwarded to the Python CLI.

set -euo pipefail

# Optionally activate a Conda environment if available.
if command -v conda >/dev/null 2>&1; then
    # shellcheck disable=SC1091  # Location is determined dynamically.
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate "${CONDA_ENV:-scholarbot}"
fi

# Change to repository root so relative paths resolve correctly and expose the
# ``src`` directory on ``PYTHONPATH`` so the package can be imported without
# installation.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

# Run the bot with verbose output by default, forwarding any extra CLI args.
python -m scholar_slack_bot --verbose "$@"
