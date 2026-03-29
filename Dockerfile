FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for PostgreSQL and PDF generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl redis-tools postgresql-client && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -r tioli && chown -R tioli:tioli /app
USER tioli

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
