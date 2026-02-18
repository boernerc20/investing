#!/bin/bash
# Setup Daily Automated Data Collection
#
# This script configures a cron job to run data collection daily at 6 PM
# (after market close at 4 PM ET + 2 hours for data availability)

PROJECT_DIR="/home/chris/projects/investing"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python"
COLLECTOR_SCRIPT="$PROJECT_DIR/agents/data_collector.py"
LOG_DIR="$PROJECT_DIR/logs"

echo "=================================="
echo "Daily Data Collection Setup"
echo "=================================="
echo ""

# Check if virtual environment exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ Virtual environment not found at: $VENV_PYTHON"
    echo "Please activate your virtual environment first"
    exit 1
fi

# Check if data collector exists
if [ ! -f "$COLLECTOR_SCRIPT" ]; then
    echo "❌ Data collector not found at: $COLLECTOR_SCRIPT"
    exit 1
fi

# Create cron job entry
CRON_ENTRY="0 18 * * 1-5 cd $PROJECT_DIR && $VENV_PYTHON $COLLECTOR_SCRIPT >> $LOG_DIR/cron_collection.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "data_collector.py"; then
    echo "⚠️  Cron job already exists!"
    echo ""
    echo "Current crontab entries:"
    crontab -l | grep "data_collector.py"
    echo ""
    read -p "Remove and recreate? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled"
        exit 0
    fi
    # Remove old entry
    crontab -l | grep -v "data_collector.py" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo ""
echo "✅ Cron job configured successfully!"
echo ""
echo "Schedule: Weekdays (Mon-Fri) at 6:00 PM"
echo "Command:  $VENV_PYTHON $COLLECTOR_SCRIPT"
echo "Logs:     $LOG_DIR/cron_collection.log"
echo ""
echo "To view your crontab:"
echo "  crontab -l"
echo ""
echo "To remove this cron job:"
echo "  crontab -e  # Then delete the line with 'data_collector.py'"
echo ""
echo "To test the collection now:"
echo "  cd $PROJECT_DIR"
echo "  source venv/bin/activate"
echo "  python agents/data_collector.py"
echo ""
