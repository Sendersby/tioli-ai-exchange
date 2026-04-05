#!/bin/bash
DOMAIN="agentisexchange.com"
EXPIRY=$(echo | openssl s_client -connect $DOMAIN:443 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2)
DAYS_LEFT=$(( ($(date -d "$EXPIRY" +%s) - $(date +%s)) / 86400 ))
echo "SSL Certificate for $DOMAIN expires in $DAYS_LEFT days ($EXPIRY)"
if [ $DAYS_LEFT -lt 14 ]; then
    echo "WARNING: Certificate expires in less than 14 days!"
fi
