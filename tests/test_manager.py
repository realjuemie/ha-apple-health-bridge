"""Tests for bridge state merging without a Home Assistant runtime."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
import types
import unittest

COMPONENT_DIR = Path(__file__).parents[1] / "custom_components" / "apple_health_bridge"


def _install_homeassistant_stubs() -> None:
    homeassistant = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")
    helpers = types.ModuleType("homeassistant.helpers")
    storage = types.ModuleType("homeassistant.helpers.storage")
    util = types.ModuleType("homeassistant.util")
    dt = types.ModuleType("homeassistant.util.dt")

    class HomeAssistant:
        pass

    class Store:
        def __class_getitem__(cls, _item):
            return cls

        def __init__(self, *_args, **_kwargs) -> None:
            self.saved = None

        def async_delay_save(self, snapshot, *, delay: int) -> None:
            self.saved = snapshot()

    core.HomeAssistant = HomeAssistant
    core.callback = lambda func: func
    storage.Store = Store
    dt.utcnow = lambda: datetime.now(timezone.utc)
    util.dt = dt
    helpers.storage = storage
    homeassistant.core = core
    homeassistant.helpers = helpers
    homeassistant.util = util
    sys.modules.update(
        {
            "homeassistant": homeassistant,
            "homeassistant.core": core,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.storage": storage,
            "homeassistant.util": util,
            "homeassistant.util.dt": dt,
        }
    )


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, COMPONENT_DIR / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_install_homeassistant_stubs()
package = types.ModuleType("apple_health_bridge")
package.__path__ = [str(COMPONENT_DIR)]
sys.modules["apple_health_bridge"] = package
_load_module("apple_health_bridge.const", "const.py")
_load_module("apple_health_bridge.protocol", "protocol.py")
manager_module = _load_module("apple_health_bridge.manager", "manager.py")


class ManagerWifiTests(unittest.IsolatedAsyncioTestCase):
    async def test_cellular_sync_clears_stale_wifi(self) -> None:
        manager = manager_module.AppleHealthBridgeManager(
            None, "entry", "iPhone", "webhook"
        )
        manager.data["wifi"] = {
            "ssid": "Old Network",
            "bssid": "AA:BB:CC:DD:EE:FF",
        }

        await manager.async_update(
            {"version": 1, "health": {"steps": {"value": 123}}},
            wifi_available=False,
        )

        self.assertEqual(manager.wifi, {})
        self.assertEqual(manager.metrics["steps"]["value"], 123)

    async def test_wifi_details_repopulate_after_main_request(self) -> None:
        manager = manager_module.AppleHealthBridgeManager(
            None, "entry", "iPhone", "webhook"
        )
        manager.data["wifi"] = {"ssid": "Old Network", "bssid": "old"}

        await manager.async_update(
            {"version": 1, "health": {}}, wifi_available=True
        )
        self.assertEqual(manager.wifi, {})

        await manager.async_update(
            {"version": 1, "wifi": {"ssid": "Current Network"}}
        )
        self.assertEqual(manager.wifi, {"ssid": "Current Network"})


if __name__ == "__main__":
    unittest.main()
