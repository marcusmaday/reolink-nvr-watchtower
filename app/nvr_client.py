"""
nvr_client.py

Low-level Reolink NVR communication wrapper.
Handles authentication, connection pooling, and API calls.
"""

import logging
from typing import Optional, Dict, Any

from reolink_aio.api import Host
from reolink_aio.exceptions import ReolinkError

logger = logging.getLogger(__name__)


class NVRClient:
    """
    Manages connection to Reolink NVR and provides normalized access to device data.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        use_https: bool = False,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_https = use_https
        self._host: Optional[Host] = None
        self._connected = False

    async def connect(self) -> bool:
        """
        Establish connection to NVR and retrieve device data.
        Returns True if successful, False otherwise.
        """
        try:
            self._host = Host(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                use_https=self.use_https,
            )
            await self._host.get_host_data()
            self._connected = True
            logger.info(
                "Connected to NVR: %s (%d channels)",
                self._host.nvr_name,
                self._host.num_channels,
            )
            return True
        except ReolinkError as e:
            logger.error("Reolink API error: %s", e)
            self._connected = False
            return False
        except Exception as e:
            logger.error("Unexpected connection error: %s", e)
            self._connected = False
            return False

    async def disconnect(self):
        """Safely disconnect from NVR."""
        if self._host:
            try:
                await self._host.logout()
                logger.info("Disconnected from NVR")
            except Exception as e:
                logger.warning("Error during logout: %s", e)
            finally:
                self._connected = False
                self._host = None

    @property
    def is_connected(self) -> bool:
        """Check if connected to NVR."""
        return self._connected and self._host is not None

    @property
    def api_host(self) -> Optional[Host]:
        """Get underlying reolink_aio Host instance."""
        if not self.is_connected:
            raise RuntimeError("NVR not connected")
        return self._host

    async def get_device_info(self) -> Dict[str, Any]:
        """Retrieve device information."""
        if not self.is_connected:
            raise RuntimeError("NVR not connected")

        host = self._host
        return {
            "model": host.model or "Unknown",
            "firmware_version": host.sw_version or "Unknown",
            "nvr_name": host.nvr_name or "Unknown",
            "mac_address": host.mac_address or "Unknown",
            "is_nvr": host.is_nvr,
            "num_channels": host.num_channels,
            "timezone": getattr(host, "timezone", "Unknown"),
        }

    async def get_channels(self) -> list[Dict[str, Any]]:
        """Retrieve list of all camera channels."""
        if not self.is_connected:
            raise RuntimeError("NVR not connected")

        host = self._host
        channels = []
        for i in range(host.num_channels):
            raw_name = host.camera_name(i) if hasattr(host, "camera_name") else None
            raw_model = host.camera_model(i) if hasattr(host, "camera_model") else None
            name = str(raw_name).strip() if raw_name is not None else ""
            model = str(raw_model).strip() if raw_model is not None else None

            placeholder_name = not name or name.lower() in {"unknown", f"channel {i}"}
            placeholder_model = not model or model.lower() == "unknown"
            enabled = not (placeholder_name and placeholder_model)

            channels.append({
                "channel": i,
                "name": name or (f"Channel {i}" if enabled else "Unknown"),
                "enabled": enabled,
                "model": model,
            })
        return channels

    async def get_rtsp_url(self, channel: int, stream: str = "sub") -> Optional[str]:
        """
        Get RTSP URL for a specific channel.
        stream: 'sub' (lower quality, lower bandwidth) or 'main' (higher quality)
        """
        if not self.is_connected:
            raise RuntimeError("NVR not connected")

        try:
            url = await self._host.get_rtsp_stream_source(channel, stream=stream)
            return url
        except Exception as e:
            logger.error("Failed to get RTSP URL for channel %d: %s", channel, e)
            return None

    async def ping(self) -> bool:
        """Verify connection is still alive."""
        if not self.is_connected:
            return False
        try:
            await self._host.get_host_data()
            return True
        except Exception as e:
            logger.warning("Ping failed: %s", e)
            self._connected = False
            return False
