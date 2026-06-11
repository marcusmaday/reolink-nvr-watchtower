# Quick Start Guide

## Installation

### Option 1: Home Assistant Apps (Recommended)

**Note**: Home Assistant now uses "Apps" (formerly called "Add-ons"). This is only available on Home Assistant OS, not on Home Assistant Container.

**Prerequisites:**
- Home Assistant Operating System installed (not Container)
- GitHub account and repository with this code
- See "Deploying to GitHub" below to set up the repository first

**Steps:**

1. In Home Assistant, go to **Settings → System → Supervisor** (or look for the terminal/supervisor icon)
2. Navigate to **App Store**
3. Click the **⋮ (three-dot menu)** and select **Repositories**
4. Add repository URL: `https://github.com/marcusmaday/reolink-nvr-ha-app`
   (This is the complete repository URL with all the code)
5. Click **Create**
6. Search for **"Reolink Enhanced"** in the App Store
7. Click **Install**
8. Go to the app settings and configure:
   - NVR Host/Port/Username/Password
   - Buffer settings
   - Retention policy
9. Start the app
10. Go to **Settings → Devices & Services**
11. Click **Create Integration** and search for **"Reolink Enhanced"**
12. Enter `localhost:5000` (or your server IP:5000) and complete setup

**Note**: Apps are only supported on Home Assistant Operating System. If you have Home Assistant Container, see Option 2 or Option 1b below instead.

### Option 1b: Local Installation (Without GitHub, For Testing)

If you want to test the app without setting up a GitHub repository:

1. Copy this entire `reolink-nvr-ha-app` folder to your Home Assistant server at:
   - `/root/reolink-nvr-ha-app` (Docker installations)
   - `/home/homeassistant/reolink-nvr-ha-app` (HAOS)
   - Or mount it to the container at `/addons/`
2. In Home Assistant Supervisor, refresh the app store
3. Load the local app and configure it
4. Start the app

Or use the Docker Compose option below instead.

**Note**: This method is primarily for development and testing. For production use, GitHub publishing is recommended.

### Option 2: Docker Compose (Development)

```bash
cd reolink-nvr-ha-app
docker-compose up -d
```

Access API at `http://localhost:5000`

## Configuration

### NVR Settings
- **Host**: IP address of your Reolink NVR
- **Port**: Usually 80 (default) or 443 (SSL)
- **Username**: NVR admin username
- **Password**: NVR admin password
- **SSL**: Enable if using HTTPS

### Buffer & Clip Settings
- **Buffer Size**: 10-300 seconds (how much video to keep in memory)
- **Pre-Event Duration**: 1-30 seconds before event
- **Post-Event Duration**: 1-30 seconds after event

### Storage & Retention
- **Retention Days**: Keep clips for this many days (1-90)
- **Max Storage MB**: Maximum clip storage before auto-delete
- **External Storage**: Path to NAS/USB (optional)

## API Examples

### Health Check
```bash
curl http://localhost:5000/api/health
```

### Get Channels
```bash
curl http://localhost:5000/api/channels
```

### Search Recordings
```bash
curl "http://localhost:5000/api/search?channel=0&start_date=2024-06-01&event_type=person"
```

### Get Timeline
```bash
curl "http://localhost:5000/api/timeline?channel=0&hours=24"
```

### WebSocket Events
```bash
wscat -c ws://localhost:5000/ws/events
```

## Home Assistant Automation Examples

### Notify on Person Detection

```yaml
automation:
  - alias: "Front Door - Person Detected"
    trigger:
      platform: state
      entity_id: binary_sensor.camera_0_person
      to: "on"
    action:
      - service: notify.mobile_app_phone
        data:
          title: "Person Detected!"
          message: "Front camera detected a person"
```

### Send Video Clip Notification

```yaml
automation:
  - alias: "Front Door - Send Clip"
    trigger:
      platform: state
      entity_id: binary_sensor.camera_0_person
      to: "on"
    action:
      - service: reolink_enhanced.send_clip_notification
        data:
          channel: 0
          title: "Person Detected on Front Door"
          message: "Sending video clip..."
```

## Deploying to GitHub

To use your app with Home Assistant's app store, you need to push this project to GitHub:

### 1. Create a GitHub Repository

1. Go to https://github.com/new
2. Create a new repository named `reolink-nvr-ha-app`
3. Choose "Public" (required for Home Assistant app store)
4. Click "Create repository"

### 2. Push Your Code

```bash
cd c:\projects\reolink-nvr-ha-app
git init
git add .
git commit -m "Initial commit: Reolink Enhanced API"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/reolink-nvr-ha-app.git
git push -u origin main
```

Replace `YOUR-USERNAME` with your actual GitHub username.

### 3. Add to Home Assistant

1. In Home Assistant, go to **Settings → System → Supervisor** → **App Store**
2. Click **⋮ (menu)** → **Repositories**
3. Paste: `https://github.com/marcusmaday/reolink-nvr-ha-app`
4. Click **Create**
5. Search for "Reolink Enhanced" and install!

### 4. (Optional) Submit to Official Store

Once you have the repository set up, you can submit it to the official Home Assistant Community Apps repository for better discoverability. See the Home Assistant documentation for details.

---

## Troubleshooting

### Can't Connect to NVR
1. Check NVR IP address and port
2. Verify credentials (test in Reolink app)
3. Ensure NVR is reachable: `ping 192.168.1.100`
4. Check firewall rules

### High Memory Usage
- Reduce buffer size
- Disable buffer if not needed

### Storage Full
- Reduce retention days
- Lower max storage MB limit
- Check if external storage is properly mounted

### Missing Events
- Check NVR event configuration
- Increase buffer size to ensure capture
- Enable debug logs

## Support

For issues and feature requests:
- GitHub: https://github.com/marcusmaday/reolink-nvr-ha-app/issues
- Repository: https://github.com/marcusmaday/reolink-nvr-ha-app

See [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) for detailed documentation.
