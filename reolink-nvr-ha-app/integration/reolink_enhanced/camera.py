"""
Reolink Enhanced Integration - Main Entity Setup
"""

import logging
from datetime import timedelta
from typing import Any, Dict

import aiohttp
from homeassistant.components.camera import Camera
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigType, async_add_entities: AddEntitiesCallback):
    """Set up Reolink Enhanced entities from a config entry."""
    host = entry.data.get(CONF_HOST, "localhost")
    port = entry.data.get(CONF_PORT, 5000)
    api_url = f"http://{host}:{port}"

    # Store API URL in hass.data for entity access
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = {
        "api_url": api_url,
    }

    # Fetch channels from API
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{api_url}/api/channels", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    channels = await resp.json()

                    # Create camera entity for each channel
                    entities = []
                    for channel_info in channels:
                        camera = ReolinkEnhancedCamera(
                            api_url=api_url,
                            channel=channel_info["channel"],
                            name=channel_info["name"],
                        )
                        entities.append(camera)

                        # Create binary sensor for motion detection
                        motion_sensor = ReolinkEnhancedMotionSensor(
                            api_url=api_url,
                            channel=channel_info["channel"],
                            name=f"{channel_info['name']} Motion",
                        )
                        entities.append(motion_sensor)

                    async_add_entities(entities)
                    _LOGGER.info("Added %d entities", len(entities))
                else:
                    _LOGGER.error("Failed to fetch channels: %s", resp.status)
    except Exception as e:
        _LOGGER.error("Error setting up entities: %s", e)


class ReolinkEnhancedCamera(Camera):
    """Reolink Enhanced Camera Entity."""

    def __init__(self, api_url: str, channel: int, name: str):
        """Initialize camera."""
        super().__init__()
        self.api_url = api_url
        self.channel = channel
        self._name = name
        self._attr_unique_id = f"reolink_enhanced_camera_{channel}"

    @property
    def name(self) -> str:
        """Return camera name."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return self._attr_unique_id

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return camera snapshot."""
        # In production, would fetch actual RTSP snapshot
        return None

    @property
    def motion_detection_enabled(self) -> bool:
        """Return True if motion detection is enabled."""
        return True


class ReolinkEnhancedMotionSensor(BinarySensorEntity):
    """Reolink Enhanced Motion Detection Sensor."""

    def __init__(self, api_url: str, channel: int, name: str):
        """Initialize sensor."""
        self.api_url = api_url
        self.channel = channel
        self._name = name
        self._attr_unique_id = f"reolink_enhanced_motion_{channel}"
        self._is_on = False

    @property
    def name(self) -> str:
        """Return sensor name."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return self._attr_unique_id

    @property
    def is_on(self) -> bool:
        """Return True if motion detected."""
        return self._is_on

    @property
    def device_class(self) -> str:
        """Return device class."""
        return "motion"

    async def async_update(self):
        """Update sensor state from API."""
        # In production, would fetch current motion state
        pass
