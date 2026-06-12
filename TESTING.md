# Testing & Verification Guide

Complete testing procedures for the Reolink NVR HA App.

---

## Table of Contents

1. [Unit Testing](#unit-testing)
2. [Integration Testing](#integration-testing)
3. [Manual Testing](#manual-testing)
4. [Performance Testing](#performance-testing)
5. [Troubleshooting Tests](#troubleshooting-tests)

---

## Unit Testing

### Test reolink_search.py Locally

Create `tests/test_reolink_search.py`:

```python
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

# Test imports
from app.reolink_search import (
    search_recordings,
    EVENT_TYPE_MAP,
    TRIGGER_TO_EVENT,
)


class MockVODFile:
    """Mock a Reolink VOD_file object."""
    def __init__(self, name, start, end, trigger):
        self.file_name = name
        self.start_time = start
        self.end_time = end
        self.trigger = trigger


@pytest.mark.asyncio
async def test_event_type_mapping():
    """Verify event type mappings are complete."""
    assert EVENT_TYPE_MAP["DOORBELL"] == "visitor"
    assert EVENT_TYPE_MAP["PERSON"] == "people"
    assert EVENT_TYPE_MAP["MOTION"] == "md"
    assert EVENT_TYPE_MAP["ANIMAL"] == "animal"
    assert EVENT_TYPE_MAP["VEHICLE"] == "vehicle"


@pytest.mark.asyncio
async def test_invalid_event_type():
    """Test that invalid event types raise ValueError."""
    mock_host = AsyncMock()
    mock_host.num_channels = 8
    
    with pytest.raises(ValueError) as exc_info:
        await search_recordings(
            host=mock_host,
            channel=0,
            start_dt=datetime(2025, 1, 10),
            end_dt=datetime(2025, 1, 10),
            event_type="INVALID",
        )
    
    assert "Unknown event_type" in str(exc_info.value)


@pytest.mark.asyncio
async def test_search_empty_result():
    """Test search when no clips found."""
    mock_host = AsyncMock()
    mock_host.num_channels = 8
    mock_host.request_vod_files = AsyncMock()
    mock_host.vod_files = Mock(return_value=[])  # No clips
    
    result = await search_recordings(
        host=mock_host,
        channel=0,
        start_dt=datetime(2025, 1, 10),
        end_dt=datetime(2025, 1, 10),
    )
    
    assert result == []
    assert isinstance(result, list)
```

Run tests:

```bash
pip install pytest pytest-asyncio
pytest tests/test_reolink_search.py -v
```

---

## Integration Testing

### Test with Real NVR

#### Prerequisites

- NVR must be on your network
- Must have admin credentials
- Must have recordings for testing

#### Test Script

Create `test_integration.py`:

```python
#!/usr/bin/env python3
import asyncio
import sys
from datetime import datetime
from reolink_aio.api import Host
from app.reolink_search import search_recordings, EVENT_TYPE_MAP


async def test_integration():
    """Full integration test with real NVR."""
    
    # Config
    NVR_HOST = "192.168.1.100"
    NVR_PORT = 80
    NVR_USER = "admin"
    NVR_PASS = "password"
    TEST_CHANNEL = 0
    TEST_DATE = "2025-01-10"  # Adjust to a date with recordings
    
    print("=" * 60)
    print("Reolink NVR HA App — Integration Test")
    print("=" * 60)
    
    # Connect
    print(f"\n[1/5] Connecting to NVR at {NVR_HOST}:{NVR_PORT}...")
    host = Host(
        host=NVR_HOST,
        port=NVR_PORT,
        username=NVR_USER,
        password=NVR_PASS,
        use_https=False,
    )
    
    try:
        await host.get_host_data()
        print(f"✓ Connected to {host.nvr_name} ({host.num_channel} channels)")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False
    
    # Get device info
    print(f"\n[2/5] Fetching device info...")
    try:
        print(f"  Model: {host.model}")
        print(f"  Firmware: {host.sw_version}")
        print(f"  MAC: {host.mac_address}")
        print(f"✓ Device info retrieved")
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False
    
    # List channels
    print(f"\n[3/5] Listing channels...")
    try:
        for i in range(host.num_channel):
            name = host.camera_name(i) or f"Channel {i}"
            print(f"  Channel {i}: {name}")
        print(f"✓ Channels listed")
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False
    
    # Search all recordings
    print(f"\n[4/5] Searching all recordings on {TEST_DATE}...")
    try:
        start_dt = datetime.strptime(TEST_DATE, "%Y-%m-%d")
        end_dt = start_dt
        
        clips = await search_recordings(
            host=host,
            channel=TEST_CHANNEL,
            start_dt=start_dt,
            end_dt=end_dt,
            event_type=None,
        )
        print(f"  Found {len(clips)} clips")
        
        if clips:
            for i, clip in enumerate(clips[:3]):  # Show first 3
                print(f"    [{i+1}] {clip['timestamp']} ({clip['duration_seconds']}s) - {clip['event_type']}")
            if len(clips) > 3:
                print(f"    ... and {len(clips)-3} more")
        print(f"✓ All recordings search OK")
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Search by event type
    print(f"\n[5/5] Searching for DOORBELL events on {TEST_DATE}...")
    try:
        doorbell_clips = await search_recordings(
            host=host,
            channel=TEST_CHANNEL,
            start_dt=start_dt,
            end_dt=end_dt,
            event_type="DOORBELL",
        )
        print(f"  Found {len(doorbell_clips)} doorbell clips")
        if doorbell_clips:
            for clip in doorbell_clips[:3]:
                print(f"    • {clip['timestamp']} ({clip['duration_seconds']}s)")
        print(f"✓ Event-type filtering OK")
    except Exception as e:
        print(f"✗ Failed: {e}")
        return False
    
    # Cleanup
    print(f"\nClosing connection...")
    await host.logout()
    
    print("\n" + "=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_integration())
    sys.exit(0 if success else 1)
```

Run:

```bash
python test_integration.py
```

---

## Manual Testing

### Using Swagger UI

1. Start the API: `python -m uvicorn main:app --reload`
2. Open: `http://localhost:5000/docs`
3. Test each endpoint:

#### Test 1: Health Check

```
GET /api/health

Expected Response (200):
{
  "status": "ok",
  "nvr_connected": true,
  "nvr_host": "192.168.1.100"
}
```

#### Test 2: Device Info

```
GET /api/device/info

Expected Response (200):
{
  "model": "RLN16-410",
  "firmware_version": "v3.1.0",
  "nvr_name": "Front Door NVR",
  "mac_address": "AA:BB:CC:DD:EE:FF",
  "is_nvr": true,
  "num_channels": 8
}
```

#### Test 3: List Channels

```
GET /api/channels

Expected Response (200):
[
  {"channel": 0, "name": "Front Door", "enabled": true, "model": "RLC-810A"},
  {"channel": 1, "name": "Back Porch", "enabled": true, "model": "RLC-810A"},
  ...
]
```

#### Test 4: Search All Recordings

```
GET /api/search?channel=0&start_date=2025-01-10

Expected Response (200):
{
  "channel": 0,
  "start_date": "2025-01-10",
  "end_date": "2025-01-10",
  "event_type": null,
  "total_clips": 42,
  "clips": [
    {
      "timestamp": "2025-01-10T08:30:00+00:00",
      "end_timestamp": "2025-01-10T08:30:15+00:00",
      "duration_seconds": 15,
      "event_type": "MOTION",
      "trigger": "md",
      "file_name": "2025_01_10_08_30_00.mp4",
      "stream_url": "rtsp://...",
      "download_url": "http://..."
    },
    ...
  ]
}
```

#### Test 5: Filter by Event Type

```
GET /api/search?channel=0&start_date=2025-01-10&event_type=DOORBELL

Expected Response (200):
{
  "channel": 0,
  "start_date": "2025-01-10",
  "end_date": "2025-01-10",
  "event_type": "DOORBELL",
  "total_clips": 3,
  "clips": [
    (doorbell events only)
  ]
}
```

#### Test 6: Multi-Day Search

```
GET /api/search?channel=0&start_date=2025-01-08&end_date=2025-01-10&event_type=PERSON

Expected: Clips from Jan 8, 9, and 10 with person detection
```

#### Test 7: Error Cases

```
# Invalid channel
GET /api/search?channel=999&start_date=2025-01-10
Expected Response (400):
{"detail": "Channel 999 out of range. NVR has 8 channels (0-based)."}

# Invalid date format
GET /api/search?channel=0&start_date=01-10-2025
Expected Response (400):
{"detail": "Invalid date format: time data '01-10-2025' does not match..."}

# Invalid event type
GET /api/search?channel=0&start_date=2025-01-10&event_type=INVALID
Expected Response (400):
{"detail": "Invalid event_type 'INVALID'. Must be one of: DOORBELL, PERSON, MOTION, ANIMAL, VEHICLE"}

# NVR not connected
(If NVR is offline)
GET /api/health
Expected Response (503):
{"status": "error", "nvr_connected": false, "nvr_host": "192.168.1.100"}
```

### Using curl

```bash
# Health check
curl -i http://localhost:5000/api/health

# Device info
curl -i http://localhost:5000/api/device/info

# Search (pretty-print JSON)
curl http://localhost:5000/api/search?channel=0&start_date=2025-01-10 | jq .

# With event filter
curl 'http://localhost:5000/api/search?channel=0&start_date=2025-01-10&event_type=DOORBELL' | jq '.clips[0]'
```

---

## Performance Testing

### Measure Search Time

```python
import time
import requests

start = time.time()
resp = requests.get(
    "http://localhost:5000/api/search",
    params={
        "channel": 0,
        "start_date": "2025-01-10",
        "end_date": "2025-01-17",  # 7 days
    }
)
duration = time.time() - start

print(f"7-day search: {duration:.2f}s")
print(f"Clips found: {resp.json()['total_clips']}")
print(f"Per-clip time: {(duration / resp.json()['total_clips']*1000):.0f}ms")
```

**Expected Performance:**
- Single day: < 2 seconds
- 7-day range: < 5 seconds
- 30-day range: < 15 seconds

If much slower, check:
- NVR CPU/disk usage (in NVR web UI)
- Network latency between HA and NVR
- NVR recording storage (full disk = slower)

---

## Troubleshooting Tests

### Test NVR Connectivity

```bash
# From HA terminal
ping -c 4 192.168.1.100

# Check port
nc -zv 192.168.1.100 80

# Try HTTP request to NVR directly
curl -i http://192.168.1.100
```

### Test Authentication

```bash
# Using reolink_aio directly
python3 << EOF
import asyncio
from reolink_aio.api import Host

async def test():
    host = Host(host="192.168.1.100", username="admin", password="wrong")
    await host.get_host_data()

try:
    asyncio.run(test())
    print("✓ Connection OK")
except Exception as e:
    print(f"✗ Error: {e}")
EOF
```

### Check Logs

```bash
# Add-on logs (HA)
Settings → Add-ons → Reolink NVR HA App → Logs

# Development logs (local)
DEBUG=true python -m uvicorn main:app --log-level debug
```

### Test VOD File Availability

```bash
# In Python shell
import asyncio
from reolink_aio.api import Host

async def test():
    host = Host(host="192.168.1.100", username="admin", password="pass")
    await host.get_host_data()
    
    # Request VOD files for today, channel 0
    await host.request_vod_files(
        0,
        start=datetime(2025, 1, 10, 0, 0, 0),
        end=datetime(2025, 1, 10, 23, 59, 59),
    )
    
    vod_files = host.vod_files(0)
    print(f"Found {len(vod_files)} VOD files")
    
    for f in vod_files[:3]:
        print(f"  {f.start_time} - {f.end_time}: {getattr(f, 'trigger', 'unknown')}")
    
    await host.logout()

asyncio.run(test())
```

---

## Automated Testing (CI/CD)

### GitHub Actions Workflow

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python 3.11
      uses: actions/setup-python@v4
      with:
        python-version: "3.11"
    
    - name: Install dependencies
      run: |
        pip install -r app/requirements.txt
        pip install pytest pytest-asyncio
    
    - name: Run unit tests
      run: |
        pytest tests/ -v
    
    - name: Lint with flake8
      run: |
        pip install flake8
        flake8 app/ --max-line-length=100 --ignore=E501,W503
```

---

## Checklist Before Release

- [ ] Unit tests pass
- [ ] Integration test passes with real NVR
- [ ] All manual tests pass
- [ ] No errors in debug logs
- [ ] Documentation is up to date
- [ ] Version bumped in `addon/manifest.json`
- [ ] Changelog updated in README
- [ ] No sensitive data in repo (credentials, IP addresses)

---

## Known Limitations

1. **NVR response time:** Depends on NVR hardware and disk speed
2. **Large date ranges:** Searching 30+ days may take 10-15 seconds
3. **Event type filtering:** Depends on reolink_aio version (≥ 0.13.3)
4. **Stream URLs:** May have authentication tokens that expire after ~24 hours

---

## Support

If tests fail, check:
- Add-on logs
- NVR connectivity and credentials
- NVR firmware version
- reolink_aio version (should be ≥ 0.13.3)
- Date format (must be YYYY-MM-DD)
- Channel number (0-based)

See [API.md](API.md) for error response documentation.
