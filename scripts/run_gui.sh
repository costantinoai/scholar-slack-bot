#!/usr/bin/env bash
# Launch the web-based GUI for managing authors and reviewing updates.
# Usage: ./scripts/run_gui.sh

set -euo pipefail

# Prepare the environment using shared helpers.
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
setup_env

# Launch the GUI module. Additional arguments are forwarded to the program.
python -m scholar_slack_bot.ui.gui "$@"
