"""Sensor platform for BLE Scanner integration."""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfPressure,
)

from .const import (
    DOMAIN,
    CONF_DEVICES,
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    CONF_POLLING_INTERVAL,
    DEFAULT_POLLING_INTERVAL,
    DEVICE_EXPECTED_SENSORS,
    ATTR_LAST_UPDATED,
    ATTR_RSSI,
    LOGGER_NAME,
    DEVICE_TYPE_PETKIT_FOUNTAIN, # Import device types for manufacturer check
    DEVICE_TYPE_S06_SOIL_TESTER,
    # Petkit Keys
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
    # S06 Keys
    KEY_S06_TEMP,
    KEY_S06_RH,
    KEY_S06_PRESSURE,
    KEY_S06_BATTERY,
)
from .coordinator import BLEScannerCoordinator

_LOGGER = logging.getLogger(LOGGER_NAME)

# How long before marking a device unavailable (factor of its polling interval)
UNAVAILABLE_TIMEOUT_BASE = timedelta(seconds=60) # Base timeout
UNAVAILABLE_TIMEOUT_FACTOR = 2 # Multiplier for polling interval

# Sensor Descriptions (Optional but good practice for defining attributes)
# Using a dictionary mapping sensor keys to descriptions
SENSOR_DESCRIPTIONS: Dict[str, SensorEntityDescription] = {
    # Common
    ATTR_RSSI: SensorEntityDescription(
        key=ATTR_RSSI,
        name="RSSI",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    # Petkit Fountain
    KEY_PF_MODEL_CODE: SensorEntityDescription(
        key=KEY_PF_MODEL_CODE,
        name="Model Code",
        icon="mdi:numeric",
        entity_registry_enabled_default=False, # Diagnostic
    ),
    KEY_PF_MODEL_NAME: SensorEntityDescription(
        key=KEY_PF_MODEL_NAME,
        name="Model Name",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False, # Diagnostic
    ),
    KEY_PF_ALIAS: SensorEntityDescription(
        key=KEY_PF_ALIAS,
        name="Alias",
        icon="mdi:tag",
        entity_registry_enabled_default=False, # Diagnostic
    ),
    KEY_PF_BATTERY: SensorEntityDescription(
        key=KEY_PF_BATTERY,
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KEY_PF_POWER_STATUS: SensorEntityDescription(
        key=KEY_PF_POWER_STATUS,
        name="Power Status",
        icon="mdi:power-plug", # Or mdi:power-plug-off
    ),
    KEY_PF_MODE: SensorEntityDescription(
        key=KEY_PF_MODE,
        name="Mode",
        icon="mdi:cog-outline", # Or mdi:water-sync for smart mode?
    ),
    KEY_PF_DND_STATE: SensorEntityDescription(
        key=KEY_PF_DND_STATE,
        name="DND State",
        icon="mdi:bell-sleep-outline", # Or mdi:bell-outline
    ),
    KEY_PF_WARN_BREAKDOWN: SensorEntityDescription(
        key=KEY_PF_WARN_BREAKDOWN,
        name="Warning Breakdown",
        icon="mdi:alert-circle-outline",
    ),
    KEY_PF_WARN_WATER: SensorEntityDescription(
        key=KEY_PF_WARN_WATER,
        name="Warning Water Missing",
        icon="mdi:water-alert-outline",
    ),
    KEY_PF_WARN_FILTER: SensorEntityDescription(
        key=KEY_PF_WARN_FILTER,
        name="Warning Filter",
        icon="mdi:filter-variant-alert",
    ),
    KEY_PF_PUMP_RUNTIME: SensorEntityDescription(
        key=KEY_PF_PUMP_RUNTIME,
        name="Pump Runtime",
        icon="mdi:timer-outline",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING, # Assuming it's total runtime
        device_class=SensorDeviceClass.DURATION,
    ),
    KEY_PF_FILTER_PERCENT: SensorEntityDescription(
        key=KEY_PF_FILTER_PERCENT,
        name="Filter Remaining",
        icon="mdi:filter-variant",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KEY_PF_RUNNING_STATUS: SensorEntityDescription(
        key=KEY_PF_RUNNING_STATUS,
        name="Running Status",
        icon="mdi:pump", # Or mdi:pump-off
    ),
    # S-06 Soil Tester
    KEY_S06_TEMP: SensorEntityDescription(
        key=KEY_S06_TEMP,
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KEY_S06_RH: SensorEntityDescription(
        key=KEY_S06_RH,
        name="Humidity", # Changed from Soil Moisture
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KEY_S06_PRESSURE: SensorEntityDescription(
        key=KEY_S06_PRESSURE,
        name="Pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KEY_S06_BATTERY: SensorEntityDescription(
        key=KEY_S06_BATTERY,
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Removed S06 Conductivity and pH descriptions
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities based on a config entry."""
    coordinator: BLEScannerCoordinator = hass.data[DOMAIN][entry.entry_id]
    devices_config = entry.options.get(CONF_DEVICES, [])
    sensors = []

    _LOGGER.info(f"Setting up sensors for {len(devices_config)} configured devices")

    for device_conf in devices_config:
        device_id = coordinator._get_device_identifier(device_conf)
        device_type = device_conf.get(CONF_DEVICE_TYPE)
        device_name = device_conf.get(CONF_DEVICE_NAME, f"BLE Device {device_id}")
        polling_interval = device_conf.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL)

        expected_keys = DEVICE_EXPECTED_SENSORS.get(device_type, [])
        if not expected_keys:
            _LOGGER.warning(f"No sensor keys defined for device type {device_type} (Device: {device_id}). Skipping sensor creation for this device.")
            continue

        _LOGGER.debug(f"Creating sensors for device {device_id} (Name: {device_name}, Type: {device_type}) with keys: {expected_keys}")

        # Create sensors for expected keys
        for key in expected_keys:
            sensors.append(
                BLEDeviceSensor(
                    coordinator,
                    device_id,
                    device_name,
                    device_type,
                    key,
                    polling_interval
                )
            )

        # Always create RSSI sensor
        sensors.append(
            BLEDeviceSensor(
                coordinator,
                device_id,
                device_name,
                device_type,
                ATTR_RSSI,
                polling_interval
            )
        )

    if sensors:
        _LOGGER.info(f"Adding {len(sensors)} sensor entities")
        async_add_entities(sensors)
    else:
        _LOGGER.info("No sensors to add")


class BLEDeviceSensor(CoordinatorEntity[BLEScannerCoordinator], SensorEntity):
    """Representation of a Sensor for a BLE device attribute."""

    _attr_has_entity_name = True # Use device name + sensor key as entity name

    def __init__(
        self,
        coordinator: BLEScannerCoordinator,
        device_id: str,
        device_name: str,
        device_type: str,
        sensor_key: str,
        polling_interval: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = device_name
        self._device_type = device_type
        self._sensor_key = sensor_key
        self._polling_interval = polling_interval

        # Generate unique ID: domain_deviceid_sensorkey
        self._attr_unique_id = f"{DOMAIN}_{self._device_id}_{self._sensor_key}".lower().replace(" ", "_")

        # Apply SensorEntityDescription if available
        if description := SENSOR_DESCRIPTIONS.get(self._sensor_key):
            self.entity_description = description
        else:
            # Fallback for keys not in SENSOR_DESCRIPTIONS
            self._attr_name = self._get_sensor_friendly_name(sensor_key)
            self._attr_state_class = SensorStateClass.MEASUREMENT # Default assumption

        # Set device information
        manufacturer = "Unknown"
        if self._device_type == DEVICE_TYPE_PETKIT_FOUNTAIN:
            manufacturer = "Petkit"
        elif self._device_type == DEVICE_TYPE_S06_SOIL_TESTER:
            manufacturer = "Generic" # Or Efento? Based on format

        # Device info will be automatically set by CoordinatorEntity based on the coordinator's device
        _LOGGER.debug(f"Initialized sensor: {self.unique_id} (Name: {self.name}, Device: {self._device_id})")


    def _get_sensor_friendly_name(self, key: str) -> str:
        """Generate a user-friendly name for the sensor key."""
        return key.replace("_", " ").capitalize()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        last_seen = self.coordinator.get_last_seen(self._device_id)
        if last_seen is None:
            _LOGGER.debug(f"Sensor {self.unique_id} unavailable: Device never seen.")
            return False

        # Calculate unavailability timeout: base + factor * polling interval
        timeout_seconds = UNAVAILABLE_TIMEOUT_BASE.total_seconds() + (UNAVAILABLE_TIMEOUT_FACTOR * self._polling_interval)
        unavailability_threshold = dt_util.utcnow() - timedelta(seconds=timeout_seconds)

        # Ensure last_seen is timezone-aware for comparison
        if last_seen.tzinfo is None:
            last_seen = dt_util.as_utc(last_seen)

        is_available = last_seen >= unavailability_threshold
        if not is_available:
             _LOGGER.debug(f"Sensor {self.unique_id} unavailable: Last seen {last_seen} is older than threshold {unavailability_threshold} (Timeout: {timeout_seconds}s)")

        # Also check if coordinator itself failed recently
        return is_available and self.coordinator.last_update_success

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data and self._device_id in self.coordinator.data:
            device_data = self.coordinator.data[self._device_id]
            value = device_data.get(self._sensor_key)
            return value
        return None # Return None if data is missing for this sensor

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        attrs = {}
        if self.coordinator.data and self._device_id in self.coordinator.data:
            device_data = self.coordinator.data[self._device_id]
            if ATTR_LAST_UPDATED in device_data:
                attrs[ATTR_LAST_UPDATED] = device_data[ATTR_LAST_UPDATED]
            # Add RSSI as attribute to all sensors except the RSSI sensor itself
            if self._sensor_key != ATTR_RSSI and ATTR_RSSI in device_data:
                 attrs[ATTR_RSSI] = device_data[ATTR_RSSI]
            # Add model name/code if available and not the sensor itself (Petkit specific)
            if self._device_type == DEVICE_TYPE_PETKIT_FOUNTAIN:
                if self._sensor_key != KEY_PF_MODEL_NAME and KEY_PF_MODEL_NAME in device_data:
                    attrs[KEY_PF_MODEL_NAME] = device_data[KEY_PF_MODEL_NAME]
                if self._sensor_key != KEY_PF_MODEL_CODE and KEY_PF_MODEL_CODE in device_data:
                    attrs[KEY_PF_MODEL_CODE] = device_data[KEY_PF_MODEL_CODE]
                if self._sensor_key != KEY_PF_ALIAS and KEY_PF_ALIAS in device_data:
                    attrs[KEY_PF_ALIAS] = device_data[KEY_PF_ALIAS]

        # Add config info
        attrs["device_type"] = self._device_type
        attrs["device_identifier"] = self._device_id
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


