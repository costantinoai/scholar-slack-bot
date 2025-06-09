#!/bin/bash
# Example helper script to run the bot

# Name of the conda environment to activate (default: scholarbot)
: "${CONDA_ENV:=scholarbot}"

# Directory of the project (default: location of this script)
: "${PROJECT_DIR:=$(cd "$(dirname "$0")" && pwd)}"

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"
cd "$PROJECT_DIR"
python -m scholar_slack_bot.main --verbose
