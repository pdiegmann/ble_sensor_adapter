"""Binary sensor platform for BLE Sensor integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.binary_sensor import BinarySensorEntityDescription

from custom_components.ble_sensor.utils.const import CONF_DEVICE_TYPE, DOMAIN
from custom_components.ble_sensor.coordinator import BLESensorDataUpdateCoordinator
from custom_components.ble_sensor.devices.device_types import get_device_type
from custom_components.ble_sensor.entity import BLESensorEntity


_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator: BLESensorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    # Get device type
    device_type = get_device_type(entry.data[CONF_DEVICE_TYPE])
    
    # Create entities
    entities = []
    for description in device_type.get_binary_sensor_descriptions():
        entity = BLESensorBinarySensorEntity(coordinator, description)
        entities.append(entity)
            
    if entities:
        async_add_entities(entities)

class BLESensorBinarySensorEntity(BLESensorEntity, BinarySensorEntity):
    """Binary sensor entity for BLE Sensor integration."""

    def __init__(
        self, 
        coordinator: BLESensorDataUpdateCoordinator, 
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor entity."""
        super().__init__(coordinator, description)
        
    @property
    def is_on(self) -> Optional[bool]:
        """Return true if the binary sensor is on."""
        if self.coordinator.data and self._key in self.coordinator.data:
            return bool(self.coordinator.data[self._key])
        return None