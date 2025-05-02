"""Sensor platform for BLE Sensor integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
    for description in device_type.get_entity_descriptions():
        if description.get("entity_type") == "sensor":
            entities.append(BLESensorSensorEntity(coordinator, description))
            
    if entities:
        async_add_entities(entities)

class BLESensorSensorEntity(BLESensorEntity, SensorEntity):
    """Sensor entity for BLE Sensor integration."""

    def __init__(
        self, 
        coordinator: BLESensorDataUpdateCoordinator, 
        description: Dict[str, Any],
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, description)