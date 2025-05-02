"""Base classes for device type handlers."""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, Union

from bleak import BleakClient
from bleak.exc import BleakError

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.switch import SwitchEntityDescription

from custom_components.ble_sensor.devices.device import BLEDevice, DeviceData

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
        self._connection_lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
        self._cleanup_tasks: List[asyncio.Task] = []
        self._is_initialized = False
        self._last_connection_time = 0
        self._connection_attempts = 0
        self._max_connection_attempts = 3
        
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

    def get_entity_descriptions(self) -> List[Union[SensorEntityDescription, BinarySensorEntityDescription, SwitchEntityDescription, SelectEntityDescription]]:
        """Return all entity descriptions for this device type."""
        return self.get_sensor_descriptions() + self.get_binary_sensor_descriptions() + self.get_switch_descriptions() + self.get_select_descriptions()

    @abstractmethod
    def get_sensor_descriptions(self) -> List[SensorEntityDescription]:
        pass

    @abstractmethod
    def get_binary_sensor_descriptions(self) -> List[BinarySensorEntityDescription]:
        pass

    @abstractmethod
    def get_switch_descriptions(self) -> List[SwitchEntityDescription]:
        """Return switch entity descriptions for this device type."""
        pass
    
    @abstractmethod
    def get_select_descriptions(self) -> List[SelectEntityDescription]:
        """Return select entity descriptions for this device type."""
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

    async def async_initialize(self, client: BleakClient) -> bool:
        """Initialize the device. Override in device-specific implementations."""
        self._is_initialized = True
        return True

    async def async_cleanup(self) -> None:
        """Clean up resources used by this device type."""
        self._stop_event.set()
        
        # Cancel any ongoing tasks
        for task in self._cleanup_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
        self._cleanup_tasks.clear()
        self._is_initialized = False
        self._connection_attempts = 0

    async def async_custom_fetch_data(self, client: BleakClient) -> Dict[str, Any]:
        """Fetch data from the device. Override in device-specific implementations."""
        return {}

    async def _ensure_initialized(self, client: BleakClient) -> bool:
        """Ensure the device is initialized."""
        if not self._is_initialized:
            try:
                async with self._connection_lock:
                    if not self._is_initialized:  # Check again under lock
                        if self._connection_attempts >= self._max_connection_attempts:
                            _LOGGER.error(
                                "Maximum connection attempts reached for device type %s",
                                self.name
                            )
                            return False
                            
                        self._connection_attempts += 1
                        return await self.async_initialize(client)
            except Exception as ex:
                _LOGGER.error(
                    "Error initializing device type %s: %s",
                    self.name,
                    ex,
                    exc_info=True
                )
                return False
        return True

    def _create_cleanup_task(self, coro) -> None:
        """Create a cleanup task that will be cancelled on cleanup."""
        task = asyncio.create_task(coro)
        self._cleanup_tasks.append(task)
        task.add_done_callback(self._cleanup_tasks.remove)
        