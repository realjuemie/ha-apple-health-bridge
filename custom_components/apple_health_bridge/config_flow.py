"""Config flow for Apple Health Bridge."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.components import webhook
from homeassistant.helpers import selector

from .const import CONF_DEVICE_NAME, CONF_WEBHOOK_ID, DOMAIN


class AppleHealthBridgeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create one local webhook per Apple device."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle setup from the integrations UI."""
        errors: dict[str, str] = {}
        if user_input is not None:
            device_name = user_input[CONF_DEVICE_NAME].strip()
            if not device_name or len(device_name) > 64:
                errors[CONF_DEVICE_NAME] = "invalid_device_name"
            else:
                return self.async_create_entry(
                    title=device_name,
                    data={
                        CONF_DEVICE_NAME: device_name,
                        CONF_WEBHOOK_ID: webhook.async_generate_id(),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_NAME, default="iPhone"): selector.TextSelector()
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
