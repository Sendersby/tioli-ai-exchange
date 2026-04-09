#!/bin/bash
# AGENTIS Exchange — Docker Deployment Script
# Usage: ./deploy-docker.sh [up|down|rebuild|logs|status]

set -e
cd "$(dirname "$0")"

case "${1:-up}" in
  up)
    echo "Starting AGENTIS Exchange..."
    docker compose up -d
    echo "Waiting for health checks..."
    sleep 10
    docker compose ps
    echo ""
    curl -s http://localhost:8000/api/health | python3 -m json.tool
    ;;
  down)
    echo "Stopping AGENTIS Exchange..."
    docker compose down
    ;;
  rebuild)
    echo "Rebuilding AGENTIS Exchange..."
    docker compose down
    docker compose build --no-cache
    docker compose up -d
    sleep 10
    docker compose ps
    ;;
  logs)
    docker compose logs -f --tail=50 ${2:-app}
    ;;
  status)
    docker compose ps
    echo ""
    echo "Volumes:"
    docker volume ls | grep agentis
    echo ""
    echo "Health:"
    curl -s http://localhost:8000/api/health | python3 -m json.tool 2>/dev/null || echo "App not responding"
    ;;
  backup)
    echo "Creating backup..."
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    docker compose exec -T db pg_dump -U tioli tioli_exchange | gzip > "backups/agentis_${TIMESTAMP}.sql.gz"
    echo "Backup saved: backups/agentis_${TIMESTAMP}.sql.gz"
    ;;
  *)
    echo "Usage: $0 {up|down|rebuild|logs|status|backup}"
    exit 1
    ;;
esac
