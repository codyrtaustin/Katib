#!/bin/bash
# Katib Heartbeat Script
# Records successful task completion with timestamp
# Usage: katib_heartbeat.sh <task_name>
# Example: katib_heartbeat.sh download

HEARTBEAT_DIR="$HOME/Documents/Katib/logs"
TASK_NAME="${1:-unknown}"
HEARTBEAT_FILE="$HEARTBEAT_DIR/heartbeat_${TASK_NAME}.txt"

# Ensure directory exists
mkdir -p "$HEARTBEAT_DIR"

# Write current timestamp
echo "$(date '+%Y-%m-%d %H:%M:%S')" > "$HEARTBEAT_FILE"

exit 0
