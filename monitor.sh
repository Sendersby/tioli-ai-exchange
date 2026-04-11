#!/bin/bash
# Simple health monitoring — runs every 5 minutes via cron
HEALTH_URL="http://127.0.0.1:8000/api/v1/health"
LOG_FILE="/var/log/tioli-monitor.log"

# Check health endpoint
STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$HEALTH_URL")

if [ "$STATUS" != "200" ]; then
    echo "$(date) ALERT: Health check returned $STATUS" >> $LOG_FILE
    # Attempt restart
    systemctl restart tioli-exchange
    echo "$(date) ACTION: Service restarted" >> $LOG_FILE
fi

# Check disk usage
DISK_PCT=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
if [ "$DISK_PCT" -gt 85 ]; then
    echo "$(date) WARNING: Disk usage at ${DISK_PCT}%" >> $LOG_FILE
fi

# Check memory
MEM_PCT=$(free | awk '/Mem:/{printf "%.0f", $3/$2 * 100}')
if [ "$MEM_PCT" -gt 90 ]; then
    echo "$(date) WARNING: Memory usage at ${MEM_PCT}%" >> $LOG_FILE
fi

# Check error rate in last 5 min
ERRORS=$(journalctl -u tioli-exchange --since "5 min ago" --no-pager 2>/dev/null | grep -ci 'error\|exception\|traceback' || echo 0)
if [ "$ERRORS" -gt 50 ]; then
    echo "$(date) WARNING: $ERRORS errors in last 5 min" >> $LOG_FILE
fi
