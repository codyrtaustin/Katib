#!/bin/bash
# Katib Daily Download Script
# Runs at 9 AM PT daily to check for and download new podcast episodes

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_SCRIPT="$SCRIPT_DIR/katib_downloader.py"

# Activate virtual environment if it exists
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
fi

# Run the downloader with check-new and process-queue
python3 "$PYTHON_SCRIPT" --all

exit 0
