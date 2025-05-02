"""Base entity for BLE Sensor integration."""
from __future__ import annotations

from typing import Any, Dict, Optional, Union

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.binary_sensor import (
    BinarySensorEntityDescription
)
from homeassistant.components.sensor import (
    SensorEntityDescription
)

from custom_components.ble_sensor.utils.const import DOMAIN, SIGNAL_DEVICE_UPDATE
from custom_components.ble_sensor.coordinator import BLESensorDataUpdateCoordinator

class BLESensorEntity(CoordinatorEntity[BLESensorDataUpdateCoordinator], Entity):
    """Base entity for BLE Sensor."""

    def __init__(
        self, 
        coordinator: BLESensorDataUpdateCoordinator, 
        description: Union[SensorEntityDescription, BinarySensorEntityDescription],
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        
        self.entity_description = description
        self._key = description.key
        self._attr_unique_id = f"{coordinator.device.unique_id}_{description.key}"
        self._attr_name = description.name

        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.mac_address)},
            name=coordinator.device.name,
            manufacturer=coordinator.device.manufacturer,
            model=coordinator.device.model,
            # Remove via_device reference that was causing warnings
        )
        
        # Optional attributes
        if hasattr(description, "device_class"):
            self._attr_device_class = description.device_class
            
        if hasattr(description, "state_class"):
            self._attr_state_class = description.state_class
            
        if hasattr(description, "native_unit_of_measurement"):
            self._attr_native_unit_of_measurement = description.native_unit_of_measurement
            
        if hasattr(description, "entity_category"):
            self._attr_entity_category = description.entity_category
            
        if hasattr(description, "icon"):
            self._attr_icon = description.icon
            
        self._attr_has_entity_name = True
        self._attr_should_poll = False

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        
        # Register update callback for direct updates
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_DEVICE_UPDATE}_{self.coordinator.entry_id}",
                self._handle_update,
            )
        )

    @property
    def device_info(self) -> DeviceInfo:
        return self._attr_device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.device.available and super().available

    @property
    def native_value(self) -> Any:
        """Return the state of the entity."""
        if self.coordinator.data and self._key in self.coordinator.data:
            return self.coordinator.data[self._key]
        return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        return {}

    def _handle_update(self, data: Dict[str, Any]) -> None:
        """Handle device update."""
        if data and self._key in data:
            self.async_write_ha_state()