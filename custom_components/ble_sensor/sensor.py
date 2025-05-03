"""Sensor platform for BLE Sensor Adapter."""
import logging
from typing import Any, Dict
from custom_components.ble_sensor.devices.base import DeviceType
from custom_components.ble_sensor.devices.device import async_get_ble_device
from custom_components.ble_sensor.entity import BaseDeviceEntity
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.ble_sensor.utils.const import (
    CONF_DEVICE_TYPE,
    CONF_MAC,
    DOMAIN,
    CONF_DEVICES,
    CONF_NAME,
    CONF_ADDRESS,
    CONF_TYPE,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
)
from custom_components.ble_sensor.coordinator import BLESensorCoordinator
from custom_components.ble_sensor.devices import get_device_type

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: BLESensorCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Get device type
    device_type = get_device_type(entry.data[CONF_DEVICE_TYPE])
    ble_device = await async_get_ble_device(entry.data[CONF_MAC])
    
    # Create entities
    _LOGGER.debug("Setting up sensor entities for device type: %s", device_type.__class__.__name__)
    entities = []
    descriptions = device_type.get_sensor_descriptions()
    _LOGGER.debug("Found %d sensor descriptions: %s", len(descriptions), descriptions)
    for description in descriptions:
        entity = BLESensorEntity(coordinator, description, ble_device)
        entities.append(entity)
            
    if entities:
        _LOGGER.debug("Adding %d sensor entities", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.debug("No sensor entities to add for this device type.")

async def ___async_setup_entry(
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
        coordinator = BLESensorCoordinator(
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
                BLESensorEntity(coordinator, sensor_info, device_instance)
            )
    
    if entities:
        async_add_entities(entities)

class BLESensorEntity(BaseDeviceEntity, SensorEntity):
    """BLE Sensor Adapter sensor entity."""
    
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
    