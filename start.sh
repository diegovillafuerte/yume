#!/bin/bash
set -e  # Exit on error

echo "=== Starting Yume Backend ==="
echo "Environment: ${APP_ENV:-development}"
echo "PORT: ${PORT:-8000}"

echo ""
echo "=== Running Database Migrations ==="
python -m alembic upgrade head
echo "✓ Migrations completed successfully"

echo ""
echo "=== Starting Uvicorn Server ==="
exec python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port ${PORT:-8000} \
  --log-level info
