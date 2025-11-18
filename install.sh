#!/bin/bash
set -e

echo "Installing audio_watcher..."
pipx install .

echo "Creating log directory..."
mkdir -p ~/Library/Logs/audio_watcher

echo "Setting up LaunchAgent..."
PLIST_SRC="io.gervas.audio_watcher.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/io.gervas.audio_watcher.plist"

# Replace __HOME__ placeholder with actual home directory
sed "s|__HOME__|$HOME|g" "$PLIST_SRC" > "$PLIST_DEST"

echo "Loading LaunchAgent..."
# Unload first if already loaded (ignore errors)
launchctl unload "$PLIST_DEST" 2>/dev/null || true
# Load the agent
launchctl load "$PLIST_DEST"

echo ""
echo "✓ Installation complete!"
echo ""
echo "The audio_watcher service is now running and will start automatically on login."
echo ""
echo "Logs are written to:"
echo "  ~/Library/Logs/audio_watcher/stdout.log"
echo "  ~/Library/Logs/audio_watcher/stderr.log"
echo ""
echo "To manage the service:"
echo "  Stop:    launchctl unload ~/Library/LaunchAgents/io.gervas.audio_watcher.plist"
echo "  Start:   launchctl load ~/Library/LaunchAgents/io.gervas.audio_watcher.plist"
echo "  Restart: launchctl unload ~/Library/LaunchAgents/io.gervas.audio_watcher.plist && launchctl load ~/Library/LaunchAgents/io.gervas.audio_watcher.plist"
echo "  Status:  launchctl list | grep io.gervas.audio_watcher"
echo ""