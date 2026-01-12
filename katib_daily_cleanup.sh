#!/bin/bash
# Katib Daily Cleanup Script
# Deletes MP3 files that have been transcribed for 14+ days
# Runs at 10 PM PT daily

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Set up environment
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/Library/Frameworks/Python.framework/Versions/3.11/bin:$PATH"
export HOME="/Users/codyaustin"

# Change to Katib directory
cd "$HOME/Katib" || exit 1

# Activate virtual environment if it exists
if [ -f "$HOME/Katib/venv/bin/activate" ]; then
    source "$HOME/Katib/venv/bin/activate"
fi

# Run the cleanup script
python3 "$HOME/Katib/katib_cleanup.py"

exit 0
