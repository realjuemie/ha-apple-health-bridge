"""Tests for the local JSON protocol."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest

COMPONENT_DIR = Path(__file__).parents[1] / "custom_components" / "apple_health_bridge"


def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, COMPONENT_DIR / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


package = types.ModuleType("apple_health_bridge")
package.__path__ = [str(COMPONENT_DIR)]
sys.modules["apple_health_bridge"] = package
_load_module("apple_health_bridge.const", "const.py")
protocol = _load_module("apple_health_bridge.protocol", "protocol.py")


class ProtocolTests(unittest.TestCase):
    def test_valid_full_payload(self) -> None:
        result = protocol.validate_payload(
            {
                "version": 1,
                "timestamp": "2026-08-03T10:30:00+08:00",
                "health": {"steps": {"value": "1234", "unit": "steps"}},
                "location": {"latitude": 31.2, "longitude": 121.4, "accuracy": 8},
                "wifi": {"ssid": "Home", "bssid": "AA:BB:CC:DD:EE:FF"},
            }
        )
        self.assertEqual(result["health"]["steps"]["value"], 1234.0)
        self.assertEqual(result["wifi"]["bssid"], "AA:BB:CC:DD:EE:FF")

    def test_requires_data_section(self) -> None:
        with self.assertRaises(protocol.PayloadError):
            protocol.validate_payload({"version": 1})

    def test_rejects_bad_metric_key(self) -> None:
        with self.assertRaises(protocol.PayloadError):
            protocol.validate_payload({"health": {"Bad Key": 1}})

    def test_rejects_out_of_range_location(self) -> None:
        with self.assertRaises(protocol.PayloadError):
            protocol.validate_payload(
                {"location": {"latitude": 91, "longitude": 0}}
            )

    def test_rejects_unknown_wifi_field(self) -> None:
        with self.assertRaises(protocol.PayloadError):
            protocol.validate_payload({"wifi": {"channel": 149}})

    def test_rejects_non_finite_number(self) -> None:
        with self.assertRaises(protocol.PayloadError):
            protocol.validate_payload({"health": {"steps": float("inf")}})


if __name__ == "__main__":
    unittest.main()
