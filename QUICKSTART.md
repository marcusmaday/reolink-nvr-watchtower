# Quick Start Guide

Get the Reolink NVR HA App up and running in 5 minutes.

## For Home Assistant Green Users

### Step 1: Push Code to GitHub

From your computer:

```bash
cd reolink-nvr-ha-app
git init
git add .
git commit -m "Initial commit: FastAPI wrapper for Reolink NVR"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/reolink-nvr-ha-app.git
git push -u origin main
```

### Step 2: Add Repository to Home Assistant

1. Open Home Assistant
2. Go to **Settings → Apps** (bottom left sidebar)
3. Click **"Install App"** button
4. Click ⋮ (three dots) → **"Repositories"**
5. Click **"Create Repository"**
6. Paste: `https://github.com/YOUR_USERNAME/reolink-nvr-ha-app`
7. Click **"Create"**

**Note:** In Home Assistant 2026+, "Add-ons" was renamed to "Apps"

### Step 3: Install App

1. In **Settings → Apps**, search for "Reolink NVR"
2. Click **"Reolink NVR HA App"**
3. Click **"Install"**
4. Wait for it to download and extract

### Step 4: Configure

1. Click "Configuration" tab
2. Fill in your NVR details:

```yaml
nvr_host: "192.168.1.100"
nvr_port: 80
nvr_username: "admin"
nvr_password: "your_password"
nvr_ssl: false
debug: false
api_port: 5000
```

3. Click "Save"

### Step 5: Start

1. Click "Start" button
2. Wait ~10 seconds
3. Click "Logs" tab — you should see:
   ```
   Connected to NVR: RLN16-410 (8 channels)
   ```

### Step 6: Test

Open your browser and visit:

```
http://YOUR_HA_GREEN_IP:5000/docs
```

You should see the Swagger UI with all endpoints documented. Try:

1. Click "GET /api/health" → "Try it out" → "Execute"
   - Should return `"status": "ok"` and `"nvr_connected": true`

2. Click "GET /api/device/info" → "Try it out" → "Execute"
   - Should return your NVR model, channels, etc.

3. Click "GET /api/channels" → "Try it out" → "Execute"
   - Should list all your cameras

4. Click "GET /api/search" → "Try it out"
   - Fill in: `channel=0`, `start_date=2025-01-10`
   - Click "Execute"
   - Should return today's clips for channel 0

### Step 7: Update Automations

Update your doorbell automation to use the API:

```yaml
alias: "Doorbell: Notifications with Clip Links"
triggers:
  - trigger: state
    entity_id: binary_sensor.front_door_visitor_2
    to: "on"
actions:
  - action: camera.snapshot
    target:
      entity_id: camera.front_door_fluent_2
    data:
      filename: /config/www/tmp/doorbell_snapshot.jpg

  - action: notify.mobile_app_pixel_8_pro
    data:
      title: "🔔 Doorbell"
      message: "Someone is at the door!"
      data:
        image: /local/tmp/doorbell_snapshot.jpg
        clickAction: >
          http://YOUR_HA_GREEN_IP:5000/api/search?channel=8&start_date={{now().strftime('%Y-%m-%d')}}&event_type=DOORBELL
        actions:
          - action: "UNLOCK_DOOR"
            title: "Unlock Front Door"
```

Replace `YOUR_HA_GREEN_IP` with your HA Green's IP address.

---

## For Local Development

### Setup

```bash
# Clone repo
git clone https://github.com/your-username/reolink-nvr-ha-app.git
cd reolink-nvr-ha-app

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows

# Install dependencies
pip install -r app/requirements.txt

# Create .env file
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

### Run Development Server

```bash
cd app
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 5000
```

Open browser: `http://localhost:5000/docs`

### Test Endpoints

```bash
# Health check
curl http://localhost:5000/api/health

# Device info
curl http://localhost:5000/api/device/info

# Search (adjust date and channel)
curl "http://localhost:5000/api/search?channel=0&start_date=2025-01-10"

# With event filter
curl "http://localhost:5000/api/search?channel=0&start_date=2025-01-10&event_type=DOORBELL"
```

---

## Troubleshooting

