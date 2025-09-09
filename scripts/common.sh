#!/usr/bin/env bash
# Common helpers for project shell scripts.
#
# Sets up a usable Python environment by optionally activating a Conda
# environment, installing required dependencies if missing, and ensuring the
# package source tree is discoverable on PYTHONPATH. The function
# `setup_env` should be invoked after sourcing this file.

set -euo pipefail

setup_env() {
    # Activate and provision a Conda environment if ``conda`` is available.
    if command -v conda >/dev/null 2>&1; then
        # shellcheck disable=SC1091  # Path is resolved dynamically at runtime.
        source "$(conda info --base)/etc/profile.d/conda.sh"

        # Name of the environment to use or create; default to ``scholarbot``.
        local env_name="${CONDA_ENV:-scholarbot}"

        # Create the environment on first run, ensuring ``pip`` is present so
        # Python packages can be installed. ``conda run`` is used instead of
        # activation to avoid polluting the current shell if creation fails.
        if ! conda env list | awk '{print $1}' | grep -qx "$env_name"; then
            conda create -y -n "$env_name" python=3.10 >/dev/null
            conda run -n "$env_name" python -m ensurepip --upgrade >/dev/null
        fi

        # Activate the environment before moving on so subsequent commands run
        # inside it.
        conda activate "$env_name"
    fi

    # Determine repository root relative to this file and change to it so that
    # relative data paths resolve correctly regardless of invocation location.
    REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    cd "$REPO_ROOT"

    # Verify core dependencies are available; if any are missing, install the
    # project in editable mode with development extras. This allows fresh
    # environments to work out of the box and provides tooling like ``pytest``.
    if ! python - <<'PY' >/dev/null 2>&1
import importlib.util, sys
for pkg in ("scholarly", "tqdm", "requests", "configparser", "flask", "pytest"):
    if importlib.util.find_spec(pkg) is None:
        sys.exit(1)
sys.exit(0)
PY
    then
        python -m pip install -e ".[dev]" >/dev/null
    fi

    # Expose the ``src`` directory on PYTHONPATH so the package can be imported
    # without requiring installation.
    export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
}
