#!/usr/bin/env bash
# cron_wrapper.sh — Entry point for the v0.3 dream pipeline cron job.
#
# This script:
#   1. Checks if nephara-dream components are available
#   2. If yes: runs orchestrate.py (v0.3 full dream)
#   3. If no: exits cleanly (v0.2 cron job handles it)
#
# Designed to run at 3:30 AM, 30 minutes after the v0.2 cron job (3:00 AM)
# which writes staging data to ~/.hermes/dream-logs/staging/YYYY-MM-DD/.
#
# Usage:
#   ./cron_wrapper.sh              # Run for today
#   ./cron_wrapper.sh 2026-04-02   # Run for specific date
#   ./cron_wrapper.sh --dry-run    # Dry run
#
# Cron example:
#   30 3 * * * /Users/jeandesauw/nephara-dream/cron_wrapper.sh >> /tmp/nephara-dream-cron.log 2>&1

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORCHESTRATE="$SCRIPT_DIR/orchestrate.py"
HERMES_VENV_PYTHON="$HOME/.hermes/claude-code/venv/bin/python3"
HERMES_ENV="$HOME/.hermes/.env"
DATE="${1:-$(date +%Y-%m-%d)}"
EXTRA_ARGS="${@:2}"

# Handle --dry-run as first arg
if [[ "$DATE" == "--dry-run" ]]; then
    DATE="$(date +%Y-%m-%d)"
    EXTRA_ARGS="--dry-run ${@:2}"
fi

# ---------------------------------------------------------------------------
# Load environment
# ---------------------------------------------------------------------------

if [[ -f "$HERMES_ENV" ]]; then
    set -a
    source "$HERMES_ENV"
    set +a
fi

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------

echo "[$(date '+%Y-%m-%d %H:%M:%S')] nephara-dream cron_wrapper starting for date=$DATE"

# Check orchestrate.py exists
if [[ ! -f "$ORCHESTRATE" ]]; then
    echo "ERROR: orchestrate.py not found at $ORCHESTRATE"
    exit 1
fi

# Check Python interpreter
PYTHON=""
if [[ -x "$HERMES_VENV_PYTHON" ]]; then
    PYTHON="$HERMES_VENV_PYTHON"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    echo "ERROR: No Python 3 interpreter found"
    exit 1
fi

echo "Using Python: $PYTHON"

# Check staging data exists (v0.2 should have written it by now)
STAGING_DIR="$HOME/.hermes/dream-logs/staging/$DATE"
if [[ ! -d "$STAGING_DIR" ]]; then
    echo "WARNING: No staging data at $STAGING_DIR"
    echo "v0.2 may not have run yet. Proceeding with --skip-v02 fallback."
    EXTRA_ARGS="$EXTRA_ARGS --skip-v02"
fi

# ---------------------------------------------------------------------------
# Run the pipeline
# ---------------------------------------------------------------------------

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running orchestrate.py..."

"$PYTHON" "$ORCHESTRATE" \
    --date "$DATE" \
    --v02-fallback \
    $EXTRA_ARGS

EXIT_CODE=$?

echo "[$(date '+%Y-%m-%d %H:%M:%S')] orchestrate.py exited with code $EXIT_CODE"
exit $EXIT_CODE
