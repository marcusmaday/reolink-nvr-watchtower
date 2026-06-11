ARG BUILD_FROM=ghcr.io/hassio-addons/base:21.0.0
FROM $BUILD_FROM

# Install additional dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    jq \
    ffmpeg

# Set working directory
WORKDIR /app

# Copy application files
COPY app/ /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy add-on startup script
COPY addon/run.sh /
RUN chmod +x /run.sh

# Create data directory
RUN mkdir -p /data/reolink

# Expose API port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://localhost:5000/api/health', timeout=5)" || exit 1

# Start the application
CMD ["/run.sh"]
