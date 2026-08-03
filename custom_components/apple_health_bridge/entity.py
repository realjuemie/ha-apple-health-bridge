"""Base entity for Apple Health Bridge."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .manager import AppleHealthBridgeManager


class AppleHealthBridgeEntity(Entity):
    """Base entity linked to a configured Apple device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: AppleHealthBridgeManager, entry: ConfigEntry) -> None:
        self.manager = manager
        self.entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Group bridge entities under one HA device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.entry_id)},
            name=self.manager.device_name,
            manufacturer="Apple",
            model="Shortcuts Health Bridge",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe when the entity is active."""
        await super().async_added_to_hass()
        self.async_on_remove(self.manager.async_add_listener(self._handle_bridge_update))

    @callback
    def _handle_bridge_update(self, _new_metric_keys: set[str]) -> None:
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return None
