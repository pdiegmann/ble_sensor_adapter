"""Constants for the BLE Scanner integration."""

DOMAIN = "ble_scanner"

# Configuration Defaults
DEFAULT_POLLING_INTERVAL = 300  # 5 minutes
DEFAULT_LOG_LEVEL = "info"

# Configuration Keys
CONF_DEVICES = "devices"
CONF_DEVICE_NAME = "name"
CONF_DEVICE_ADDRESS = "address"
CONF_DEVICE_TYPE = "type"
CONF_POLLING_INTERVAL = "polling_interval"
CONF_LOG_LEVEL = "log_level"

# Device Types
DEVICE_TYPE_PETKIT_FOUNTAIN = "petkit-fountain"
DEVICE_TYPE_S06_SOIL_TESTER = "s-06-soil-tester"
SUPPORTED_DEVICE_TYPES = [
    DEVICE_TYPE_PETKIT_FOUNTAIN,
    DEVICE_TYPE_S06_SOIL_TESTER,
]

# Attributes / Sensor Keys
ATTR_LAST_UPDATED = "last_updated"
ATTR_RSSI = "rssi"

# --- Petkit Fountain Sensor Keys (Based on PetkitW5BLEMQTT library analysis) ---
KEY_PF_MODEL_CODE = "model_code"
KEY_PF_MODEL_NAME = "model_name"
KEY_PF_ALIAS = "alias"
KEY_PF_BATTERY = "battery" # If Battery Service (0x180F) is advertised
KEY_PF_POWER_STATUS = "power_status"
KEY_PF_MODE = "mode"
KEY_PF_DND_STATE = "dnd_state"
KEY_PF_WARN_BREAKDOWN = "warning_breakdown"
KEY_PF_WARN_WATER = "warning_water_missing"
KEY_PF_WARN_FILTER = "warning_filter"
KEY_PF_PUMP_RUNTIME = "pump_runtime"
KEY_PF_FILTER_PERCENT = "filter_percentage"
KEY_PF_RUNNING_STATUS = "running_status"

# --- S-06 Soil Tester Expected Keys (Based on main.py analysis) ---
KEY_S06_TEMP = "temperature"
KEY_S06_RH = "rh" # Relative Humidity
KEY_S06_PRESSURE = "pressure"
KEY_S06_BATTERY = "battery"
# Removed KEY_S06_MOISTURE, KEY_S06_CONDUCTIVITY, KEY_S06_PH as they are not in the parsed data

# Map device types to their expected sensor keys (excluding RSSI/LastUpdated)
DEVICE_EXPECTED_SENSORS = {
    DEVICE_TYPE_PETKIT_FOUNTAIN: [
        KEY_PF_MODEL_CODE,
        KEY_PF_MODEL_NAME,
        KEY_PF_ALIAS,
        KEY_PF_BATTERY,
        KEY_PF_POWER_STATUS,
        KEY_PF_MODE,
        KEY_PF_DND_STATE,
        KEY_PF_WARN_BREAKDOWN,
        KEY_PF_WARN_WATER,
        KEY_PF_WARN_FILTER,
        KEY_PF_PUMP_RUNTIME,
        KEY_PF_FILTER_PERCENT,
        KEY_PF_RUNNING_STATUS,
    ],
    DEVICE_TYPE_S06_SOIL_TESTER: [
        KEY_S06_TEMP,
        KEY_S06_RH,
        KEY_S06_PRESSURE,
        KEY_S06_BATTERY,
    ],
}

# Logger name
LOGGER_NAME = "custom_components.ble_scanner"

