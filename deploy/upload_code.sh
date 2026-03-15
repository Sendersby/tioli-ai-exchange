#!/bin/bash
# Upload the TiOLi codebase to the server
# Run this from your LOCAL machine (Windows Git Bash or similar)
# Usage: bash deploy/upload_code.sh

SERVER="165.232.37.86"
REMOTE_DIR="/home/tioli/app"

echo "Uploading TiOLi AI Transact Exchange to $SERVER..."

# Upload app code (excluding venv, db, cache)
rsync -avz --progress \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.db' \
    --exclude='*.sqlite3' \
    --exclude='*.json' \
    --exclude='.pytest_cache' \
    --exclude='.git' \
    --exclude='backups' \
    -e ssh \
    . root@$SERVER:$REMOTE_DIR/

echo ""
echo "Upload complete. Now SSH to the server and run:"
echo "  ssh root@$SERVER"
echo "  chown -R tioli:tioli /home/tioli/app"
echo "  systemctl restart tioli-exchange"
