"""Base entity for BLE Sensor integration."""
from __future__ import annotations

from typing import Any, Dict, Optional

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.ble_sensor.utils.const import DOMAIN
from custom_components.ble_sensor.coordinator import BLESensorCoordinator

class BaseDeviceEntity(CoordinatorEntity[BLESensorCoordinator]):
    """Base entity for BLE Sensor."""

    def __init__(
        self, 
        coordinator: BLESensorCoordinator, 
        device_id: str,
        device_name: str,
        device_address: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._device_name = device_name
        self._device_address = device_address

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_name,
            manufacturer="BLE Device",
            model="BLE Sensor",
            via_device=(DOMAIN, "bluetooth"),
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success and 
            self.coordinator.is_device_available(self._device_id)
        )