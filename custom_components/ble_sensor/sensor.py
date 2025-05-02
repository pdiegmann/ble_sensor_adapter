"""Sensor platform for BLE Sensor integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.components.binary_sensor import (
    BinarySensorEntityDescription
)
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription
)

from custom_components.ble_sensor.const import CONF_DEVICE_TYPE, DOMAIN
from custom_components.ble_sensor.coordinator import BLESensorDataUpdateCoordinator
from custom_components.ble_sensor.device_types import get_device_type
from custom_components.ble_sensor.entity import BLESensorEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: BLESensorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Get device type
    device_type = get_device_type(entry.data[CONF_DEVICE_TYPE])
    
    # Create entities
    entities = []
    for description in device_type.get_sensor_descriptions():
        entities.append(BLESensorSensorEntity(coordinator, description))
            
    if entities:
        async_add_entities(entities)

class BLESensorSensorEntity(BLESensorEntity, SensorEntity):
    """Sensor entity for BLE Sensor integration."""

    def __init__(
        self, 
        coordinator: BLESensorDataUpdateCoordinator, 
        description: Union[SensorEntityDescription, BinarySensorEntityDescription],
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device.unique_id}_{description.key}"
        self._attr_name = description.name
        
        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.mac_address)},
            name=coordinator.device.name,
            manufacturer=coordinator.device.manufacturer,
            model=coordinator.device.model,
            # Remove via_device reference
        )
        
        self._attr_has_entity_name = True
        self._attr_should_poll = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.mac_address)},
            name=self.coordinator.device.name,
            manufacturer=self.coordinator.device.manufacturer,
            model=self.coordinator.device.model,
            # Remove this line or use a valid device identifier:
            # via_device=(DOMAIN, "bluetooth"),
        )