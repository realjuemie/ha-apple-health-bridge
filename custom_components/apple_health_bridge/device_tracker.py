"""Location entity reported by Apple Shortcuts."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import AppleHealthBridgeEntity
from .manager import AppleHealthBridgeManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the device tracker."""
    manager: AppleHealthBridgeManager = entry.runtime_data
    async_add_entities([AppleShortcutDeviceTracker(manager, entry)])


class AppleShortcutDeviceTracker(AppleHealthBridgeEntity, TrackerEntity):
    """Latest location sent by this Apple device."""

    _attr_name = "位置"
    _attr_icon = "mdi:map-marker"

    def __init__(self, manager: AppleHealthBridgeManager, entry: ConfigEntry) -> None:
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_location"

    @property
    def available(self) -> bool:
        return "latitude" in self.manager.location and "longitude" in self.manager.location

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        return self.manager.location.get("latitude")

    @property
    def longitude(self) -> float | None:
        return self.manager.location.get("longitude")

    @property
    def location_accuracy(self) -> int:
        return round(self.manager.location.get("accuracy", 0))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return {
            key: value
            for key, value in self.manager.location.items()
            if key in {"altitude", "vertical_accuracy", "timestamp"}
        }
