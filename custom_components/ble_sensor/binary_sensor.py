"""Binary sensor platform for BLE Sensor integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from custom_components.ble_sensor.devices.base import DeviceType
from custom_components.ble_sensor.devices.device import async_get_ble_device
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.binary_sensor import BinarySensorEntityDescription

from custom_components.ble_sensor.utils.const import CONF_DEVICE_TYPE, CONF_MAC, DOMAIN
from custom_components.ble_sensor.coordinator import BLESensorCoordinator
from custom_components.ble_sensor.devices import get_device_type
from custom_components.ble_sensor.entity import BaseDeviceEntity


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
    ble_device = await async_get_ble_device(hass, entry.data[CONF_MAC])
    
    # Create entities
    _LOGGER.debug("Setting up binary sensor entities for device type: %s", device_type.__class__.__name__)
    entities = []
    descriptions = device_type.get_binary_sensor_descriptions()
    _LOGGER.debug("Found %d binary sensor descriptions: %s", len(descriptions), descriptions)
    for description in descriptions:
        entity = BLEBinarySensorEntity(coordinator, description, ble_device)
        entities.append(entity)
            
    if entities:
        _LOGGER.debug("Adding %d binary sensor entities", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.debug("No binary sensor entities to add for this device type.")

class BLEBinarySensorEntity(BaseDeviceEntity, BinarySensorEntity):
    """Binary sensor entity for BLE Sensor integration."""

    def __init__(
        self, 
        coordinator: BLESensorCoordinator, 
        description: BinarySensorEntityDescription,
        device: DeviceType
    ) -> None:
        """Initialize the binary sensor entity."""
        super().__init__(coordinator, description, device)
        
    @property
    def is_on(self) -> Optional[bool]:
        """Return true if the binary sensor is on."""
        return self.as_bool(self.native_value)
    