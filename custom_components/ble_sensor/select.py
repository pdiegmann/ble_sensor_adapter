"""Select platform for BLE Sensor integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from custom_components.ble_sensor.coordinator import BLESensorCoordinator
from custom_components.ble_sensor.devices import get_device_type
from custom_components.ble_sensor.entity import BaseDeviceEntity
from custom_components.ble_sensor.utils.const import DOMAIN
from homeassistant.components.select import (SelectEntity,
                                             SelectEntityDescription)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform."""
    coordinator: BLESensorCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []

    # Create select entities for each configured device
    # Simplified: we know all devices are Petkit Fountain type
    device_handler = get_device_type()  # Gets default Petkit Fountain
    select_descriptions = device_handler.get_select_descriptions()

    for device_config in coordinator.device_configs:
        for description in select_descriptions:
            entity = BLESelectEntity(
                coordinator=coordinator,
                description=description,
                device_id=device_config.device_id,
                device_name=device_config.name,
                device_address=device_config.address,
            )
            entities.append(entity)

    if entities:
        _LOGGER.debug("Adding %d select entities", len(entities))
        async_add_entities(entities)

class BLESelectEntity(BaseDeviceEntity, SelectEntity):
    """BLE select entity."""

    def __init__(
        self,
        coordinator: BLESensorCoordinator,
        description: SelectEntityDescription,
        device_id: str,
        device_name: str,
        device_address: str,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator, device_id, device_name, device_address)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{description.key}"
        self._attr_name = f"{device_name} {description.name}"
        self._attr_options = description.options

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        if not self.available:
            return None

        device_data = self.coordinator.get_device_data(self._device_id)
        if device_data is None:
            return None

        value = device_data.get(self.entity_description.key)
        if value is None:
            return None

        # Ensure the value is in the options list
        if str(value) in self.options:
            return str(value)

        return None

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        # This would need to be implemented based on the specific device
        # For now, just log that the action was attempted
        _LOGGER.warning("Select option not implemented for %s", self.entity_id)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success and
            self.coordinator.is_device_available(self._device_id)
        )
