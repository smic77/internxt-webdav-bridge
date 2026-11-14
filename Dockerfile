FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir \
    ASGIWebDAV \
    requests \
    cryptography \
    uvicorn \
    tzdata \
    backports.zstd

# Copy application files
COPY internxt.py /app/internxt.py
COPY internxt_provider.py /app/internxt_provider.py
COPY standalone.py /app/standalone.py
COPY healthcheck.py /app/healthcheck.py

# Create data directory
RUN mkdir -p /data

# Expose port
EXPOSE 8000

# Health check
# Authenticated PROPFIND using WEBDAV_USERNAME / WEBDAV_PASSWORD from the environment
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD ["python", "/app/healthcheck.py"]

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Run the application
CMD ["python", "standalone.py"]
