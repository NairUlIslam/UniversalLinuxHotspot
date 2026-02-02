#!/bin/bash
# Wrapper to launch hotspot backend with the correct python environment
# This dynamic script works regardless of installation path

# Get the absolute directory of this script
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
PROJECT_DIR="$SCRIPT_DIR"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python"
BACKEND_SCRIPT="$PROJECT_DIR/hotspot_backend.py"

# Ensure venv exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Virtual environment not found at $VENV_PYTHON"
    echo "Please run install.sh first."
    exit 1
fi

# Execute backend with all passed arguments
# We use exec to replace the shell process with the python process
exec "$VENV_PYTHON" "$BACKEND_SCRIPT" "$@" > /tmp/hotspot_universal.log 2>&1
