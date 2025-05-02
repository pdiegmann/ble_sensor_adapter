# custom_components/ble_scanner/sensor.py
"""Sensor platform for BLE Scanner integration."""
import logging
from typing import Any, Dict, Optional # Removed Set, Tuple

from homeassistant.components.sensor import (
    SensorDeviceClass, # Keep
    SensorEntity,
    SensorStateClass,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ( # Import necessary constants
    PERCENTAGE, # Keep
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT, # Keep
    UnitOfTemperature, # Keep
    UnitOfTime,
    UnitOfPressure,
)
from homeassistant.core import HomeAssistant, callback
# Removed DeviceEntryType, DeviceInfo, dt_util
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity


from custom_components.ble_scanner.const import (
    DOMAIN,
    CONF_DEVICE_TYPE, # Needed to get device type from config entry
    DEVICE_EXPECTED_SENSORS,
    ATTR_LAST_UPDATED,
    ATTR_RSSI,
    LOGGER_NAME,
    # Keep device type constants if needed for logic, but keys are primary
    DEVICE_TYPE_PETKIT_FOUNTAIN,
    DEVICE_TYPE_S06_SOIL_TESTER,
    # Keep all sensor keys used in SENSOR_DESCRIPTIONS
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
    KEY_S06_TEMP,
    KEY_S06_RH,
    KEY_S06_PRESSURE,
    KEY_S06_BATTERY,
)
from custom_components.ble_scanner.coordinator import BleScannerCoordinator # Removed CoordinatorData

_LOGGER = logging.getLogger(LOGGER_NAME)

# Sensor Descriptions remain largely the same, used by BleSensor __init__
SENSOR_DESCRIPTIONS: Dict[str, SensorEntityDescription] = {
    # Common
    ATTR_RSSI: SensorEntityDescription(
        key=ATTR_RSSI,
        translation_key="signal_strength",
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
        entity_registry_enabled_default=False,
    ),
    KEY_PF_MODEL_NAME: SensorEntityDescription(
        key=KEY_PF_MODEL_NAME,
        name="Model Name",
        icon="mdi:information-outline",
        entity_registry_enabled_default=False,
    ),
    KEY_PF_ALIAS: SensorEntityDescription(
        key=KEY_PF_ALIAS,
        name="Alias",
        icon="mdi:tag",
        entity_registry_enabled_default=False,
    ),
    KEY_PF_BATTERY: SensorEntityDescription(
        key=KEY_PF_BATTERY,
        translation_key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KEY_PF_POWER_STATUS: SensorEntityDescription(
        key=KEY_PF_POWER_STATUS,
        name="Power Status",
        icon="mdi:power-plug",
    ),
    KEY_PF_MODE: SensorEntityDescription(
        key=KEY_PF_MODE,
        name="Mode",
        icon="mdi:cog-outline",
    ),
    KEY_PF_DND_STATE: SensorEntityDescription(
        key=KEY_PF_DND_STATE,
        name="DND State",
        icon="mdi:bell-sleep-outline",
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
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.DURATION,
    ),
    KEY_PF_FILTER_PERCENT: SensorEntityDescription(
        key=KEY_PF_FILTER_PERCENT,
        translation_key="filter_life",
        icon="mdi:filter-variant",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KEY_PF_RUNNING_STATUS: SensorEntityDescription(
        key=KEY_PF_RUNNING_STATUS,
        name="Running Status",
        icon="mdi:pump",
    ),
    # S-06 Soil Tester
    KEY_S06_TEMP: SensorEntityDescription(
        key=KEY_S06_TEMP,
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KEY_S06_RH: SensorEntityDescription(
        key=KEY_S06_RH,
        translation_key="humidity",
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
        translation_key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BLE Scanner sensor entities based on config entry."""
    coordinator: BleScannerCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_type = entry.data.get(CONF_DEVICE_TYPE)

    if not device_type:
        _LOGGER.error(f"Device type not found in config entry data: {entry.entry_id}")
        return

    expected_keys = DEVICE_EXPECTED_SENSORS.get(device_type, [])
    # Always add RSSI sensor
    all_sensor_keys = set(expected_keys) | {ATTR_RSSI}

    sensors_to_add = []
    for sensor_key in all_sensor_keys:
        # Check if a description exists, otherwise skip (or create a basic one)
        # For now, we assume keys in DEVICE_EXPECTED_SENSORS have descriptions
        if sensor_key in SENSOR_DESCRIPTIONS:
            _LOGGER.debug(f"Creating sensor '{sensor_key}' for device {coordinator.config_entry.unique_id}")
            sensors_to_add.append(BleSensor(coordinator, sensor_key))
        else:
             _LOGGER.warning(f"No SensorEntityDescription found for key '{sensor_key}' of device type '{device_type}'. Skipping sensor creation.")


    if sensors_to_add:
        async_add_entities(sensors_to_add)

# Removed the dynamic update logic (_async_update_sensors and listener)


class BleSensor(CoordinatorEntity[BleScannerCoordinator], SensorEntity):
    """Representation of a Sensor for a BLE device attribute, linked to a coordinator."""

    _attr_has_entity_name = True # Sensor name will be based on entity_description

    def __init__(
        self,
        coordinator: BleScannerCoordinator,
        sensor_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_key = sensor_key

        # Apply SensorEntityDescription
        # This sets name, device_class, unit_of_measurement, etc.
        self.entity_description = SENSOR_DESCRIPTIONS[self._sensor_key]

        # Generate unique ID: entry_unique_id_sensorkey
        # Assuming entry.unique_id is the MAC address
        if coordinator.config_entry.unique_id:
            safe_address = coordinator.config_entry.unique_id.replace(":", "")
            self._attr_unique_id = f"{safe_address}_{self._sensor_key}"
        else:
            # Fallback if unique_id is somehow missing (should not happen)
            self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self._sensor_key}"
            _LOGGER.warning(f"Config entry {coordinator.config_entry.entry_id} lacks a unique_id. Using entry_id for sensor unique_id.")


        # Construct device info to link this sensor entity to the device entry
        # created by the config entry. Use the config entry's unique_id (MAC address)
        # as the identifier within the integration's domain.
        device_info = {
            "identifiers": {(DOMAIN, coordinator.config_entry.unique_id)},
        }
        # Add device name from the handler if available
        if coordinator._device_handler and coordinator._device_handler.name:
             device_info["name"] = coordinator._device_handler.name
        # TODO: Consider adding manufacturer/model from handler if available

        self._attr_device_info = device_info

        _LOGGER.debug(f"Initialized sensor: {self.unique_id} (Coordinator: {coordinator.name})")

    # Removed _set_device_info method

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Availability is determined by the coordinator's success
        return super().available and self.coordinator.data is not None

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        # Get the specific sensor value from the coordinator's data dictionary
        if self.coordinator.data:
            value = self.coordinator.data.get(self._sensor_key)
            # _LOGGER.debug(f"Sensor {self.unique_id} value: {value}")
            return value
        # _LOGGER.debug(f"Sensor {self.unique_id}: No data available from coordinator.")
        return None # Return None if coordinator data is missing

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        attrs = {}
        # Add common attributes from the coordinator's data if available
        if self.coordinator.data:
            if ATTR_LAST_UPDATED in self.coordinator.data:
                attrs[ATTR_LAST_UPDATED] = self.coordinator.data[ATTR_LAST_UPDATED]

            # Add RSSI if this isn't the RSSI sensor itself
            if self._sensor_key != ATTR_RSSI and ATTR_RSSI in self.coordinator.data:
                 attrs[ATTR_RSSI] = self.coordinator.data[ATTR_RSSI]

        return attrs