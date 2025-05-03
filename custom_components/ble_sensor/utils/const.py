"""Constants for the BLE Sensor integration."""
from typing import Final

DOMAIN: Final = "ble_sensor"
CONF_LOG_LEVEL: Final = "log_level"
CONF_DEVICE_TYPE: Final = "device_type"
CONF_MAC: Final = "mac"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_UPDATE_INTERVAL: Final = "update_interval"
CONF_POLL_INTERVAL: Final = "poll_interval"
CONF_RETRY_COUNT: Final = "retry_count"

DEFAULT_SCAN_INTERVAL: Final = 60
DEFAULT_UPDATE_INTERVAL: Final = 60
DEFAULT_POLL_INTERVAL: Final = 10
DEFAULT_RETRY_COUNT: Final = 3

# Device types
DEVICE_TYPES: Final = {
    "petkit_fountain": "Petkit Fountain",
    "soil_tester": "S-06 Soil Tester"
    # Add more device types as needed
}

# System health
SYSTEM_HEALTH_INFO: Final = "system_health_info"

# Signals
SIGNAL_DEVICE_UPDATE: Final = f"{DOMAIN}_device_update"
SIGNAL_DEVICE_AVAILABLE: Final = f"{DOMAIN}_device_available"
SIGNAL_DEVICE_UNAVAILABLE: Final = f"{DOMAIN}_device_unavailable"

# PETKIT FOUNTAIN
KEY_PF_MODEL_CODE = "model_code"
KEY_PF_MODEL_NAME = "model_name"
KEY_PF_ALIAS = "alias"
KEY_PF_BATTERY = "battery"
KEY_PF_POWER_STATUS = "power_status"
KEY_PF_MODE = "mode"
KEY_PF_DND_STATE = "dnd_state"
KEY_PF_WARN_BREAKDOWN = "warn_breakdown"
KEY_PF_WARN_WATER = "warn_water"
KEY_PF_WARN_FILTER = "warn_filter"
KEY_PF_PUMP_RUNTIME = "pump_runtime"
KEY_PF_FILTER_PERCENT = "filter_percent"
KEY_PF_RUNNING_STATUS = "running_status"


# S-06 SOIL TESTER
KEY_S06_TEMP = "temperature"
KEY_S06_RH = "humidity"
KEY_S06_PRESSURE = "pressure"
KEY_S06_BATTERY = "battery"