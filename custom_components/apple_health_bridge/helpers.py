"""User-facing setup helpers."""

from homeassistant.components import persistent_notification, webhook
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .manager import AppleHealthBridgeManager


def create_setup_notification(
    hass: HomeAssistant, manager: AppleHealthBridgeManager
) -> None:
    """Show the LAN-only endpoint needed by Apple Shortcuts."""
    try:
        url = webhook.async_generate_url(
            hass,
            manager.webhook_id,
            allow_internal=True,
            allow_external=False,
            allow_ip=True,
            prefer_external=False,
        )
    except Exception:  # HA may not have an internal URL configured yet.
        url = f"http://HOME_ASSISTANT_IP:8123{webhook.async_generate_path(manager.webhook_id)}"

    persistent_notification.async_create(
        hass,
        (
            f"设备：**{manager.device_name}**\n\n"
            "请把下面的局域网地址填入苹果快捷指令的“获取 URL 内容”动作：\n\n"
            f"`{url}`\n\n"
            "请求方法使用 `POST`，正文类型使用 `JSON`。此地址等同密码，请勿公开。"
        ),
        title="Apple Health Bridge 快捷指令连接信息",
        notification_id=f"{DOMAIN}_{manager.entry_id}_setup",
    )
