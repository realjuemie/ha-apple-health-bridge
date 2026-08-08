"""Payload validation independent from Home Assistant internals."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import math
import re
from typing import Any

from .const import MAX_HEALTH_METRICS, PAYLOAD_VERSION, WIFI_FIELDS

_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ALLOWED_METRIC_FIELDS = {"value", "unit", "name", "start", "end", "source"}
_ALLOWED_LOCATION_FIELDS = {
    "latitude",
    "longitude",
    "accuracy",
    "altitude",
    "vertical_accuracy",
    "timestamp",
}


class PayloadError(ValueError):
    """Raised when an incoming payload is invalid."""


def validate_payload(payload: Any) -> dict[str, Any]:
    """Validate and normalize a shortcut payload."""
    if not isinstance(payload, dict):
        raise PayloadError("JSON 根对象必须是字典")

    version = payload.get("version", PAYLOAD_VERSION)
    if version != PAYLOAD_VERSION:
        raise PayloadError(f"不支持的协议版本: {version}")

    normalized: dict[str, Any] = {"version": PAYLOAD_VERSION}
    if "timestamp" in payload:
        normalized["timestamp"] = _timestamp(payload["timestamp"], "timestamp")

    if "health" in payload:
        normalized["health"] = _health(payload["health"])
    if "location" in payload:
        normalized["location"] = _location(payload["location"])
    if "wifi" in payload:
        normalized["wifi"] = _wifi(payload["wifi"])

    if not any(key in normalized for key in ("health", "location", "wifi")):
        raise PayloadError("至少需要 health、location 或 wifi 中的一项")
    return normalized


def _health(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        raise PayloadError("health 必须是字典")
    if len(value) > MAX_HEALTH_METRICS:
        raise PayloadError(f"一次最多上传 {MAX_HEALTH_METRICS} 个健康指标")

    result: dict[str, dict[str, Any]] = {}
    for key, raw_metric in value.items():
        if not isinstance(key, str) or not _KEY_PATTERN.fullmatch(key):
            raise PayloadError(f"无效的健康指标键: {key!r}")
        metric = raw_metric if isinstance(raw_metric, dict) else {"value": raw_metric}
        unknown = set(metric) - _ALLOWED_METRIC_FIELDS
        if unknown:
            raise PayloadError(f"健康指标 {key} 包含未知字段: {sorted(unknown)}")
        if "value" not in metric:
            raise PayloadError(f"健康指标 {key} 缺少 value")

        item: dict[str, Any] = {"value": _number(metric["value"], f"health.{key}.value")}
        for field in ("unit", "name", "source"):
            if field in metric:
                item[field] = _short_string(metric[field], f"health.{key}.{field}", 80)
        for field in ("start", "end"):
            if field in metric:
                item[field] = _timestamp(metric[field], f"health.{key}.{field}")
        result[key] = item
    return result


def _location(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PayloadError("location 必须是字典")
    unknown = set(value) - _ALLOWED_LOCATION_FIELDS
    if unknown:
        raise PayloadError(f"location 包含未知字段: {sorted(unknown)}")
    if "latitude" not in value or "longitude" not in value:
        raise PayloadError("location 必须同时包含 latitude 和 longitude")

    latitude = _number(value["latitude"], "location.latitude")
    longitude = _number(value["longitude"], "location.longitude")
    if not -90 <= latitude <= 90:
        raise PayloadError("latitude 必须位于 -90 到 90")
    if not -180 <= longitude <= 180:
        raise PayloadError("longitude 必须位于 -180 到 180")

    result: dict[str, Any] = {"latitude": latitude, "longitude": longitude}
    for field in ("accuracy", "altitude", "vertical_accuracy"):
        if field in value:
            result[field] = _number(value[field], f"location.{field}")
    if result.get("accuracy", 0) < 0 or result.get("vertical_accuracy", 0) < 0:
        raise PayloadError("定位精度不能为负数")
    if "timestamp" in value:
        result["timestamp"] = _timestamp(value["timestamp"], "location.timestamp")
    return result


def _wifi(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PayloadError("wifi 必须是字典")
    unknown = set(value) - set(WIFI_FIELDS)
    if unknown:
        raise PayloadError(f"wifi 包含未知字段: {sorted(unknown)}")

    result: dict[str, Any] = {}
    for field, raw in value.items():
        if field in {"channel", "rate"} and isinstance(raw, (int, float)) and not isinstance(raw, bool):
            result[field] = _number(raw, f"wifi.{field}")
        else:
            result[field] = _short_string(raw, f"wifi.{field}", 120)
    return result


def _number(value: Any, path: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        if isinstance(value, str):
            text = value.strip().replace("\u00a0", " ").replace("\u202f", " ")
            # Shortcuts may localize a form value (for example, ``1,234 步``)
            # while serializing a numeric output. Accept the leading numeric
            # token and discard only a display unit, never arbitrary text.
            match = re.match(r"^[+-]?(?:\d[\d, ]*(?:\.\d+)?|\.\d+)", text)
            if match:
                token = match.group(0).replace(" ", "")
                if "," in token and "." not in token:
                    groups = token.split(",")
                    token = (
                        token.replace(",", ".")
                        if len(groups) == 2 and len(groups[1]) != 3
                        else token.replace(",", "")
                    )
                else:
                    token = token.replace(",", "")
                try:
                    value = float(token)
                except ValueError:
                    value = None
        if not isinstance(value, (int, float)):
            raise PayloadError(f"{path} 必须是数字")
    if not math.isfinite(value):
        raise PayloadError(f"{path} 必须是有限数字")
    return value


def _short_string(value: Any, path: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise PayloadError(f"{path} 必须是字符串")
    value = value.strip()
    if not value or len(value) > max_length:
        raise PayloadError(f"{path} 长度必须为 1 到 {max_length}")
    return value


def _timestamp(value: Any, path: str) -> str:
    text = _short_string(value, path, 64)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as err:
        raise PayloadError(f"{path} 必须是 ISO 8601 时间") from err
    return text


def storage_copy(data: dict[str, Any]) -> dict[str, Any]:
    """Return a safe snapshot for delayed storage writes."""
    return deepcopy(data)
