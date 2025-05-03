"""Sensor platform for BLE Sensor Adapter."""
import logging
from typing import Any, Dict, Optional

from bleak.backends.device import BLEDevice

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.ble_sensor.utils import bluetooth
from custom_components.ble_sensor.utils.const import (
    DOMAIN,
    CONF_DEVICES,
    CONF_NAME,
    CONF_ADDRESS,
    CONF_TYPE,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
)
from .coordinator import BLESensorAdapterCoordinator
from .devices import get_device_instance

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BLE Sensor Adapter sensors."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    devices = data.get(CONF_DEVICES, [])
    
    # For discovery during config_flow
    if not devices:
        return
    
    entities = []
    
    for device_config in devices:
        name = device_config.get(CONF_NAME)
        address = device_config.get(CONF_ADDRESS)
        device_type = device_config.get(CONF_TYPE)
        polling_interval = device_config.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        
        if not address or not device_type:
            _LOGGER.error("Invalid device configuration: missing address or type")
            continue
        
        # Find the BLE device
        ble_device = await async_get_ble_device(hass, address)
        if not ble_device:
            _LOGGER.error("Could not find BLE device with address %s", address)
            # Don't fail - we'll try again next time
            continue
        
        # Create the device-specific instance
        device_instance = get_device_instance(device_type, address, name)
        if not device_instance:
            _LOGGER.error("Invalid device type: %s", device_type)
            continue
        
        # Create coordinator
        coordinator = BLESensorAdapterCoordinator(
            hass,
            _LOGGER,
            ble_device,
            device_instance,
            polling_interval,
        )
        
        # Request initial data
        await coordinator.async_refresh()
        
        # Create sensor entities for each supported sensor type
        for sensor_info in device_instance.get_supported_sensors():
            entities.append(
                BLESensorAdapterSensor(
                    coordinator,
                    device_instance,
                    sensor_info["key"],
                    sensor_info["name"],
                    sensor_info.get("device_class"),
                    sensor_info.get("state_class"),
                    sensor_info.get("unit_of_measurement"),
                    sensor_info.get("icon"),
                )
            )
    
    if entities:
        async_add_entities(entities)

async def async_get_ble_device(hass: HomeAssistant, address: str) -> Optional[BLEDevice]:
    """Get a BLE device by address."""
    # Try to find the device in already discovered devices
    ble_device = bluetooth.async_ble_device_from_address(hass, address, connectable=True)
    if ble_device:
        return ble_device
    
    # Look for it in all discovered service infos
    for service_info in bluetooth.async_discovered_service_info(hass):
        if service_info.address == address:
            return service_info.device
    
    # Try one more direct scan
    try:
        return await bluetooth.async_scanner_device_by_address(hass, address, connectable=True)
    except Exception as ex:
        _LOGGER.error("Error scanning for device %s: %s", address, str(ex))
        return None

class BLESensorAdapterSensor(CoordinatorEntity, SensorEntity):
    """BLE Sensor Adapter sensor entity."""

    def __init__(
        self,
        coordinator: BLESensorAdapterCoordinator,
        device: Any,
        key: str,
        name: str,
        device_class: Optional[str] = None,
        state_class: Optional[str] = None,
        unit_of_measurement: Optional[str] = None,
        icon: Optional[str] = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self._device = device
        self._key = key
        self._attr_name = f"{device.name} {name}"
        self._attr_unique_id = f"{DOMAIN}_{device.address}_{key}"
        
        if device_class is not None:
            self._attr_device_class = device_class
        
        if state_class is not None:
            self._attr_state_class = state_class
            
        if unit_of_measurement is not None:
            self._attr_native_unit_of_measurement = unit_of_measurement
            
        if icon is not None:
            self._attr_icon = icon
        
        # Device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.address)},
            name=device.name,
            manufacturer=device.get_manufacturer(),
            model=device.get_model(),
            via_device=(DOMAIN, device.address),
        )
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Use both the coordinator's availability and our own data check
        coordinator_available = super().available
        has_data = (
            self.coordinator.data is not None and 
            self._key in self.coordinator.data
        )
        return coordinator_available and has_data
    
    @property
    def native_value(self) -> Any:
        """Return the value reported by the sensor."""
        return self.coordinator.data.get(self._key) if self.coordinator.data else None
    
    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {}
        
        attributes = {}
        
        # Add RSSI
        if "rssi" in self.coordinator.data:
            attributes["rssi"] = self.coordinator.data["rssi"]
        
        # Add last update time
        if "last_update" in self.coordinator.data:
            attributes["last_update"] = self.coordinator.data["last_update"]
        
        # Add connection status
        attributes["connected"] = self.coordinator.is_connected
        
        return attributes
    
    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        
        # Update state immediately when added to hass
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.coordinator.is_device_available(self._device_id)
        )