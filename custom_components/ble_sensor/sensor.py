"""Sensor platform for BLE Sensor integration."""
import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.ble_sensor.utils.const import DOMAIN, DEFAULT_DEVICE_TYPE
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
    
    entities = []
    
    # Create sensor entities for each configured device
    # Simplified: we know all devices are Petkit Fountain type
    device_handler = get_device_type()  # Gets default Petkit Fountain
    sensor_descriptions = device_handler.get_sensor_descriptions()
    
    for device_config in coordinator.device_configs:
        for description in sensor_descriptions:
            entity = BLESensorEntity(
                coordinator=coordinator,
                description=description,
                device_id=device_config.device_id,
                device_name=device_config.name,
                device_address=device_config.address,
            )
            entities.append(entity)
    
    if entities:
        _LOGGER.debug("Adding %d sensor entities", len(entities))
        async_add_entities(entities)

class BLESensorEntity(BaseDeviceEntity, SensorEntity):
    """BLE sensor entity."""

    def __init__(
        self,
        coordinator: BLESensorCoordinator,
        description: SensorEntityDescription,
        device_id: str,
        device_name: str,
        device_address: str,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, device_id, device_name, device_address)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{description.key}"
        self._attr_name = f"{device_name} {description.name}"

    @property
    def native_value(self) -> Any:
        """Return the native value of the sensor."""
        if not self.available:
            return None
            
        device_data = self.coordinator.get_device_data(self._device_id)
        if device_data is None:
            return None
            
        return device_data.get(self.entity_description.key)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success and 
            self.coordinator.is_device_available(self._device_id)
        )

