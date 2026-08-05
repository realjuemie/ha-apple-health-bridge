"""State manager for Apple Health Bridge."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, STORAGE_VERSION
from .protocol import storage_copy

UpdateListener = Callable[[set[str]], None]


class AppleHealthBridgeManager:
    """Own the latest locally received state for one Apple device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        device_name: str,
        webhook_id: str,
    ) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.device_name = device_name
        self.webhook_id = webhook_id
        self.store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{entry_id}",
            private=True,
        )
        self.data: dict[str, Any] = self._empty_data()
        self.is_first_setup = True
        self._listeners: set[UpdateListener] = set()

    async def async_load(self) -> None:
        """Load the most recently received values."""
        stored = await self.store.async_load()
        if isinstance(stored, dict):
            self.data.update(stored)
            self.is_first_setup = False

    async def async_update(self, payload: dict[str, Any]) -> set[str]:
        """Merge a validated payload and notify entities."""
        old_metric_keys = set(self.metrics)
        if health := payload.get("health"):
            self.data.setdefault("health", {}).update(deepcopy(health))
        if "location" in payload:
            self.data["location"] = deepcopy(payload["location"])
        if "wifi" in payload:
            self.data["wifi"] = deepcopy(payload["wifi"])

        self.data["client_timestamp"] = payload.get("timestamp")
        self.data["last_sync"] = dt_util.utcnow().isoformat()
        new_metric_keys = set(self.metrics) - old_metric_keys

        self.store.async_delay_save(lambda: storage_copy(self.data), delay=1)
        for listener in tuple(self._listeners):
            listener(new_metric_keys)
        return new_metric_keys

    @callback
    def async_add_listener(self, listener: UpdateListener) -> Callable[[], None]:
        """Subscribe to state updates."""
        self._listeners.add(listener)

        @callback
        def unsubscribe() -> None:
            self._listeners.discard(listener)

        return unsubscribe

    @property
    def metrics(self) -> dict[str, dict[str, Any]]:
        """Return health metric records."""
        return self.data.get("health", {})

    @property
    def location(self) -> dict[str, Any]:
        """Return location data."""
        return self.data.get("location", {})

    @property
    def wifi(self) -> dict[str, Any]:
        """Return Wi-Fi data."""
        return self.data.get("wifi", {})

    @property
    def selection(self) -> str | None:
        """Return the persisted shortcut selection, if configured."""
        value = self.data.get("selection")
        return value if isinstance(value, str) and value else None

    async def async_set_selection(self, selection: str) -> None:
        """Persist the shortcut selection for subsequent runs."""
        self.data["selection"] = selection
        self.store.async_delay_save(lambda: storage_copy(self.data), delay=1)

    @staticmethod
    def _empty_data() -> dict[str, Any]:
        return {
            "health": {},
            "location": {},
            "wifi": {},
            "client_timestamp": None,
            "last_sync": None,
        }
