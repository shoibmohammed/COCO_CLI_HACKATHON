#!/usr/bin/env bash
# Bootstrap script for Optional Local Jira Worker environment (Developer Fallback)
# Run once before first use of the local worker.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"
WORKER_DIR="$PROJECT_ROOT/local_jira_worker"
VENV_DIR="$WORKER_DIR/.venv"
REQUIREMENTS_FILE="$WORKER_DIR/requirements.txt"

echo "=== Optional Local Jira Worker Bootstrap (Developer Fallback) ==="
echo "Worker directory: $WORKER_DIR"

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found in PATH."
    exit 1
fi
echo "Python: $(command -v python3)"

# 2. Create venv if missing
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to create venv."
        exit 1
    fi
    echo "Venv created at $VENV_DIR"
else
    echo "Venv already exists."
fi

# 3. Install dependencies
PIP_EXEC="$VENV_DIR/bin/pip"
if [ -f "$REQUIREMENTS_FILE" ]; then
    echo "Installing dependencies..."
    "$PIP_EXEC" install -r "$REQUIREMENTS_FILE" --quiet
    echo "Dependencies installed."
else
    echo "Installing snowflake-connector-python and requests..."
    "$PIP_EXEC" install snowflake-connector-python requests --quiet
    echo "Core dependencies installed."
fi

# 4. Check .env
ENV_FILE="$WORKER_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo ""
    echo "NOTE: No .env file found at $ENV_FILE (using demo/mock mode)."
    echo "For live Jira synchronization, configure credentials from .env.example."
else
    echo ".env file found."
fi

echo ""
echo "=== Local Worker Bootstrap complete ==="
echo "To run: $VENV_DIR/bin/python $WORKER_DIR/worker.py"
