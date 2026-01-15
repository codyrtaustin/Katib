#!/bin/bash
# Katib Daily Cleanup Script
# Deletes MP3 files that have been transcribed for 14+ days
# Runs at 10 PM PT daily

# Set up environment
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/Library/Frameworks/Python.framework/Versions/3.11/bin:$PATH"
export HOME="/Users/codyaustin"

SCRIPT_DIR="$HOME/Katib"
LOG_DIR="$HOME/Documents/Katib/logs"
LOG_FILE="$LOG_DIR/cleanup_$(date '+%Y-%m-%d').log"

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
        osascript -e "display notification \"$message\" with title \"Katib Cleanup\" sound name \"$sound\""
    else
        osascript -e "display notification \"$message\" with title \"Katib Cleanup\""
    fi
}

# Log script execution start
log "=========================================="
log "Katib Daily Cleanup Script Started"
log "=========================================="

notify "Cleanup script started"

# Change to Katib directory
cd "$SCRIPT_DIR" || {
    log "ERROR: Cannot change to $SCRIPT_DIR"
    notify "ERROR: Cannot access Katib directory" "Basso"
    exit 1
}

# Activate virtual environment if it exists
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
    log "Using virtual environment"
fi

# Run the cleanup script and capture output
log "Running katib_cleanup.py..."
OUTPUT=$(python3 "$SCRIPT_DIR/katib_cleanup.py" 2>&1)
EXIT_CODE=$?

# Log output
echo "$OUTPUT" >> "$LOG_FILE"

# Count deleted files from output
DELETED_COUNT=$(echo "$OUTPUT" | grep -c "Deleted:")

# Log completion
log "=========================================="
log "Script completed with exit code: $EXIT_CODE"
log "Files cleaned up: $DELETED_COUNT"
log "=========================================="

if [ $EXIT_CODE -eq 0 ]; then
    # Write heartbeat on success
    bash "$SCRIPT_DIR/katib_heartbeat.sh" cleanup

    if [ "$DELETED_COUNT" -gt 0 ]; then
        notify "Completed: $DELETED_COUNT file(s) cleaned up"
    else
        notify "Completed: No files to clean up"
    fi
else
    notify "ERROR: Cleanup failed with code $EXIT_CODE" "Basso"
fi

exit $EXIT_CODE
