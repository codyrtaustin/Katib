#!/bin/bash
# Katib Daily Download Script
# Runs at 9 AM PT daily to check for and download new podcast episodes

# Set up environment - launchd doesn't inherit user PATH
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/Library/Frameworks/Python.framework/Versions/3.11/bin:$PATH"
export HOME="/Users/codyaustin"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_SCRIPT="$SCRIPT_DIR/katib_downloader.py"

# Log script execution start
echo "=========================================="
echo "Katib Daily Download Script Started"
echo "Date: $(date)"
echo "User: $(whoami)"
echo "Working Directory: $SCRIPT_DIR"
echo "=========================================="

# Pull latest code from GitHub
echo "Pulling latest updates from GitHub..."
cd "$SCRIPT_DIR" && git pull 2>&1 || echo "Git pull failed (continuing anyway)"
echo ""

# Use explicit Python path for reliability
PYTHON3="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"

# Activate virtual environment if it exists
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
    PYTHON3="python3"  # Use venv Python if available
    echo "Using virtual environment Python"
else
    echo "Using system Python: $PYTHON3"
fi

# Verify Python and dependencies
if ! "$PYTHON3" -c "import requests, feedparser" 2>/dev/null; then
    echo "ERROR: Python dependencies not found. Please install requirements."
    exit 1
fi

# Run the downloader with check-new and process-queue
echo "Running katib_downloader.py --all"
"$PYTHON3" "$PYTHON_SCRIPT" --all
EXIT_CODE=$?

# Log completion
echo "=========================================="
echo "Script completed with exit code: $EXIT_CODE"
echo "End time: $(date)"
echo "=========================================="

exit $EXIT_CODE
