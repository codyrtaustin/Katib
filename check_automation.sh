#!/bin/bash
# Quick script to check if Katib automation ran today

LOGS_DIR="$HOME/Documents/Katib/logs"
TODAY=$(date +%Y-%m-%d)
YESTERDAY=$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d "1 day ago" +%Y-%m-%d)

echo "=========================================="
echo "Katib Automation Status Check"
echo "Date: $(date)"
echo "=========================================="
echo ""

# Check LaunchAgent stdout log
echo "1. LaunchAgent Output (stdout):"
if [ -f "$LOGS_DIR/launchd_download.log" ] && [ -s "$LOGS_DIR/launchd_download.log" ]; then
    echo "   ✓ Log file exists and has content"
    echo "   Last 5 lines:"
    tail -5 "$LOGS_DIR/launchd_download.log" | sed 's/^/   /'
else
    echo "   ⚠ No output logged (file empty or doesn't exist)"
fi
echo ""

# Check LaunchAgent error log
echo "2. LaunchAgent Errors (stderr):"
if [ -f "$LOGS_DIR/launchd_download_error.log" ] && [ -s "$LOGS_DIR/launchd_download_error.log" ]; then
    echo "   ⚠ Errors found! Last 5 lines:"
    tail -5 "$LOGS_DIR/launchd_download_error.log" | sed 's/^/   /'
else
    echo "   ✓ No errors logged"
fi
echo ""

# Check today's Python log
echo "3. Today's Python Script Log ($TODAY):"
LOG_FILE="$LOGS_DIR/katib_downloader_$TODAY.log"
if [ -f "$LOG_FILE" ]; then
    LINE_COUNT=$(wc -l < "$LOG_FILE" | tr -d ' ')
    echo "   ✓ Log file exists ($LINE_COUNT lines)"
    echo "   Last 5 entries:"
    tail -5 "$LOG_FILE" | sed 's/^/   /'
    
    # Check for execution markers
    if grep -q "Checking RSS feeds for new episodes" "$LOG_FILE"; then
        FIRST_RUN=$(grep "Checking RSS feeds for new episodes" "$LOG_FILE" | head -1 | cut -d' ' -f1-2)
        echo "   ✓ Script executed at: $FIRST_RUN"
    fi
else
    echo "   ⚠ No log file for today yet"
fi
echo ""

# Check yesterday's log for comparison
echo "4. Yesterday's Log ($YESTERDAY) for comparison:"
YESTERDAY_LOG="$LOGS_DIR/katib_downloader_$YESTERDAY.log"
if [ -f "$YESTERDAY_LOG" ]; then
    LINE_COUNT=$(wc -l < "$YESTERDAY_LOG" | tr -d ' ')
    echo "   ✓ Yesterday's log exists ($LINE_COUNT lines)"
    if grep -q "Checking RSS feeds for new episodes" "$YESTERDAY_LOG"; then
        FIRST_RUN=$(grep "Checking RSS feeds for new episodes" "$YESTERDAY_LOG" | head -1 | cut -d' ' -f1-2)
        echo "   Yesterday's first run: $FIRST_RUN"
    fi
else
    echo "   (No log file for yesterday)"
fi
echo ""

# Check LaunchAgent status
echo "5. LaunchAgent Status:"
if launchctl list | grep -q "com.katib.download"; then
    echo "   ✓ LaunchAgent is loaded"
    launchctl list | grep "com.katib.download" | sed 's/^/   /'
else
    echo "   ⚠ LaunchAgent not found in launchctl list"
fi
echo ""

echo "=========================================="
echo "Summary:"
echo "  - Check launchd_download.log for script execution markers"
echo "  - Check katib_downloader_$TODAY.log for detailed activity"
echo "  - If no logs today, the script may not have run yet"
echo "=========================================="
