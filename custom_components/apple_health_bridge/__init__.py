"""Apple Health Bridge integration."""

from __future__ import annotations

from http import HTTPStatus
import logging

from aiohttp.web import Request, Response, json_response

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_DEVICE_NAME,
    CONF_WEBHOOK_ID,
    DOMAIN,
    MAX_PAYLOAD_BYTES,
    PLATFORMS,
)
from .helpers import create_setup_notification
from .manager import AppleHealthBridgeManager
from .protocol import PayloadError, validate_payload

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one Apple Health Bridge device."""
    manager = AppleHealthBridgeManager(
        hass,
        entry.entry_id,
        entry.data[CONF_DEVICE_NAME],
        entry.data[CONF_WEBHOOK_ID],
    )
    await manager.async_load()
    entry.runtime_data = manager

    async def handle_webhook(
        _hass: HomeAssistant, _webhook_id: str, request: Request
    ) -> Response:
        if request.content_length and request.content_length > MAX_PAYLOAD_BYTES:
            return json_response(
                {"ok": False, "error": "payload_too_large"},
                status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
        try:
            raw_payload = await request.json()
        except Exception:
            return json_response(
                {"ok": False, "error": "invalid_json"},
                status=HTTPStatus.BAD_REQUEST,
            )
        try:
            payload = validate_payload(raw_payload)
        except PayloadError as err:
            return json_response(
                {"ok": False, "error": "invalid_payload", "detail": str(err)},
                status=HTTPStatus.BAD_REQUEST,
            )

        new_metrics = await manager.async_update(payload)
        return json_response(
            {
                "ok": True,
                "received": {
                    "health": len(payload.get("health", {})),
                    "location": "location" in payload,
                    "wifi": "wifi" in payload,
                },
                "new_entities": sorted(new_metrics),
            }
        )

    webhook.async_register(
        hass,
        DOMAIN,
        f"Apple Health Bridge: {manager.device_name}",
        manager.webhook_id,
        handle_webhook,
        local_only=True,
        allowed_methods=("POST", "PUT"),
    )
    entry.async_on_unload(lambda: webhook.async_unregister(hass, manager.webhook_id))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if manager.is_first_setup:
        create_setup_notification(hass, manager)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the bridge and its entities."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
