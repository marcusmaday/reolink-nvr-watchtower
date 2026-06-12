"""
Reolink Enhanced Integration for Home Assistant.

This custom integration connects to the Reolink Enhanced API add-on
and exposes cameras, sensors, and events to Home Assistant.
"""

import logging
from typing import Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

DOMAIN: Final = "reolink_enhanced"
VERSION: Final = "0.2.0"

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.CAMERA,
    Platform.BINARY_SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Reolink Enhanced from a config entry."""
    _LOGGER.info("Setting up Reolink Enhanced for %s:%s", entry.data.get("host"), entry.data.get("port"))

    # Initialize hass.data
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    hass.data[DOMAIN][entry.entry_id] = {
        "api_url": f"http://{entry.data.get('host', 'localhost')}:{entry.data.get('port', 5000)}",
    }

    # Set up all platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