### "NVR not connected" (503)

**Check configuration:**
```bash
# From HA terminal, test connectivity
ping 192.168.1.100

# Or check logs
cat /var/logs/addon_* | grep reolink
```

**Verify NVR:**
1. Open NVR web interface in browser: `http://192.168.1.100`
2. Verify username/password work
3. Check if API/HTTP is enabled in NVR settings
4. Try updating add-on config with correct IP/credentials

### Search Returns Empty Results

1. Verify channel number (use `/api/channels` to list)
2. Make sure recordings exist for that date
3. Check NVR web UI to see if recordings are there
4. Try searching without event_type filter first

### Swagger UI shows "Failed to fetch"

1. Check that add-on is running (Logs tab)
2. Try direct curl request to verify API is responding
3. Check firewall isn't blocking port 5000

### "Channel X out of range"

1. Channels are **0-based** (0, 1, 2, ... not 1, 2, 3)
2. Use `/api/channels` endpoint to see valid channels
3. If NVR has 8 channels, valid range is 0-7

### Slow Search Responses

1. Searching across large date ranges is slow
2. Try breaking into 7-day windows
3. Use `stream=sub` (default) for faster load
4. Check NVR CPU/disk utilization in NVR web UI

---

## Next Steps

### 1. Create Dashboard Card

Create a custom Lovelace card to display recent clips:

```yaml
type: custom:html-card
html: |
  <h2>Recent Doorbell Events</h2>
  <div id="clips"></div>
  <script>
    async function loadClips() {
      const today = new Date().toISOString().split('T')[0];
      const res = await fetch(
        `http://YOUR_HA_GREEN_IP:5000/api/search?channel=0&start_date=${today}&event_type=DOORBELL`
      );
      const data = await res.json();
      const html = data.clips.length > 0
        ? data.clips.map((c, i) => `
            <div style="margin: 10px 0; padding: 10px; border: 1px solid #ccc; border-radius: 5px;">
              <strong>${new Date(c.timestamp).toLocaleString()}</strong> (${c.duration_seconds}s)
              <br/>
              <a href="${c.stream_url}" target="_blank" style="color: #03a9f4;">▶️ Watch</a>
            </div>
          `).join('')
        : '<p style="color: #999;">No doorbell events today</p>';
      document.getElementById('clips').innerHTML = html;
    }
    loadClips();
  </script>
```

### 2. Automate Video Downloads

Create an automation to download important clips:

```yaml
alias: "Doorbell: Archive Clip"
triggers:
  - trigger: state
    entity_id: binary_sensor.front_door_visitor_2
    to: "on"
actions:
  - action: shell_command.download_doorbell_video
```

In `configuration.yaml`:

```yaml
shell_command:
  download_doorbell_video: >
    curl -s 'http://localhost:5000/api/search?channel=8&start_date={{ now().strftime("%Y-%m-%d") }}&event_type=DOORBELL'
    | jq -r '.clips[0].download_url' 
    | xargs -I {} curl {} -o /config/www/clips/doorbell_$(date +%s).mp4
```

### 3. Create GitHub Issues/Discussions

Found a bug or have a feature request? Open an issue:
https://github.com/marcusmaday/reolink-nvr-ha-app/issues

### 4. Contribute

Want to contribute? See [DEVELOPMENT.md](DEVELOPMENT.md) for:
- Setting up dev environment
- Code style guidelines
- Testing procedures
- How to submit PRs

---

## Need Help?

- **API docs:** http://localhost:5000/docs
- **GitHub Issues:** https://github.com/marcusmaday/reolink-nvr-ha-app/issues
- **HA Reolink Integration:** https://www.home-assistant.io/integrations/reolink/
- **Reolink Support:** https://support.reolink.com/

---

## What's Next?

Once you have the API working:

1. ✅ Create automations with clip links in notifications
2. ✅ Build custom Lovelace cards for clip viewing
3. ⏳ Set up automated video archival
4. ⏳ Integrate with other HA automations (e.g., unlock door on doorbell)
5. ⏳ Create mobile dashboard with clip gallery

See [TODO.md](TODO.md) for planned enhancements.
