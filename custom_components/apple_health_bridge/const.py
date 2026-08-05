"""Constants for Apple Health Bridge."""

from typing import Final

DOMAIN: Final = "apple_health_bridge"
PLATFORMS: Final = ["sensor", "device_tracker", "button"]

CONF_DEVICE_NAME: Final = "device_name"
CONF_WEBHOOK_ID: Final = "webhook_id"

STORAGE_VERSION: Final = 1
PAYLOAD_VERSION: Final = 1
MAX_PAYLOAD_BYTES: Final = 128 * 1024
MAX_HEALTH_METRICS: Final = 50

ATTR_CLIENT_TIMESTAMP: Final = "client_timestamp"
ATTR_HEALTH: Final = "health"
ATTR_LOCATION: Final = "location"
ATTR_WIFI: Final = "wifi"

SIGNAL_UPDATE: Final = f"{DOMAIN}_update"

KNOWN_HEALTH_METRICS: Final = {
    "steps": {"name": "步数", "unit": "steps", "icon": "mdi:walk"},
    "walking_running_distance": {
        "name": "步行与跑步距离",
        "unit": "km",
        "icon": "mdi:map-marker-distance",
        "device_class": "distance",
    },
    "active_energy": {
        "name": "活动能量",
        "unit": "kcal",
        "icon": "mdi:fire",
        "device_class": "energy",
    },
    "exercise_minutes": {
        "name": "锻炼时间",
        "unit": "min",
        "icon": "mdi:timer-outline",
        "device_class": "duration",
    },
    "stand_hours": {"name": "站立小时", "unit": "h", "icon": "mdi:human-handsup"},
    "heart_rate": {"name": "心率", "unit": "bpm", "icon": "mdi:heart-pulse"},
    "resting_heart_rate": {
        "name": "静息心率",
        "unit": "bpm",
        "icon": "mdi:heart-outline",
    },
    "blood_oxygen": {"name": "血氧", "unit": "%", "icon": "mdi:water-percent"},
    "respiratory_rate": {
        "name": "呼吸频率",
        "unit": "breaths/min",
        "icon": "mdi:lungs",
    },
    "sleep_duration": {
        "name": "睡眠时长",
        "unit": "h",
        "icon": "mdi:sleep",
        "device_class": "duration",
    },
    "weight": {
        "name": "体重",
        "unit": "kg",
        "icon": "mdi:scale-bathroom",
        "device_class": "weight",
    },
    "body_fat_percentage": {
        "name": "体脂率",
        "unit": "%",
        "icon": "mdi:percent",
    },
    "floors_climbed": {"name": "爬楼层数", "unit": "floors", "icon": "mdi:stairs"},
}

WIFI_FIELDS: Final = {
    "ssid": {"name": "Wi-Fi 名称", "icon": "mdi:wifi"},
    "bssid": {"name": "Wi-Fi BSSID", "icon": "mdi:router-wireless"},
}

# These entities existed in early releases but are neither collected by the
# shortcut nor useful for this integration. They are removed from the entity
# registry during setup so existing installations do not retain dead entries.
REMOVED_WIFI_FIELDS: Final = {"channel", "standard", "rate"}
