#!/bin/bash
# Katib Cron Backup Script
# Runs at 9:30 AM as a failsafe in case LaunchAgent didn't fire
# Checks heartbeat file and triggers download if missed

HEARTBEAT_FILE="$HOME/Documents/Katib/logs/heartbeat_download.txt"
DOWNLOAD_SCRIPT="$HOME/Katib/katib_daily_download.sh"
LOG_DIR="$HOME/Documents/Katib/logs"
LOG_FILE="$LOG_DIR/cron_backup.log"
TODAY=$(date '+%Y-%m-%d')

# Ensure log directory exists
mkdir -p "$LOG_DIR"

echo "" >> "$LOG_FILE"
echo "=========================================" >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cron backup check started" >> "$LOG_FILE"

# Check if heartbeat file exists and contains today's date
if [ -f "$HEARTBEAT_FILE" ]; then
    HEARTBEAT_DATE=$(cat "$HEARTBEAT_FILE" | cut -d' ' -f1)

    if [ "$HEARTBEAT_DATE" = "$TODAY" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Download already ran today at $(cat "$HEARTBEAT_FILE")" >> "$LOG_FILE"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] No action needed" >> "$LOG_FILE"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: Download did not run today!" >> "$LOG_FILE"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Last run was: $(cat "$HEARTBEAT_FILE")" >> "$LOG_FILE"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Triggering recovery download..." >> "$LOG_FILE"

        osascript -e 'display notification "LaunchAgent missed! Running backup download..." with title "Katib Recovery" sound name "Basso"'

        # Run the download script
        bash "$DOWNLOAD_SCRIPT" >> "$LOG_FILE" 2>&1

        if [ $? -eq 0 ]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Recovery download completed successfully" >> "$LOG_FILE"
            osascript -e 'display notification "Backup download completed successfully" with title "Katib Recovery"'
        else
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Recovery download failed!" >> "$LOG_FILE"
            osascript -e 'display notification "ERROR: Backup download failed!" with title "Katib Recovery" sound name "Basso"'
        fi
    fi
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: No heartbeat file found!" >> "$LOG_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Triggering recovery download..." >> "$LOG_FILE"

    osascript -e 'display notification "No heartbeat found! Running backup download..." with title "Katib Recovery" sound name "Basso"'

    # Run the download script
    bash "$DOWNLOAD_SCRIPT" >> "$LOG_FILE" 2>&1
fi

echo "=========================================" >> "$LOG_FILE"
exit 0
