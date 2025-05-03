"""Sensor platform for BLE Sensor Adapter."""
import logging
from typing import Any, Dict, Optional

from bleak.backends.device import BLEDevice

from custom_components.ble_sensor.devices.base import DeviceType
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
from custom_components.ble_sensor.coordinator import BLESensorDataUpdateCoordinator
from custom_components.ble_sensor.devices import get_device_type

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
        device_instance = get_device_type(device_type, address, name)
        if not device_instance:
            _LOGGER.error("Invalid device type: %s", device_type)
            continue
        
        # Create coordinator
        coordinator = BLESensorDataUpdateCoordinator(
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
                BLESensorAdapterSensor(coordinator, sensor_info, device_instance)
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

class BLESensorAdapterSensor(DeviceType, SensorEntity):
    """BLE Sensor Adapter sensor entity."""

    def __init__(
        self,
        coordinator: BLESensorDataUpdateCoordinator,
        description: SensorEntityDescription,
        device: DeviceType
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description, device)
    
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
    