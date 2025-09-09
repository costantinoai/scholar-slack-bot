#!/usr/bin/env bash
# Common helpers for project shell scripts.
#
# Sets up a usable Python environment by optionally activating a Conda
# environment, installing required dependencies if missing, and ensuring the
# package source tree is discoverable on PYTHONPATH. The function
# `setup_env` should be invoked after sourcing this file.

set -euo pipefail

setup_env() {
    # Activate a Conda environment if `conda` is available.
    if command -v conda >/dev/null 2>&1; then
        # shellcheck disable=SC1091  # Path is resolved dynamically at runtime.
        source "$(conda info --base)/etc/profile.d/conda.sh"
        conda activate "${CONDA_ENV:-scholarbot}"
    fi

    # Determine repository root relative to this file and change to it so that
    # relative data paths resolve correctly regardless of invocation location.
    REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    cd "$REPO_ROOT"

    # Verify core dependencies are available; if any are missing install from
    # requirements.txt. This allows fresh environments to work out of the box.
    if ! python - <<'PY' >/dev/null 2>&1
import importlib.util, sys
for pkg in ("scholarly", "tqdm", "requests", "configparser", "flask"):
    if importlib.util.find_spec(pkg) is None:
        sys.exit(1)
sys.exit(0)
PY
    then
        python -m pip install -r "$REPO_ROOT/requirements.txt" >/dev/null
    fi

    # Expose the ``src`` directory on PYTHONPATH so the package can be imported
    # without requiring installation.
    export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
}
