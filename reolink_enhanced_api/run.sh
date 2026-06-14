#!/bin/bash
set -e

# Reolink Enhanced API Add-on Entry Point
# This script runs inside the Home Assistant add-on container

echo "Starting Reolink Enhanced API Add-on..."

# Read add-on options from Home Assistant config
CONFIG_PATH=/data/options.json

if [ -f "$CONFIG_PATH" ]; then
    echo "Loading configuration from $CONFIG_PATH"
    
    export API_PORT=$(jq -r '.api_port // 5000' "$CONFIG_PATH")
    export NVR_HOST=$(jq -r '.nvr_host' "$CONFIG_PATH")
    export NVR_PORT=$(jq -r '.nvr_port' "$CONFIG_PATH")
    export NVR_USERNAME=$(jq -r '.nvr_username' "$CONFIG_PATH")
    export NVR_PASSWORD=$(jq -r '.nvr_password' "$CONFIG_PATH")
    export NVR_SSL=$(jq -r '.nvr_ssl' "$CONFIG_PATH")
    export BUFFER_ENABLED=$(jq -r '.buffer_enabled' "$CONFIG_PATH")
    export BUFFER_SIZE_SECONDS=$(jq -r '.buffer_size_seconds' "$CONFIG_PATH")
    export CLIP_DURATION_BEFORE=$(jq -r '.clip_duration_before' "$CONFIG_PATH")
    export CLIP_DURATION_AFTER=$(jq -r '.clip_duration_after' "$CONFIG_PATH")
    export RETENTION_DAYS=$(jq -r '.retention_days' "$CONFIG_PATH")
    export MAX_STORAGE_MB=$(jq -r '.max_storage_mb' "$CONFIG_PATH")
    export DEBUG=$(jq -r '.debug' "$CONFIG_PATH")
    export API_HOST=$(jq -r '.api_host // "0.0.0.0"' "$CONFIG_PATH")
    export ALLOW_CORS=$(jq -r '.allow_cors // false' "$CONFIG_PATH")
    export EXTERNAL_STORAGE_PATH=$(jq -r '.external_storage_path // empty' "$CONFIG_PATH")
    export CLIP_QUALITY=$(jq -r '.clip_quality // "medium"' "$CONFIG_PATH")
    
    echo "Configuration:"
    echo "  API Port: $API_PORT"
    echo "  NVR Host: $NVR_HOST:$NVR_PORT"
    echo "  Username: $NVR_USERNAME"
    echo "  SSL: $NVR_SSL"
    echo "  Buffer Enabled: $BUFFER_ENABLED"
    echo "  Retention: $RETENTION_DAYS days"
    echo "  Clip Quality: $CLIP_QUALITY"
    echo "  API Host: $API_HOST"
    echo "  Allow CORS: $ALLOW_CORS"
    echo "  External Storage: ${EXTERNAL_STORAGE_PATH:-none}"
    echo "  Debug: $DEBUG"
else
    echo "No options.json found, using defaults"
fi

# Set data directory for clips and index
export HOME_ASSISTANT_DATA_DIR=/data/reolink

mkdir -p /data/reolink
cd /app

# Run the FastAPI app
exec python -m uvicorn main:app --host "$API_HOST" --port "$API_PORT"
