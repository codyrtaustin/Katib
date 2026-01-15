#!/bin/bash
# Katib Daily Download Script
# Runs at 9 AM PT daily to check for and download new podcast episodes

# Set up environment - launchd doesn't inherit user PATH
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/Library/Frameworks/Python.framework/Versions/3.11/bin:$PATH"
export HOME="/Users/codyaustin"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_SCRIPT="$SCRIPT_DIR/katib_downloader.py"
LOG_DIR="$HOME/Documents/Katib/logs"
LOG_FILE="$LOG_DIR/download_$(date '+%Y-%m-%d').log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Helper function for logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

notify() {
    local message="$1"
    local sound="${2:-}"
    if [ -n "$sound" ]; then
        osascript -e "display notification \"$message\" with title \"Katib Download\" sound name \"$sound\""
    else
        osascript -e "display notification \"$message\" with title \"Katib Download\""
    fi
}

# Log script execution start
log "=========================================="
log "Katib Daily Download Script Started"
log "User: $(whoami)"
log "Working Directory: $SCRIPT_DIR"
log "=========================================="

notify "Download script started"

# Pull latest code from GitHub
log "Pulling latest updates from GitHub..."
cd "$SCRIPT_DIR" && git pull >> "$LOG_FILE" 2>&1 || log "Git pull failed (continuing anyway)"

# Use explicit Python path for reliability
PYTHON3="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"

# Activate virtual environment if it exists
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
    PYTHON3="python3"  # Use venv Python if available
    log "Using virtual environment Python"
else
    log "Using system Python: $PYTHON3"
fi

# Verify Python and dependencies
if ! "$PYTHON3" -c "import requests, feedparser" 2>/dev/null; then
    log "ERROR: Python dependencies not found. Please install requirements."
    notify "ERROR: Python dependencies not found!" "Basso"
    exit 1
fi

# Run the downloader with check-new and process-queue
log "Running katib_downloader.py --all"
OUTPUT=$("$PYTHON3" "$PYTHON_SCRIPT" --all 2>&1)
EXIT_CODE=$?

# Log output
echo "$OUTPUT" >> "$LOG_FILE"

# Count downloaded episodes from output
DOWNLOADED_COUNT=$(echo "$OUTPUT" | grep -c "Successfully downloaded:")

# Log completion
log "=========================================="
log "Script completed with exit code: $EXIT_CODE"
log "Episodes downloaded: $DOWNLOADED_COUNT"
log "=========================================="

if [ $EXIT_CODE -eq 0 ]; then
    # Write heartbeat on success
    bash "$SCRIPT_DIR/katib_heartbeat.sh" download

    if [ "$DOWNLOADED_COUNT" -gt 0 ]; then
        notify "Completed: $DOWNLOADED_COUNT episode(s) downloaded"
    else
        notify "Completed: No new episodes"
    fi
else
    notify "ERROR: Download failed with code $EXIT_CODE" "Basso"
fi

exit $EXIT_CODE
