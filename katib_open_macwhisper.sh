#!/bin/bash
# Katib MacWhisper Opener
# Opens MacWhisper at 8:55 AM before downloads start
# This ensures watch folders are active when new podcasts arrive

LOG_DIR="$HOME/Documents/Katib/logs"
LOG_FILE="$LOG_DIR/macwhisper_$(date '+%Y-%m-%d').log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Log start
echo "" >> "$LOG_FILE"
echo "=========================================" >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Opening MacWhisper..." >> "$LOG_FILE"

# Check if MacWhisper is already running
if pgrep -x "MacWhisper" > /dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] MacWhisper already running" >> "$LOG_FILE"
    osascript -e 'display notification "MacWhisper already running" with title "Katib"'
else
    # Open MacWhisper
    open -a "MacWhisper"

    if [ $? -eq 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] MacWhisper opened successfully" >> "$LOG_FILE"
        osascript -e 'display notification "MacWhisper opened for podcast transcription" with title "Katib"'
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Failed to open MacWhisper" >> "$LOG_FILE"
        osascript -e 'display notification "ERROR: Failed to open MacWhisper!" with title "Katib" sound name "Basso"'
        exit 1
    fi
fi

echo "=========================================" >> "$LOG_FILE"
exit 0
