"""
Configuration flow for Reolink Enhanced Integration.
"""

import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="localhost"): str,
        vol.Required(CONF_PORT, default=5000): int,
    }
)


class ReolinkEnhancedConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Reolink Enhanced."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        # Validate the input
        try:
            # Test connection to API
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"http://{user_input[CONF_HOST]}:{user_input[CONF_PORT]}/api/health"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        errors["base"] = "cannot_connect"
                    else:
                        data = await resp.json()
                        if not data.get("nvr_connected"):
                            errors["base"] = "nvr_not_connected"
        except Exception as e:
            _LOGGER.error("Error validating connection: %s", e)
            errors["base"] = "cannot_connect"

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=errors,
            )

        # Create config entry
        return self.async_create_entry(
            title=f"Reolink NVR ({user_input[CONF_HOST]})",
            data=user_input,
        )
