"""Sensor entities for health and Wi-Fi values."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import KNOWN_HEALTH_METRICS, WIFI_FIELDS
from .entity import AppleHealthBridgeEntity
from .manager import AppleHealthBridgeManager


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors and add new metric entities at runtime."""
    manager: AppleHealthBridgeManager = entry.runtime_data
    # Always expose the supported Health entities.  They remain unavailable
    # until the shortcut uploads a value, which makes setup observable even
    # when HealthKit has not returned a sample yet.
    known_metric_keys: set[str] = set(KNOWN_HEALTH_METRICS) | set(manager.metrics)

    entities: list[SensorEntity] = [
        AppleHealthLastSyncSensor(manager, entry),
        *(AppleHealthWifiSensor(manager, entry, key) for key in WIFI_FIELDS),
        *(AppleHealthMetricSensor(manager, entry, key) for key in sorted(known_metric_keys)),
    ]
    async_add_entities(entities)

    @callback
    def add_new_metric_entities(new_metric_keys: set[str]) -> None:
        keys = new_metric_keys - known_metric_keys
        if not keys:
            return
        known_metric_keys.update(keys)
        async_add_entities(
            [AppleHealthMetricSensor(manager, entry, key) for key in sorted(keys)]
        )

    entry.async_on_unload(manager.async_add_listener(add_new_metric_entities))


class AppleHealthMetricSensor(AppleHealthBridgeEntity, SensorEntity):
    """A dynamically created HealthKit metric sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, manager: AppleHealthBridgeManager, entry: ConfigEntry, metric_key: str
    ) -> None:
        super().__init__(manager, entry)
        self.metric_key = metric_key
        definition = KNOWN_HEALTH_METRICS.get(metric_key, {})
        metric = manager.metrics.get(metric_key, {})
        self._attr_unique_id = f"{entry.entry_id}_health_{metric_key}"
        self._attr_name = metric.get("name") or definition.get("name") or metric_key.replace("_", " ").title()
        self._attr_icon = definition.get("icon", "mdi:heart-pulse")
        if device_class := definition.get("device_class"):
            self._attr_device_class = SensorDeviceClass(device_class)

    @property
    def available(self) -> bool:
        return self.metric_key in self.manager.metrics

    @property
    def native_value(self) -> int | float | None:
        return self.manager.metrics.get(self.metric_key, {}).get("value")

    @property
    def native_unit_of_measurement(self) -> str | None:
        metric = self.manager.metrics.get(self.metric_key, {})
        definition = KNOWN_HEALTH_METRICS.get(self.metric_key, {})
        return metric.get("unit") or definition.get("unit")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        metric = self.manager.metrics.get(self.metric_key, {})
        attrs = {
            key: value
            for key, value in metric.items()
            if key in {"start", "end", "source"} and value is not None
        }
        attrs["client_timestamp"] = self.manager.data.get("client_timestamp")
        return attrs


class AppleHealthWifiSensor(AppleHealthBridgeEntity, SensorEntity):
    """A Wi-Fi detail reported by Shortcuts."""

    def __init__(
        self, manager: AppleHealthBridgeManager, entry: ConfigEntry, field: str
    ) -> None:
        super().__init__(manager, entry)
        definition = WIFI_FIELDS[field]
        self.field = field
        self._attr_unique_id = f"{entry.entry_id}_wifi_{field}"
        self._attr_name = definition["name"]
        self._attr_icon = definition["icon"]
        self._attr_native_unit_of_measurement = definition.get("unit")
        if self._attr_native_unit_of_measurement:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def available(self) -> bool:
        return self.field in self.manager.wifi

    @property
    def native_value(self) -> Any:
        return self.manager.wifi.get(self.field)


class AppleHealthLastSyncSensor(AppleHealthBridgeEntity, SensorEntity):
    """Timestamp of the last accepted local payload."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:cloud-sync-outline"
    _attr_name = "上次同步"

    def __init__(self, manager: AppleHealthBridgeManager, entry: ConfigEntry) -> None:
        super().__init__(manager, entry)
        self._attr_unique_id = f"{entry.entry_id}_last_sync"

    @property
    def available(self) -> bool:
        return self.manager.data.get("last_sync") is not None

    @property
    def native_value(self) -> datetime | None:
        value = self.manager.data.get("last_sync")
        return dt_util.parse_datetime(value) if value else None
