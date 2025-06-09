#!/bin/bash
# Helper script to add multiple authors

ids=(
    "U4i0WGsAAAAJ"
    "FS0s6WYAAAAJ"
    "Tv-zquoAAAAJ"
)

: "${CONDA_ENV:=scholarbot}"
: "${PROJECT_DIR:=$(cd "$(dirname "$0")" && pwd)}"

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"
cd "$PROJECT_DIR"

for id in "${ids[@]}"; do
    python -m scholar_slack_bot.main --add_scholar_id "$id"
done

