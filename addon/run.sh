#!/bin/bash
# Home Assistant add-on run script

# Read add-on options
export NVR_HOST=$(jq --raw-output '.nvr_host // "192.168.1.100"' /data/options.json)
export NVR_PORT=$(jq --raw-output '.nvr_port // 80' /data/options.json)
export NVR_USERNAME=$(jq --raw-output '.nvr_username // "admin"' /data/options.json)
export NVR_PASSWORD=$(jq --raw-output '.nvr_password // "password"' /data/options.json)
export NVR_SSL=$(jq --raw-output '.nvr_ssl // false' /data/options.json)
export DEBUG=$(jq --raw-output '.debug // false' /data/options.json)
export API_PORT=$(jq --raw-output '.api_port // 5000' /data/options.json)

# Log configuration
echo "Starting Reolink NVR HA App"
echo "NVR Host: $NVR_HOST"
echo "NVR Port: $NVR_PORT"
echo "NVR SSL: $NVR_SSL"
echo "API Port: $API_PORT"
echo "Debug: $DEBUG"

# Start the FastAPI application
cd /app
python3 -m uvicorn main:app --host 0.0.0.0 --port $API_PORT
