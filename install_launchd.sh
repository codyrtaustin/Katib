#!/bin/bash
# Katib Launchd Installation Script
# This script helps install the launchd plist files with correct paths

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
HOME_DIR="$HOME"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "Katib Launchd Installation"
echo "=========================="
echo ""
echo "Script directory: $SCRIPT_DIR"
echo "Home directory: $HOME_DIR"
echo "LaunchAgents directory: $LAUNCH_AGENTS_DIR"
echo ""

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$LAUNCH_AGENTS_DIR"

# Function to install plist with path replacement
install_plist() {
    local plist_file="$1"
    local target_file="$2"
    
    echo "Installing $plist_file..."
    
    # Create a temporary copy and replace paths
    sed "s|/Users/codyaustin|$HOME_DIR|g" "$plist_file" > "$target_file"
    
    # Also replace the script directory path if it's different
    # (This assumes the repo is in the home directory - adjust if needed)
    if [ "$SCRIPT_DIR" != "$HOME_DIR/Katib" ]; then
        sed -i '' "s|$HOME_DIR/Katib|$SCRIPT_DIR|g" "$target_file"
    fi
    
    echo "  ✓ Installed to $target_file"
}

# Install download plist
install_plist "$SCRIPT_DIR/com.katib.download.plist" "$LAUNCH_AGENTS_DIR/com.katib.download.plist"

# Install transcribe plist
install_plist "$SCRIPT_DIR/com.katib.transcribe.plist" "$LAUNCH_AGENTS_DIR/com.katib.transcribe.plist"

echo ""
echo "Installation complete!"
echo ""
echo "To load the launchd agents, run:"
echo "  launchctl load $LAUNCH_AGENTS_DIR/com.katib.download.plist"
echo "  launchctl load $LAUNCH_AGENTS_DIR/com.katib.transcribe.plist"
echo ""
echo "To verify they're loaded:"
echo "  launchctl list | grep katib"
echo ""
echo "To unload (disable):"
echo "  launchctl unload $LAUNCH_AGENTS_DIR/com.katib.download.plist"
echo "  launchctl unload $LAUNCH_AGENTS_DIR/com.katib.transcribe.plist"
