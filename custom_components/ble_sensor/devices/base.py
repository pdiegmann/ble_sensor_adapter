"""Base class for BLE devices."""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, Union, overload

from bleak import BleakClient
from bleak_retry_connector import establish_connection

from custom_components.ble_sensor.devices.device import BLEDevice
from custom_components.ble_sensor.utils.const import (CONF_ADDRESS, CONF_MAC,
                                                      CONF_TYPE, DOMAIN)
from homeassistant.components.binary_sensor import \
    BinarySensorEntityDescription
from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

class DeviceType(ABC):
    """Base class for device type handlers."""

    def __init__(self) -> None:
        """Initialize the device type handler."""
        self._name = "BLE Device"
        self._description = "BLE Device"
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

    def get_entity_descriptions(self) -> List[Union[SensorEntityDescription, BinarySensorEntityDescription, SwitchEntityDescription, SelectEntityDescription]]:
        """Return all entity descriptions for this device type."""
        return self.get_sensor_descriptions() + self.get_binary_sensor_descriptions() + self.get_switch_descriptions() + self.get_select_descriptions()

    def get_sensor_descriptions(self) -> List[SensorEntityDescription]:
        return []

    def get_binary_sensor_descriptions(self) -> List[BinarySensorEntityDescription]:
        return []

    def get_switch_descriptions(self) -> List[SwitchEntityDescription]:
        """Return switch entity descriptions for this device type."""
        return []

    def get_select_descriptions(self) -> List[SelectEntityDescription]:
        """Return select entity descriptions for this device type."""
        return []

    def create_device(self, mac_address: str) -> BLEDevice:
        """Create a device instance for this device type."""
        return BLEDevice(
            mac_address=mac_address,
            device_type=self.name,
            model=self.name,
            manufacturer="Petkit",  # Simplified since we only support Petkit devices
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

    def parse_raw_data(
        self,
        battery_payload: Optional[bytes],
        state_payload: Optional[bytes],
        config_payload: Optional[bytes],
    ) -> Dict[str, Any]:
        """Parse raw data from device payloads."""
        raise NotImplementedError

    async def _get_raw_data(self, ble_device, uuid: str) -> bytearray|None:
        """Get raw data from a characteristic."""
        client = None
        data = None
        try:
            async with asyncio.timeout(30):
                client = await establish_connection(
                    client_class=BleakClient,
                    device=ble_device,
                    name=ble_device.address,
                    timeout=10.0  # Use at least 10 second timeout
                )
                data = await client.read_gatt_char(uuid)
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout connecting to device %s", ble_device.address)
        except Exception as e:
            _LOGGER.error("Error connecting to %s: %s", ble_device.address, str(e))
        finally:
            if client is not None and client.is_connected:
                await client.disconnect()
            return data

    async def async_custom_fetch_data(self, ble_device) -> Dict[str, Any]:
        """Fetch data from the device."""
        raise NotImplementedError
