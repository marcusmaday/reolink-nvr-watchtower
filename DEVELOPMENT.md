# Development Guide

## Project Structure

```
reolink-nvr-ha-app/
├── addon/                      # Home Assistant add-on files
│   ├── manifest.json          # Add-on configuration
│   ├── Dockerfile             # Container build instructions
│   └── run.sh                 # Startup script
├── app/                        # FastAPI application
│   ├── main.py               # Main API application
│   ├── requirements.txt       # Python dependencies
│   └── reolink_search.py      # Recording search implementation (TODO)
├── docs/                       # Documentation
│   ├── API.md                # API endpoint documentation
│   └── ARCHITECTURE.md        # Technical architecture
├── tests/                      # Test files (TODO)
├── README.md                  # Project readme
├── LICENSE                    # MIT License
└── .gitignore                 # Git ignore patterns
```

## Local Development

### Prerequisites
- Python 3.11+
- Git

### Setup

1. Clone the repository:
```bash
git clone https://github.com/marcusmaday/reolink-nvr-ha-app.git
cd reolink-nvr-ha-app
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r app/requirements.txt
```

4. Create a `.env` file for local development:
```bash
cat > .env << EOF
NVR_HOST=192.168.1.100
NVR_PORT=80
NVR_USERNAME=admin
NVR_PASSWORD=your_password
NVR_SSL=false
DEBUG=true
API_PORT=5000
EOF
```

5. Run the development server:
```bash
cd app
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 5000
```

The API will be available at `http://localhost:5000` with interactive docs at `/docs`

## API Development Workflow

### 1. Recording Search Implementation (In Progress)

The `search_recordings` endpoint needs to query the Reolink NVR API for recordings.

**Next steps:**
- Implement `reolink_aio.api.Host.search_recordings()` or equivalent
- Parse response and filter by event type
- Return structured JSON response

**Reference:**
- [reolink_aio documentation](https://github.com/starkillerOG/reolink_aio)
- Your network traffic capture from the NVR web interface

### 2. Clip Download/Streaming (Planned)

Implement endpoints to:
- Download clips as MP4
- Stream clips directly
- Extract snapshots from clips

### 3. Event Webhooks (Planned)

Subscribe to real-time Reolink events and forward to Home Assistant webhooks.

## Testing

To test the API locally:

```bash
# Health check
curl http://localhost:5000/api/health

# Device info
curl http://localhost:5000/api/device/info

# Search recordings
curl "http://localhost:5000/api/search?channel=8&start_date=2025-01-10&event_type=DOORBELL"

# Interactive docs
# Open browser to http://localhost:5000/docs
```

## Docker Build

Test the Docker build locally:

```bash
# Build for your platform
docker build -t reolink-nvr-ha-app:latest -f addon/Dockerfile .

# Run container
docker run -it -p 5000:5000 \
  -e NVR_HOST=192.168.1.100 \
  -e NVR_USERNAME=admin \
  -e NVR_PASSWORD=password \
  reolink-nvr-ha-app:latest
```

## Code Style

- Follow PEP 8 Python style guide
- Use type hints for function signatures
- Add docstrings to all functions
- Keep functions focused and testable

## Committing Changes

1. Create a feature branch:
```bash
git checkout -b feature/feature-name
```

2. Commit with clear messages:
```bash
git commit -m "feat: Add recording search endpoint"
git commit -m "fix: Handle timezone in search date"
git commit -m "docs: Update API documentation"
```

3. Push and create a pull request:
```bash
git push origin feature/feature-name
```

## Architecture Overview

```
┌─────────────────────────┐
│   Home Assistant        │
│  (with Reolink add-on)  │
└────────────┬────────────┘
             │
    HTTP REST API (port 5000)
             │
┌────────────▼────────────────────┐
│  Reolink NVR HA App (FastAPI)   │
│  ┌─────────────────────────┐    │
│  │  /api/search            │    │
│  │  /api/download          │    │
│  │  /api/snapshot          │    │
│  │  /api/device/info       │    │
│  │  /api/channels          │    │
│  └─────────────────────────┘    │
└────────────┬─────────────────────┘
             │
    HTTP API (reolink_aio library)
             │
┌────────────▼──────────────┐
│   Reolink NVR Device      │
│  (192.168.1.100:80)       │
└───────────────────────────┘
```

## Reolink API Notes

The `reolink_aio` library handles:
- Authentication (login tokens)
- Session management
- HTTP request signing
- Event subscription

The recordings search likely uses the undocumented Reolink API. Refer to:
- Community API documentation
- Network traffic captured from NVR web interface
- reolink_aio source code for similar implementations

## Troubleshooting Development

### Import errors
```bash
# Make sure you're in the virtual environment
source venv/bin/activate
pip install -r app/requirements.txt
```

### NVR connection fails
- Verify NVR credentials in `.env`
- Test connectivity: `ping 192.168.1.100`
- Try accessing NVR web interface directly

### FastAPI won't start
- Check Python version: `python3 --version` (need 3.11+)
- Check port availability: `lsof -i :5000`
- Review logs for specific errors

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [reolink_aio GitHub](https://github.com/starkillerOG/reolink_aio)
- [Home Assistant Add-on Development](https://developers.home-assistant.io/docs/add-ons)
- [Pydantic Documentation](https://docs.pydantic.dev/)
