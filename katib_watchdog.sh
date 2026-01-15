#!/bin/bash
# Katib Watchdog Script
# Runs every 30 minutes to ensure all scheduled tasks are running
# Detects missed runs and triggers recovery automatically

LOG_DIR="$HOME/Documents/Katib/logs"
LOG_FILE="$LOG_DIR/watchdog_$(date '+%Y-%m-%d').log"
HEARTBEAT_DIR="$LOG_DIR"
KATIB_DIR="$HOME/Katib"
TODAY=$(date '+%Y-%m-%d')
CURRENT_HOUR=$(date '+%H')
CURRENT_MINUTE=$(date '+%M')

# Ensure log directory exists
mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

notify() {
    local title="$1"
    local message="$2"
    local sound="${3:-}"

    if [ -n "$sound" ]; then
        osascript -e "display notification \"$message\" with title \"$title\" sound name \"$sound\""
    else
        osascript -e "display notification \"$message\" with title \"$title\""
    fi
}

check_heartbeat() {
    local task="$1"
    local heartbeat_file="$HEARTBEAT_DIR/heartbeat_${task}.txt"

    if [ -f "$heartbeat_file" ]; then
        local heartbeat_date=$(cat "$heartbeat_file" | cut -d' ' -f1)
        if [ "$heartbeat_date" = "$TODAY" ]; then
            return 0  # Task ran today
        fi
    fi
    return 1  # Task did not run today
}

check_agent_loaded() {
    local agent="$1"
    if launchctl list | grep -q "$agent"; then
        return 0  # Agent is loaded
    fi
    return 1  # Agent is not loaded
}

# Start logging
log "========================================="
log "Watchdog check started"
log "Current time: $CURRENT_HOUR:$CURRENT_MINUTE"

# Check if LaunchAgents are loaded
AGENTS_OK=true

for agent in "com.katib.download" "com.katib.cleanup" "com.katib.macwhisper"; do
    if ! check_agent_loaded "$agent"; then
        log "WARNING: Agent $agent is NOT loaded!"
        AGENTS_OK=false
    fi
done

if [ "$AGENTS_OK" = false ]; then
    log "ERROR: One or more agents not loaded!"
    notify "Katib Watchdog" "WARNING: LaunchAgents not loaded! Check configuration." "Basso"
fi

# Check MacWhisper (should run at 8:55 AM)
# Only check after 9:00 AM
if [ "$CURRENT_HOUR" -ge 9 ]; then
    if ! check_heartbeat "macwhisper"; then
        log "MacWhisper heartbeat missing - checking if app is running"
        if ! pgrep -x "MacWhisper" > /dev/null; then
            log "MacWhisper not running - opening it now"
            open -a "MacWhisper"
            notify "Katib Watchdog" "Recovery: Opened MacWhisper (was not running)"
            # Write heartbeat
            bash "$KATIB_DIR/katib_heartbeat.sh" macwhisper
        else
            log "MacWhisper is running (heartbeat file missing but app is up)"
            bash "$KATIB_DIR/katib_heartbeat.sh" macwhisper
        fi
    fi
fi

# Check Download task (should run at 9:00 AM)
# Only trigger recovery after 9:30 AM to give primary time to run
if [ "$CURRENT_HOUR" -gt 9 ] || ([ "$CURRENT_HOUR" -eq 9 ] && [ "$CURRENT_MINUTE" -ge 30 ]); then
    if ! check_heartbeat "download"; then
        log "WARNING: Download task did not run today!"
        log "Triggering recovery download..."
        notify "Katib Watchdog" "Recovery: Download missed - running now" "Basso"

        # Run download script
        bash "$KATIB_DIR/katib_daily_download.sh" >> "$LOG_FILE" 2>&1
        EXIT_CODE=$?

        if [ $EXIT_CODE -eq 0 ]; then
            log "Recovery download completed successfully"
            notify "Katib Watchdog" "Recovery download completed successfully"
        else
            log "ERROR: Recovery download failed with exit code $EXIT_CODE"
            notify "Katib Watchdog" "ERROR: Recovery download failed!" "Basso"
        fi
    else
        log "Download task ran today - OK"
    fi
fi

# Check Cleanup task (should run at 10:00 PM / 22:00)
# Only trigger recovery after 10:30 PM
if [ "$CURRENT_HOUR" -gt 22 ] || ([ "$CURRENT_HOUR" -eq 22 ] && [ "$CURRENT_MINUTE" -ge 30 ]); then
    if ! check_heartbeat "cleanup"; then
        log "WARNING: Cleanup task did not run today!"
        log "Triggering recovery cleanup..."
        notify "Katib Watchdog" "Recovery: Cleanup missed - running now" "Basso"

        # Run cleanup script
        bash "$KATIB_DIR/katib_daily_cleanup.sh" >> "$LOG_FILE" 2>&1
        EXIT_CODE=$?

        if [ $EXIT_CODE -eq 0 ]; then
            log "Recovery cleanup completed successfully"
            notify "Katib Watchdog" "Recovery cleanup completed successfully"
        else
            log "ERROR: Recovery cleanup failed with exit code $EXIT_CODE"
            notify "Katib Watchdog" "ERROR: Recovery cleanup failed!" "Basso"
        fi
    else
        log "Cleanup task status: checking..."
        # Only log cleanup status after 10 PM
        if [ "$CURRENT_HOUR" -ge 22 ]; then
            log "Cleanup task ran today - OK"
        fi
    fi
fi

log "Watchdog check completed"
log "========================================="

exit 0
