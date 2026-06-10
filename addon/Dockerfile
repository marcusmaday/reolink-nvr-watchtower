ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest
FROM ${BUILD_FROM}

# Install Python and dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-uvicorn \
    curl

# Set working directory
WORKDIR /app

# Copy requirements
COPY app/requirements.txt .

# Install Python packages
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# Create non-root user
RUN addgroup -S appuser && adduser -S appuser -G appuser
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Start application
CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
