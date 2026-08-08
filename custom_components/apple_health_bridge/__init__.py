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
    KNOWN_HEALTH_METRICS,
    MAX_PAYLOAD_BYTES,
    PLATFORMS,
)
from .helpers import create_setup_notification
from .manager import AppleHealthBridgeManager
from .protocol import PayloadError, validate_payload

_LOGGER = logging.getLogger(__name__)


def _form_number(value: object) -> object:
    """Convert a form-encoded numeric value before protocol validation."""
    if isinstance(value, str):
        text = value.strip()
        try:
            return float(text)
        except ValueError:
            return value
    return value


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
        if request.method == "GET":
            return Response(
                text=manager.selection or "__AHB_SETUP_REQUIRED__",
                content_type="text/plain",
            )
        if request.content_length and request.content_length > MAX_PAYLOAD_BYTES:
            return json_response(
                {"ok": False, "error": "payload_too_large"},
                status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
        try:
            if request.content_type == "application/x-www-form-urlencoded":
                form = await request.post()
                selection = str(form.get("selection", "")).strip()
                if selection:
                    await manager.async_set_selection(selection)
                health = {
                    key: {"value": _form_number(value)}
                    for key, value in form.items()
                    if key in KNOWN_HEALTH_METRICS and str(value).strip()
                }
                raw_payload = {"version": 1, "health": health}
                if form.get("latitude") and form.get("longitude"):
                    raw_payload["location"] = {
                        key: form[key]
                        for key in ("latitude", "longitude", "altitude")
                        if form.get(key)
                    }
                wifi = {
                    key: form[key] for key in ("ssid", "bssid") if form.get(key)
                }
                if wifi:
                    raw_payload["wifi"] = wifi
                # The shortcut saves the first-run selection in a separate
                # request before collecting Health data. Treat it as a valid
                # successful request, so iOS does not stop the shortcut on a
                # 400 response before the actual sync starts.
                if selection and not health and "location" not in raw_payload and not wifi:
                    return Response(text="同步项目已保存", content_type="text/plain")
            else:
                raw_payload = await request.json()
        except Exception:
            raw_body = await request.read()
            preview = raw_body.decode("utf-8", errors="replace")[:512]
            return json_response(
                {
                    "ok": False,
                    "error": "invalid_json",
                    "content_type": request.content_type,
                    "body_preview": preview,
                },
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
        parts = [f"健康数据 {len(payload.get('health', {}))} 项"]
        if "location" in payload:
            parts.append("位置")
        if "wifi" in payload:
            parts.append("Wi-Fi")
        if new_metrics:
            parts.append(f"新增实体 {len(new_metrics)} 个")
        return Response(text="同步成功：" + "、".join(parts), content_type="text/plain")

    webhook.async_register(
        hass,
        DOMAIN,
        f"Apple Health Bridge: {manager.device_name}",
        manager.webhook_id,
        handle_webhook,
        # The webhook ID is an unguessable capability token.  Allowing remote
        # delivery is required for users who intentionally expose Home
        # Assistant through a reverse proxy or Cloudflare Tunnel.
        local_only=False,
        allowed_methods=("GET", "POST", "PUT"),
    )
    entry.async_on_unload(lambda: webhook.async_unregister(hass, manager.webhook_id))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if manager.is_first_setup:
        create_setup_notification(hass, manager)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the bridge and its entities."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
