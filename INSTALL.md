# Installation & Configuration Guide

## Prerequisites

- Home Assistant Green (or any Home Assistant installation)
- Reolink NVR with HTTP API access enabled
- Network connectivity between Home Assistant and Reolink NVR
- NVR username and password

## Step 1: Add Repository to Home Assistant

1. Open Home Assistant
2. Go to **Settings** → **Add-ons** (in the sidebar)
3. Click the three-dot menu in the top right → **Repositories**
4. Click **Create Repository**
5. Enter the repository URL: `https://github.com/marcusmaday/reolink-nvr-ha-app`
6. Click **Create**

The repository will be added and you should see "Reolink NVR HA App" available.

## Step 2: Install the Add-on

1. In the Add-ons store, search for "Reolink NVR HA App"
2. Click on it and select **Install**
3. Wait for installation to complete

## Step 3: Configure the Add-on

1. Click on **Reolink NVR HA App** (in My Home Assistant sections)
2. Go to the **Configuration** tab
3. Fill in your NVR details:

```yaml
nvr_host: "192.168.1.100"        # IP address of your Reolink NVR
nvr_port: 80                       # Default HTTP port (443 for HTTPS)
nvr_username: "admin"              # NVR admin username
nvr_password: "your_password"      # NVR admin password
nvr_ssl: false                     # Use HTTPS (true/false)
debug: false                        # Enable debug logging (true/false)
api_port: 5000                     # API port (don't change unless needed)
```

**Important Notes:**
- The `nvr_host` must be reachable from Home Assistant (IP address, not hostname)
- Use port 80 for HTTP or 443 for HTTPS
- Ensure your NVR user has API access enabled
- Keep `api_port` as 5000 unless you have port conflicts

## Step 4: Start the Add-on

1. Go to the **Reolink NVR HA App** add-on page
2. Click the **Start** button
3. Check the **Logs** tab to verify it started successfully

You should see:
```
Starting Reolink NVR HA App...
Connecting to NVR at 192.168.1.100:80
Connected to NVR: [NVR Model]
Channels: [Number of channels]
```

## Step 5: Test the API

Open a web browser and test the API:

### Health Check
```
http://your-ha-ip:5000/api/health
```

You should see:
```json
{
  "status": "ok",
  "nvr_connected": true,
  "nvr_host": "192.168.1.100"
}
```

### Device Info
```
http://your-ha-ip:5000/api/device/info
```

### Interactive API Documentation
```
http://your-ha-ip:5000/docs
```

This opens Swagger UI with all available endpoints.

## Step 6: Use in Home Assistant Automations

Update your doorbell automation to reference the API:

```yaml
alias: "Doorbell: Notifications with Event Link"
triggers:
  - trigger: state
    entity_id: binary_sensor.front_door_visitor_2
    to: "on"
actions:
  - action: notify.mobile_app_pixel_8_pro
    data:
      title: "🔔 Doorbell"
      message: "Someone is at the door!"
      data:
        image: >-
          /local/tmp/doorbell_snapshot_pressed.jpg?v={{ now().timestamp() | int }}
        clickAction: >
          http://your-ha-ip:5000/api/search?channel=8&start_date={{now().strftime('%Y-%m-%d')}}&event_type=DOORBELL
```

Replace `your-ha-ip` with your Home Assistant IP address or Nabu Casa URL.

## Step 7: Configure a Dashboard Card (Optional)

Create a custom dashboard card to view recent doorbell events:

1. Create a new custom:html-card in your Lovelace dashboard
2. Add this HTML:

```yaml
type: custom:html-card
html: |
  <div id="clips-container"></div>
  <script>
    async function loadClips() {
      try {
        const today = new Date().toISOString().split('T')[0];
        const res = await fetch(
          `http://your-ha-ip:5000/api/search?channel=8&start_date=${today}&event_type=DOORBELL`
        );
        const data = await res.json();
        
        const html = data.clips.length > 0
          ? data.clips.map(clip => `
              <div style="border: 1px solid #ccc; padding: 10px; margin: 10px 0; border-radius: 5px;">
                <p><strong>${new Date(clip.timestamp).toLocaleString()}</strong> - ${clip.duration_seconds}s</p>
                <a href="${clip.stream_url}" target="_blank" style="color: #03a9f4; text-decoration: none;">
                  Watch Clip →
                </a>
              </div>
            `).join('')
          : '<p style="color: #999;">No doorbell events today</p>';
        
        document.getElementById('clips-container').innerHTML = html;
      } catch (e) {
        document.getElementById('clips-container').innerHTML = `<p style="color: #f44336;">Error: ${e.message}</p>`;
      }
    }
    loadClips();
  </script>
```

Replace `your-ha-ip` with your Home Assistant address.

## Troubleshooting

### Add-on won't start

1. Check the logs (Reolink NVR HA App → Logs)
2. Verify NVR credentials are correct
3. Ensure NVR is reachable from Home Assistant:
   ```bash
   # From Home Assistant terminal
   ping 192.168.1.100
   ```

### Health check fails (API running but NVR not connected)

1. Verify NVR IP address in configuration
2. Check username and password
3. Ensure NVR API/HTTP service is enabled in NVR settings
4. Check firewall between Home Assistant and NVR

### SSL/TLS Certificate Errors

1. If using HTTPS and getting certificate errors:
   - Set `nvr_ssl: false` if NVR uses self-signed certificate
   - Or update the certificate on your NVR

### API returns 503 Service Unavailable

1. Add-on is not running
2. NVR connection lost
3. Check logs for specific error message

### Search returns no clips

1. Verify channel number matches your setup
2. Ensure recordings exist for the selected date
3. Check event type filter (try without filtering first)
4. Try a wider date range

## Advanced Configuration

### Using Nabu Casa for Remote Access

If using Nabu Casa remote access, reference the API via your Nabu Casa URL:

```
https://your-url.ui.nabu.casa:8123/api/reolink-nvr-ha-app/search?channel=8&start_date=2025-01-10
```

**Note:** The exact URL depends on your Nabu Casa setup. Check your HA remote URL and append `/api/reolink-nvr-ha-app` to it.

### Environment Variables

If running outside Home Assistant, you can set environment variables instead of using the options UI:

```bash
export NVR_HOST=192.168.1.100
export NVR_PORT=80
export NVR_USERNAME=admin
export NVR_PASSWORD=password
export NVR_SSL=false
export DEBUG=false
export API_PORT=5000

python3 -m uvicorn main:app --host 0.0.0.0 --port 5000
```

## Support

For issues or questions:
- Check the [GitHub Issues](https://github.com/marcusmaday/reolink-nvr-ha-app/issues)
- Review the [API documentation](https://github.com/marcusmaday/reolink-nvr-ha-app#api-endpoints)
- See the [Development guide](DEVELOPMENT.md) for debugging

## Next Steps

After installation:
1. ✅ Set up and test the API
2. ✅ Update automations to use the API
3. ⬜ Create custom dashboard cards for clip viewing
4. ⬜ Integrate with other Home Assistant automations
