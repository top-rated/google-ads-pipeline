#!/bin/bash
set -e

echo "Starting Google Ads Pipeline..."

# Function to run the monitor script
run_monitor() {
    echo "$(date): Running monitor.py"
    python3 monitor.py >> /app/logs/monitor.log 2>&1
}

# Function to run the optimize script
run_optimize() {
    echo "$(date): Running optimize.py"
    python3 optimize.py >> /app/logs/optimize.log 2>&1
}

# In a professional setup, we could use a real cron daemon, 
# but for a single container, a simple loop is often more robust and easier to log.

# Counter to track days
DAY_COUNTER=0

while true; do
    # 1. Run monitor daily
    run_monitor
    
    # 2. Run optimize weekly (every 7 days)
    if [ $((DAY_COUNTER % 7)) -eq 0 ]; then
        run_optimize
    fi
    
    # Increment counter
    DAY_COUNTER=$((DAY_COUNTER + 1))
    
    # Sleep for 24 hours
    echo "Sleeping for 24 hours..."
    sleep 86400
done
