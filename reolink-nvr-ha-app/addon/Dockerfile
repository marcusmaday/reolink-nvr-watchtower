ARG BUILD_FROM=python:3.11-alpine
FROM $BUILD_FROM

# Install system dependencies
RUN apk add --no-cache \
    bash \
    jq \
    ffmpeg \
    curl

# Set working directory
WORKDIR /app

# Copy application files
COPY app/ /app/

# Install Python dependencies
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt || \
    pip install --no-cache-dir -r requirements.txt

# Copy add-on startup script
COPY addon/run.sh /
RUN chmod +x /run.sh

# Create data directory
RUN mkdir -p /data/reolink

# Expose API port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Start the application
CMD ["/run.sh"]
