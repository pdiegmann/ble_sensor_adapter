"""Base classes for device type handlers."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from custom_components.ble_sensor.device import BLEDevice, DeviceData

_LOGGER = logging.getLogger(__name__)

class BaseDeviceData:
    """Base class for device data."""

    def __init__(self, raw_data: Dict[str, Any]) -> None:
        """Initialize the device data."""
        self.raw_data = raw_data
        self._parsed_data: Dict[str, Any] = {}
        self.parse_data()

    @property
    def data(self) -> Dict[str, Any]:
        """Return the parsed data."""
        return self._parsed_data

    def parse_data(self) -> None:
        """Parse raw data into usable values."""
        # Base implementation just copies raw data
        # Specific device types should override this
        self._parsed_data = self.raw_data.copy()

class DeviceType(ABC):
    """Base class for device type handlers."""

    def __init__(self) -> None:
        """Initialize the device type handler."""
        self._name = "Unknown Device Type"
        self._description = "Unknown Device Type"
        
    @property
    def name(self) -> str:
        """Return the name of this device type."""
        return self._name
        
    @property
    def description(self) -> str:
        """Return the description of this device type."""
        return self._description

    @abstractmethod
    def get_device_data_class(self) -> Type[DeviceData]:
        """Return the device data class for this device type."""
        pass

    @abstractmethod
    def get_entity_descriptions(self) -> List[Dict[str, Any]]:
        """Return entity descriptions for this device type."""
        pass
        
    def create_device(self, mac_address: str) -> BLEDevice:
        """Create a device instance for this device type."""
        return BLEDevice(
            mac_address=mac_address,
            device_type=self.name,
            data_class=self.get_device_data_class(),
            model=self.name,
            manufacturer="Custom BLE Device",
        )

    def get_characteristics(self) -> List[str]:
        """Return a list of characteristics UUIDs this device uses."""
        return []
        
    def get_services(self) -> List[str]:
        """Return a list of service UUIDs this device uses."""
        return []
        
    def requires_polling(self) -> bool:
        """Return True if this device requires polling."""
        return False