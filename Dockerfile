FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY . .

# Install Python dependencies (non-editable for production)
RUN pip install --no-cache-dir .

# Expose port (Railway auto-detects this)
EXPOSE 8000

# Run migrations and start server
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
