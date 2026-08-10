"""Button entities for Apple Health Bridge."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import AppleHealthBridgeEntity
from .helpers import create_setup_notification
from .manager import AppleHealthBridgeManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up bridge helper buttons."""
    manager: AppleHealthBridgeManager = entry.runtime_data
    async_add_entities([
        ShowSetupInfoButton(manager, entry),
        ResetHealthSourceButton(manager, entry),
    ])


class ShowSetupInfoButton(AppleHealthBridgeEntity, ButtonEntity):
    """Show the secret local webhook URL in a persistent notification."""

    _attr_name = "显示快捷指令连接信息"
    _attr_icon = "mdi:link-variant"

    def __init__(self, manager: AppleHealthBridgeManager, entry: ConfigEntry) -> None:
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_show_setup_info"

    async def async_press(self) -> None:
        create_setup_notification(self.hass, self.manager)


class ResetHealthSourceButton(AppleHealthBridgeEntity, ButtonEntity):
    """Clear the selected HealthKit source and trigger a new picker run."""

    _attr_name = "重置健康数据来源"
    _attr_icon = "mdi:source-branch-refresh"

    def __init__(self, manager: AppleHealthBridgeManager, entry: ConfigEntry) -> None:
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_reset_health_source"

    async def async_press(self) -> None:
        await self.manager.async_clear_health_source()
