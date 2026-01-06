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

# Make startup script executable
RUN chmod +x start.sh

# Expose port (Railway auto-detects this)
EXPOSE 8000

# Run startup script
CMD ["./start.sh"]
