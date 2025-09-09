#!/usr/bin/env bash
# Fetch publications for tracked authors and send updates to Slack.
# Additional arguments are forwarded to the Python CLI.

set -euo pipefail

# Prepare the environment using shared helpers.
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
setup_env

# Run the bot with verbose output by default, forwarding any extra CLI args.
python -m scholar_slack_bot --verbose "$@"
