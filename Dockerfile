FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl redis-tools postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY run.py .
COPY static/ ./static/ 2>/dev/null || true

# Copy templates if separate
COPY templates/ ./templates/ 2>/dev/null || true

# Create non-root user
RUN useradd -m -r tioli && chown -R tioli:tioli /app
USER tioli

# Create data directories
RUN mkdir -p /app/reports /app/backups

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
