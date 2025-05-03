"""Base entity for BLE Sensor integration."""
from __future__ import annotations

from typing import Any, Dict, Optional, Union

from custom_components.ble_sensor.devices.base import DeviceType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.binary_sensor import (
    BinarySensorEntityDescription
)
from homeassistant.components.sensor import (
    SensorEntityDescription
)
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.components.select import SelectEntityDescription

from custom_components.ble_sensor.utils.const import DOMAIN, SIGNAL_DEVICE_UPDATE
from custom_components.ble_sensor.coordinator import BLESensorCoordinator

class BaseDeviceEntity(CoordinatorEntity[BLESensorCoordinator], Entity):
    """Base entity for BLE Sensor."""

    def __init__(
        self, 
        coordinator: BLESensorCoordinator, 
        description: Union[SensorEntityDescription, BinarySensorEntityDescription, SwitchEntityDescription, SelectEntityDescription],
        device: Dict[str, Any],
        *args,
        **kwargs
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, *args, **kwargs)
        address = device.get("address") or device.get("mac") or device.get("mac_address")
        device_id = device.get("id", address)
        self.device = device
        self.entity_description = description
        self._key = description.key
        self._device_id = address
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_name = description.name

        # Set device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.mac_address)},
            name=device.get("name"),
            manufacturer=device.get("manufacturer"),
            model=device.get("model"),
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

        if hasattr(description, "options"):
            self._attr_options = description.options
            
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
    def native_value(self) -> Any:
        """Return the state of the entity."""
        return self._attr_native_value

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        return {}

    def _handle_update(self, data: Dict[str, Any]) -> None:
        """Handle device update."""
        if data and self._key in data:
            self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.coordinator.is_device_available(self._device_id)
            and self._attr_native_value
        )
        
    @property
    def attr_available(self) -> bool:
        return self.available
    
    @property
    def _attr_native_value(self):
        return self.coordinator._device_data.get(self._device_id)
    
    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()
        
        # Update state immediately when added to hass
        self.async_write_ha_state()
    
    def as_bool(self, val):
        if isinstance(val, bool):
            return val
        elif isinstance(val, str):
            return val.lower() in ("on", "true", "1")
        return bool(val)