#!/bin/bash
set -e

echo "================================================"
echo "  TiOLi AGENTIS Exchange — Self-Hosted Startup"
echo "================================================"

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
for i in $(seq 1 30); do
    if pg_isready -h db -U "${POSTGRES_USER:-tioli}" -q 2>/dev/null; then
        echo "PostgreSQL ready."
        break
    fi
    if [ $i -eq 30 ]; then
        echo "ERROR: PostgreSQL not ready after 30s"
        exit 1
    fi
    sleep 1
done

# Wait for Redis
echo "Waiting for Redis..."
for i in $(seq 1 15); do
    if redis-cli -h redis ping 2>/dev/null | grep -q PONG; then
        echo "Redis ready."
        break
    fi
    if [ $i -eq 15 ]; then
        echo "WARNING: Redis not reachable, continuing without cache"
    fi
    sleep 1
done

# Run database table creation (handled by app startup via init_db)
echo "Database tables will be created on first request..."

# Marker for first run
MARKER="/app/data/.seeded"
if [ "$AUTO_SEED" = "true" ] && [ ! -f "$MARKER" ]; then
    echo "First run detected — seed data will be applied on startup"
    mkdir -p /app/data
    touch "$MARKER"
fi

echo "Starting TiOLi AGENTIS Exchange..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
