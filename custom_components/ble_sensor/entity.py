"""Base entity for BLE Sensor integration."""
from __future__ import annotations

from typing import Any, Dict, Optional

from custom_components.ble_sensor.coordinator import BLESensorCoordinator
from custom_components.ble_sensor.utils.const import DOMAIN
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity


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
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Focus on device-specific availability rather than global coordinator success
        return self.coordinator.is_device_available(self._device_id)
