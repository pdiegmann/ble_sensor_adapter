"""Device class for BLE sensors."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TypeVar, Generic, Type, Protocol

from custom_components.ble_sensor.const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class DeviceData(Protocol):
    """Protocol for device data classes."""
    
    @property
    def data(self) -> Dict[str, Any]:
        """Return the parsed device data."""
        ...

T = TypeVar("T", bound=DeviceData)

class BLEDevice(Generic[T]):
    """Base class for BLE devices."""

    def __init__(
        self, 
        mac_address: str,
        device_type: str,
        data_class: Type[T],
        model: str = "Generic BLE Device",
        manufacturer: str = "Unknown",
    ) -> None:
        """Initialize the BLE device."""
        self.mac_address = mac_address
        self.device_type = device_type
        self.model = model
        self.manufacturer = manufacturer
        self.data_class = data_class
        self._data: Optional[T] = None
        self._available = False

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this device."""
        return f"{DOMAIN}_{self.device_type}_{self.mac_address}"

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return f"{self.model} ({self.mac_address})"

    @property
    def data(self) -> Optional[Dict[str, Any]]:
        """Return the device data."""
        if self._data:
            return self._data.data
        return None

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self._available

    @available.setter
    def available(self, available: bool) -> None:
        """Set device availability."""
        self._available = available

    def update_from_data(self, data: Dict[str, Any]) -> bool:
        """Update device from data dictionary."""
        try:
            self._data = self.data_class(data)
            return True
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error("Failed to parse data for %s: %s", self.mac_address, ex)
            return False

    def get_device_info(self) -> Dict[str, Any]:
        """Return device information for Home Assistant."""
        return {
            "identifiers": {(DOMAIN, self.mac_address)},
            "name": self.name,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "via_device": (DOMAIN, "bluetooth"),
        }