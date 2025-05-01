# custom_components/ble_scanner/sensor.py
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
from homeassistant.const import ( # Import necessary constants
    CONF_ADDRESS,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfPressure,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo # Import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util


from .const import (
    DOMAIN,
    # CONF_DEVICES, # No longer needed here
    CONF_DEVICE_ADDRESS, # Use this constant
    CONF_DEVICE_NAME, # Still used for fallback naming
    CONF_DEVICE_TYPE,
    CONF_POLLING_INTERVAL,
    DEFAULT_POLLING_INTERVAL,
    DEVICE_EXPECTED_SENSORS,
    ATTR_LAST_UPDATED,
    ATTR_RSSI,
    LOGGER_NAME,
    DEVICE_TYPE_PETKIT_FOUNTAIN,
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
UNAVAILABLE_TIMEOUT_FACTOR = 2.5 # Increased factor slightly

# Sensor Descriptions (Optional but good practice for defining attributes)
# Using a dictionary mapping sensor keys to descriptions
SENSOR_DESCRIPTIONS: Dict[str, SensorEntityDescription] = {
    # Common
    ATTR_RSSI: SensorEntityDescription(
        key=ATTR_RSSI,
        translation_key="signal_strength", # Use translation key
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False, # Usually diagnostic
    ),
    # Petkit Fountain
    KEY_PF_MODEL_CODE: SensorEntityDescription(
        key=KEY_PF_MODEL_CODE,
        name="Model Code", # Keep specific names if no translation needed
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
        name="Pressure", # No standard translation key?
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
    """Set up sensor entities for a specific BLE device config entry."""
    coordinator: BLEScannerCoordinator = hass.data[DOMAIN][entry.entry_id]
    sensors = []

    # Get device details directly from the entry
    device_address = entry.data[CONF_DEVICE_ADDRESS]
    device_type = entry.data[CONF_DEVICE_TYPE]
    # Use entry title as the primary name, fallback to type/address
    device_name = entry.title or f"{device_type} {device_address}"
    # Get polling interval from options, fallback to data, then default
    polling_interval = entry.options.get(
        CONF_POLLING_INTERVAL, entry.data.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL)
    )

    _LOGGER.info(f"Setting up sensors for device: {device_address} (Name: {device_name}, Type: {device_type})")

    expected_keys = DEVICE_EXPECTED_SENSORS.get(device_type, [])
    if not expected_keys:
        _LOGGER.warning(f"No sensor keys defined for device type {device_type} (Device: {device_address}). Only RSSI sensor will be created.")
        # Still create RSSI sensor even if no others are defined
        expected_keys = [] # Ensure loop below doesn't run if empty

    _LOGGER.debug(f"Expected sensor keys for {device_address}: {expected_keys}")

    # Create sensors for expected keys for this specific device
    for key in expected_keys:
        sensors.append(
            BLEDeviceSensor(
                coordinator,
                device_address, # Pass address as device_id
                device_name,
                device_type,
                key,
                # polling_interval, # Polling interval is handled by coordinator
                entry.entry_id, # Pass entry_id for linking
            )
        )

    # Always create RSSI sensor for this device
    sensors.append(
        BLEDeviceSensor(
            coordinator,
            device_address, # Pass address as device_id
            device_name,
            device_type,
            ATTR_RSSI,
            # polling_interval, # Polling interval is handled by coordinator
            entry.entry_id, # Pass entry_id for linking
        )
    )

    if sensors:
        _LOGGER.info(f"Adding {len(sensors)} sensor entities for {device_address}")
        async_add_entities(sensors)
    else:
        _LOGGER.info(f"No sensors to add for {device_address}")


class BLEDeviceSensor(CoordinatorEntity[BLEScannerCoordinator], SensorEntity):
    """Representation of a Sensor for a BLE device attribute."""

    _attr_has_entity_name = True # Use device name + sensor key as entity name

    def __init__(
        self,
        coordinator: BLEScannerCoordinator,
        device_address: str, # Changed parameter name for clarity
        device_name: str,
        device_type: str,
        sensor_key: str,
        # polling_interval: int, # Removed, handled by coordinator
        entry_id: str, # Keep entry_id parameter
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_address = device_address # Store address
        # self._device_name = device_name # Name comes from device info
        self._device_type = device_type
        self._sensor_key = sensor_key
        # self._polling_interval = polling_interval # Removed

        # Generate unique ID: domain_deviceaddress_sensorkey
        # Ensure address characters are valid for entity ID
        safe_address = device_address.replace(":", "").lower()
        self._attr_unique_id = f"{DOMAIN}_{safe_address}_{self._sensor_key}"

        # Apply SensorEntityDescription if available
        if description := SENSOR_DESCRIPTIONS.get(self._sensor_key):
            self.entity_description = description
            # If description has translation_key, name is handled by HA
            # Otherwise, set name explicitly if needed (or rely on _attr_has_entity_name)
            # if not hasattr(description, "translation_key") and not self._attr_has_entity_name:
            #      self._attr_name = self._get_sensor_friendly_name(sensor_key) # Let has_entity_name handle it

        else:
            # Fallback for keys not in SENSOR_DESCRIPTIONS
            # Name is handled by _attr_has_entity_name = True
            # self._attr_name = self._get_sensor_friendly_name(sensor_key)
            self._attr_state_class = SensorStateClass.MEASUREMENT # Default assumption

        # Set device information
        manufacturer = "Unknown"
        if self._device_type == DEVICE_TYPE_PETKIT_FOUNTAIN:
            manufacturer = "Petkit"
        elif self._device_type == DEVICE_TYPE_S06_SOIL_TESTER:
            manufacturer = "Generic" # Or Efento? Based on format

        # Define device info using the DeviceInfo class
        # Use the device_address as the primary identifier
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_address)}, # Use address here
            name=device_name, # Use the name derived in async_setup_entry
            manufacturer=manufacturer,
            model=self._device_type,
            # Link to the config entry that created this device/entity
            # This allows grouping entities under the device in the UI
            config_entry_id=entry_id,
            # Optionally use via_device if there's a separate Bluetooth adapter entity
            # via_device=(...),
        )
        _LOGGER.debug(f"Initialized sensor: {self.unique_id} (Device: {self._device_address})")


    # def _get_sensor_friendly_name(self, key: str) -> str:
    #     """Generate a user-friendly name for the sensor key (fallback)."""
    #     # No longer needed if using translation keys or _attr_has_entity_name
    #     return key.replace("_", " ").capitalize()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Check coordinator status first
        if not self.coordinator.last_update_success:
             # _LOGGER.debug(f"Sensor {self.unique_id} unavailable: Coordinator update failed.")
             return False # Let coordinator handle logging failure reasons

        last_seen = self.coordinator.get_last_seen() # Coordinator is per-device, no need for address arg
        if last_seen is None:
            # If coordinator succeeded but device wasn't seen (shouldn't happen if coordinator succeeded)
            _LOGGER.debug(f"Sensor {self.unique_id} unavailable: Device {self._device_address} not seen in last successful update.")
            return False

        # Calculate unavailability timeout: base + factor * polling interval
        # Get interval from options first, then data, then default
        current_interval = self.coordinator.config_entry.options.get(
            CONF_POLLING_INTERVAL, self.coordinator.config_entry.data.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL)
        )
        timeout_seconds = UNAVAILABLE_TIMEOUT_BASE.total_seconds() + (UNAVAILABLE_TIMEOUT_FACTOR * current_interval)
        unavailability_threshold = dt_util.utcnow() - timedelta(seconds=timeout_seconds)

        # Ensure last_seen is timezone-aware for comparison
        if last_seen.tzinfo is None:
            last_seen = dt_util.as_utc(last_seen)

        is_available = last_seen >= unavailability_threshold
        # Reduce log spam, only log when becoming unavailable
        # if not is_available:
        #      _LOGGER.warning(f"Sensor {self.unique_id} unavailable: Last seen {last_seen} is older than threshold {unavailability_threshold} (Timeout: {timeout_seconds}s)")

        return is_available

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        # Data is now structured per-device in the coordinator
        if self.coordinator.data: # Check if coordinator data exists
            # The coordinator's data should directly contain the state for this device
            value = self.coordinator.data.get(self._sensor_key)
            # _LOGGER.debug(f"Sensor {self.unique_id} value: {value}") # Verbose logging
            return value
        # _LOGGER.debug(f"Sensor {self.unique_id}: No data available in coordinator.")
        return None # Return None if data is missing

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        attrs = {}
        if self.coordinator.data:
            device_data = self.coordinator.data # Data is specific to this device now
            if ATTR_LAST_UPDATED in device_data:
                attrs[ATTR_LAST_UPDATED] = device_data[ATTR_LAST_UPDATED]
            # Add RSSI as attribute to all sensors except the RSSI sensor itself
            if self._sensor_key != ATTR_RSSI and ATTR_RSSI in device_data:
                 attrs[ATTR_RSSI] = device_data[ATTR_RSSI]

            # Add model name/code if available and not the sensor itself (Petkit specific)
            if self._device_type == DEVICE_TYPE_PETKIT_FOUNTAIN:
                if self._sensor_key != KEY_PF_MODEL_NAME and KEY_PF_MODEL_NAME in device_data:
                    attrs["model_name"] = device_data[KEY_PF_MODEL_NAME] # Use snake_case for attr keys
                if self._sensor_key != KEY_PF_MODEL_CODE and KEY_PF_MODEL_CODE in device_data:
                    attrs["model_code"] = device_data[KEY_PF_MODEL_CODE]
                if self._sensor_key != KEY_PF_ALIAS and KEY_PF_ALIAS in device_data:
                    attrs["alias"] = device_data[KEY_PF_ALIAS]

        # Add config info for debugging/info
        # attrs["device_type"] = self._device_type # Already in device info
        # attrs["device_address"] = self._device_address # Already in device info identifiers
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Coordinator is per-device, so any update applies to this sensor
        # _LOGGER.debug(f"Updating state for sensor {self.unique_id} (Device: {self._device_address})")
        self.async_write_ha_state()
