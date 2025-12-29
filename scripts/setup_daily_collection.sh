#!/bin/bash
# Setup automatic daily historical data collection

echo "🔧 Setting up automatic daily data collection..."

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script is for macOS only"
    exit 1
fi

# Load and enable the scheduled task
PLIST_PATH=~/Library/LaunchAgents/com.vibestracker.dailycollection.plist

if [ -f "$PLIST_PATH" ]; then
    # Unload if already loaded
    launchctl unload "$PLIST_PATH" 2>/dev/null

    # Load the task
    launchctl load "$PLIST_PATH"

    echo "✅ Daily collection scheduled!"
    echo ""
    echo "📅 Schedule:"
    echo "   - Runs daily at 9:00 AM"
    echo "   - Collects 10 monthly periods per run"
    echo "   - Logs to: logs/daily_collection.log"
    echo ""
    echo "🔍 Check status:"
    echo "   launchctl list | grep vibestracker"
    echo ""
    echo "🛑 To disable:"
    echo "   launchctl unload $PLIST_PATH"
    echo ""
    echo "🔄 To run manually now:"
    echo "   .venv/bin/python scripts/incremental_historical_collection.py"
else
    echo "❌ Scheduled task file not found at: $PLIST_PATH"
    echo "   Please run this script from the vibes-tracker directory"
    exit 1
fi
