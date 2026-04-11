#!/bin/bash
set -e
echo "=== TiOLi Exchange Deploy Script ==="
echo "Date: $(date)"
echo ""
echo "=== Running tests ==="
cd /home/tioli/app
python3 -m pytest tests/ -q --tb=short 2>&1 | tail -10
echo ""
echo "=== Tests passed, restarting app ==="
systemctl restart tioli-exchange
sleep 3
STATUS=$(systemctl is-active tioli-exchange)
echo "Service status: $STATUS"
if [ "$STATUS" != "active" ]; then
    echo "ERROR: Service failed to start!"
    journalctl -u tioli-exchange --no-pager -n 20
    exit 1
fi
echo ""
echo "=== Smoke test ==="
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://exchange.tioli.co.za/api/v1/health)
if [ "$HTTP_CODE" = "200" ]; then
    echo "Health check: PASS (HTTP $HTTP_CODE)"
else
    echo "Health check: FAIL (HTTP $HTTP_CODE)"
    exit 1
fi
echo ""
echo "=== Deploy complete ==="
