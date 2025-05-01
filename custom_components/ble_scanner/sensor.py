# custom_components/ble_scanner/sensor.py
"""Sensor platform for BLE Scanner integration."""
import logging
from datetime import datetime, timedelta # Keep timedelta if needed elsewhere, dt_util handles timezone
from typing import Any, Dict, Optional, Set, Tuple # Added Set, Tuple

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ( # Import necessary constants
    CONF_ADDRESS, # Keep address constant
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfPressure,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType # Added for device info
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util # Keep dt_util


from .const import (
    DOMAIN,
    # CONF_DEVICES, # No longer needed here
    # CONF_DEVICE_ADDRESS, # Not directly used in setup, derived from coordinator
    # CONF_DEVICE_NAME, # Not directly used in setup, derived from coordinator
    CONF_DEVICE_TYPE, # Used to identify device type from parsed data
    # CONF_POLLING_INTERVAL, # Not used by sensor directly
    # DEFAULT_POLLING_INTERVAL, # Not used by sensor directly
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
from .coordinator import BLEScannerCoordinator, CoordinatorData # Import CoordinatorData type hint

_LOGGER = logging.getLogger(LOGGER_NAME)

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
    """Set up sensor entities dynamically from coordinator data."""
    coordinator: BLEScannerCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Set to store ('address', 'sensor_key') tuples of added entities
    added_entities: set[tuple[str, str]] = set()

    @callback
    def _async_update_sensors() -> None:
        """Check coordinator data and add entities."""
        new_entities = []
        if not coordinator.data:
            _LOGGER.debug("Coordinator has no data, skipping sensor update.")
            return

        # Iterate through devices found by the coordinator
        for address, device_data in coordinator.data.items():
            # Determine device type (assuming parser adds this key)
            # TODO: Adjust key if parser uses a different one (e.g., 'model', 'type')
            # Need a reliable way to get the device type from the parsed data.
            # Let's assume the parser adds CONF_DEVICE_TYPE for now.
            device_type = device_data.get(CONF_DEVICE_TYPE)
            if not device_type:
                # Try common model keys as fallback for type identification
                # This depends heavily on parser implementation consistency
                device_type = device_data.get(KEY_PF_MODEL_NAME) # Example fallback for Petkit
                if not device_type:
                     _LOGGER.warning(f"Device type not found in data for {address}, cannot create sensors. Data: {device_data}")
                     continue # Skip this device if type cannot be determined

            # Determine device name (e.g., from model name or fallback)
            # TODO: Adjust key if parser uses a different one
            device_name = device_data.get(KEY_PF_MODEL_NAME) or device_data.get(KEY_PF_ALIAS) or f"{device_type} {address}"

            # Get expected sensor keys for this device type
            expected_keys = DEVICE_EXPECTED_SENSORS.get(device_type, [])
            # Always include RSSI
            all_keys_for_device = set(expected_keys) | {ATTR_RSSI}

            # Create sensors for this device if not already added
            for sensor_key in all_keys_for_device:
                # Only create sensor if the key is actually present in the device_data
                if sensor_key in device_data:
                    entity_tuple = (address, sensor_key)
                    if entity_tuple not in added_entities:
                        _LOGGER.info(f"Adding sensor '{sensor_key}' for device {address} (Type: {device_type})")
                        new_entities.append(
                            BLEDeviceSensor(
                                coordinator,
                                address,
                                device_name,
                                device_type, # Pass the determined type
                                sensor_key,
                                entry.entry_id,
                            )
                        )
                        added_entities.add(entity_tuple)
                # else: # Optional: Log if an expected key is missing
                #     if sensor_key in expected_keys: # Only log if it was explicitly expected
                #         _LOGGER.debug(f"Expected sensor key '{sensor_key}' not found in data for {address}")


        if new_entities:
            async_add_entities(new_entities)

        # Note: No explicit removal logic here. Sensors for devices that disappear
        # from coordinator.data will become unavailable due to the `available` property.

    # Add listener and trigger initial update
    entry.async_on_unload(coordinator.async_add_listener(_async_update_sensors))
    _async_update_sensors() # Run once on setup


class BLEDeviceSensor(CoordinatorEntity[BLEScannerCoordinator], SensorEntity):
    """Representation of a Sensor for a BLE device attribute."""

    _attr_has_entity_name = True # Use device name + sensor key as entity name
    # Prevent device from being added to HA device registry before we have device info
    _attr_device_info = None

    def __init__(
        self,
        coordinator: BLEScannerCoordinator,
        device_address: str,
        device_name: str, # Name determined dynamically
        device_type: str, # Type determined dynamically
        sensor_key: str,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_address = device_address.lower() # Ensure lowercase address
        self._device_type = device_type # Store type determined during setup
        self._sensor_key = sensor_key
        self._entry_id = entry_id # Store entry_id for device info

        # Generate unique ID: domain_deviceaddress_sensorkey
        safe_address = self._device_address.replace(":", "")
        self._attr_unique_id = f"{DOMAIN}_{safe_address}_{self._sensor_key}"

        # Apply SensorEntityDescription if available
        if description := SENSOR_DESCRIPTIONS.get(self._sensor_key):
            self.entity_description = description
        else:
            # Fallback for keys not in SENSOR_DESCRIPTIONS
            self._attr_state_class = SensorStateClass.MEASUREMENT # Default assumption

        # Device info is set dynamically in _handle_coordinator_update
        self._set_device_info(device_name) # Try setting initial device info

        _LOGGER.debug(f"Initialized sensor: {self.unique_id} (Device: {self._device_address})")

    def _set_device_info(self, device_name: str) -> None:
        """Set device information based on current coordinator data."""
        # Try to get more specific info from coordinator data
        manufacturer = "Unknown"
        model = self._device_type # Fallback model to type
        sw_version = None # Placeholder

        # Example: Extract more details if available in parsed data
        # Adjust keys based on what parsers actually provide
        device_data = self.coordinator.data.get(self._device_address, {}) if self.coordinator.data else {}
        if self._device_type == DEVICE_TYPE_PETKIT_FOUNTAIN:
            manufacturer = "Petkit"
            model = device_data.get(KEY_PF_MODEL_NAME, self._device_type) # Use model name if present
        elif self._device_type == DEVICE_TYPE_S06_SOIL_TESTER:
            manufacturer = "Generic" # Or Efento?
            # model = device_data.get("model_identifier", self._device_type) # Example

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_address)}, # Use address as unique identifier for the device
            name=device_name, # Use dynamically determined name
            manufacturer=manufacturer,
            model=model,
            sw_version=sw_version,
            entry_type=DeviceEntryType.SERVICE, # Indicate it's provided by an integration service
            #config_entry_id=self._entry_id, # Link to the integration's config entry
        )


    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Available if the coordinator is successful AND this device's address is in the data
        # Coordinator's last_update_success check is handled by CoordinatorEntity base class
        return (
            super().available and # Check coordinator availability
            self.coordinator.data is not None and
            self._device_address in self.coordinator.data
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        # Data is now structured per-device in the coordinator
        if self.coordinator.data and self._device_address in self.coordinator.data:
            value = self.coordinator.data[self._device_address].get(self._sensor_key)
            # _LOGGER.debug(f"Sensor {self.unique_id} value: {value}") # Verbose
            return value
        # _LOGGER.debug(f"Sensor {self.unique_id}: No data available for device {self._device_address}.")
        return None # Return None if device data or sensor key is missing

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        attrs = {}
        # Ensure data exists for the device before accessing attributes
        if self.coordinator.data and self._device_address in self.coordinator.data:
            device_data = self.coordinator.data[self._device_address]

            # Add last updated time from the device's data block
            if ATTR_LAST_UPDATED in device_data:
                attrs[ATTR_LAST_UPDATED] = device_data[ATTR_LAST_UPDATED]

            # Add RSSI if this isn't the RSSI sensor itself
            if self._sensor_key != ATTR_RSSI and ATTR_RSSI in device_data:
                 attrs[ATTR_RSSI] = device_data[ATTR_RSSI]

            # Add other relevant attributes from device_data if needed
            # Example for Petkit: Use self._device_type determined during init
            if self._device_type == DEVICE_TYPE_PETKIT_FOUNTAIN:
                 if self._sensor_key != KEY_PF_MODEL_NAME and KEY_PF_MODEL_NAME in device_data:
                     attrs["model_name"] = device_data[KEY_PF_MODEL_NAME]
                 if self._sensor_key != KEY_PF_MODEL_CODE and KEY_PF_MODEL_CODE in device_data:
                     attrs["model_code"] = device_data[KEY_PF_MODEL_CODE]
                 if self._sensor_key != KEY_PF_ALIAS and KEY_PF_ALIAS in device_data:
                     attrs["alias"] = device_data[KEY_PF_ALIAS]
                 # Add others as needed...

        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Update device info if it hasn't been set yet or if relevant data changed
        # This ensures manufacturer/model are updated if they appear later
        if self._attr_device_info is None or \
           (self._device_type == DEVICE_TYPE_PETKIT_FOUNTAIN and self._attr_device_info.get("model") == self._device_type):
             # Attempt to update device info if missing or using fallback model
             device_data = self.coordinator.data.get(self._device_address, {}) if self.coordinator.data else {}
             device_name = device_data.get(KEY_PF_MODEL_NAME) or device_data.get(KEY_PF_ALIAS) or f"{self._device_type} {self._device_address}"
             self._set_device_info(device_name)


        # Only write state if this sensor's device address is present in the data
        if self.coordinator.data and self._device_address in self.coordinator.data:
            # _LOGGER.debug(f"Updating state for sensor {self.unique_id} (Device: {self._device_address})")
            self.async_write_ha_state()
        # else: # Optional: Log if device disappeared? Might be noisy.
            # _LOGGER.debug(f"Skipping state write for sensor {self.unique_id}, device {self._device_address} not in coordinator data.")

