"""Diagnostics with webhook credentials redacted."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_WEBHOOK_ID
from .manager import AppleHealthBridgeManager


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return non-secret diagnostic state."""
    manager: AppleHealthBridgeManager = entry.runtime_data
    return {
        "config": async_redact_data(dict(entry.data), {CONF_WEBHOOK_ID}),
        "received_metric_keys": sorted(manager.metrics),
        "has_location": bool(manager.location),
        "wifi_fields": sorted(manager.wifi),
        "last_sync": manager.data.get("last_sync"),
    }
