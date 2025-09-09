#!/usr/bin/env bash
# Launch the web-based GUI for managing authors and reviewing updates.
# Usage: ./scripts/run_gui.sh

set -euo pipefail

# Optionally activate a Conda environment if available.
if command -v conda >/dev/null 2>&1; then
    # shellcheck disable=SC1091  # Location is determined dynamically.
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate "${CONDA_ENV:-scholarbot}"
fi

# Determine the repository root regardless of invocation location and expose
# the ``src`` directory on ``PYTHONPATH`` so the package can be imported
# without installation.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

# Launch the GUI module. Additional arguments are forwarded to the program.
python -m scholar_slack_bot.ui.gui "$@"
