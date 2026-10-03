#!/usr/bin/env bash
# Master Judge Bootstrap & Verification Script (Bash)
# Prepares and validates the Snowflake Container Runtime deployment for judges.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"

echo "================================================================="
echo "🏭 MFG PREDICTIVE MAINTENANCE & OEE COMMAND CENTER"
echo "   MASTER JUDGE BOOTSTRAP & DEPLOYMENT PRE-FLIGHT"
echo "   Target: Snowflake Container Runtime (SYSTEM_COMPUTE_POOL_CPU)"
echo "================================================================="

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found in PATH."
    exit 1
fi
echo "[1/5] Python Environment: $(command -v python3)"

# 2. Run AST Syntax Validation
echo "[2/5] Validating Python AST Syntax..."
python3 "$PROJECT_ROOT/scripts/validate_python.py"
if [ $? -ne 0 ]; then
    echo "ERROR: Python syntax validation failed."
    exit 1
fi

# 3. Run Container Runtime Deployment Pre-Flight Validation
echo "[3/5] Running Container Runtime Pre-Flight Validation..."
python3 "$PROJECT_ROOT/scripts/validate_streamlit_deployment.py"
if [ $? -ne 0 ]; then
    echo "ERROR: Container Runtime pre-flight validation failed."
    exit 1
fi

# 4. Run Offline Test Suite
echo "[4/5] Executing Offline Release Test Suite..."
python3 -m unittest discover -s "$PROJECT_ROOT/tests" -p "test_*.py"
if [ $? -ne 0 ]; then
    echo "ERROR: Unit tests failed."
    exit 1
fi
echo "  -> All offline tests PASSED."

# 5. Security & Manifest Verification
echo "[5/5] Verifying Deployment Security & Manifest..."
python3 "$PROJECT_ROOT/scripts/verify_deployment.py"

echo ""
echo "================================================================="
echo "🟢 BOOTSTRAP COMPLETE — SYSTEM IS 100% JUDGE READY"
echo "Primary Runtime: Snowflake-Hosted Streamlit (Container Runtime)"
echo "================================================================="
