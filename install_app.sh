#!/bin/bash
# Install Katib.app to Applications folder

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_PATH="$SCRIPT_DIR/Katib.app"
APPLICATIONS_DIR="$HOME/Applications"

echo "Installing Katib.app to Applications..."
echo ""

if [ ! -d "$APP_PATH" ]; then
    echo "Error: Katib.app not found at $APP_PATH"
    exit 1
fi

# Copy to Applications
cp -R "$APP_PATH" "$APPLICATIONS_DIR/"

if [ $? -eq 0 ]; then
    echo "✓ Successfully installed Katib.app to $APPLICATIONS_DIR"
    echo ""
    echo "You can now:"
    echo "  1. Open Applications folder (Cmd+Shift+A in Finder)"
    echo "  2. Find Katib.app"
    echo "  3. Drag it to your Dock, or right-click and select 'Keep in Dock'"
    echo ""
    echo "Or launch it now with:"
    echo "  open $APPLICATIONS_DIR/Katib.app"
else
    echo "Error: Failed to install app"
    exit 1
fi
