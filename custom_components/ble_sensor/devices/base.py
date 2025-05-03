"""Base class for BLE devices."""
from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Any, Dict, List, Optional, Type, Union, overload
from bleak_retry_connector import establish_connection

from custom_components.ble_sensor.utils.const import CONF_ADDRESS, CONF_MAC, CONF_TYPE, DOMAIN
from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
)

from bleak import BleakClient

from custom_components.ble_sensor.devices.device import BLEDevice, DeviceData
from custom_components.ble_sensor.utils import bluetooth

_LOGGER = logging.getLogger(__name__)

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

    async def async_custom_fetch_data(self, client: BleakClient) -> Dict[str, Any]:
        """Fetch data from the device. Override in device-specific implementations."""
        return {}


    @overload
    async def connect_and_get_data(self, address, hass: Optional[HomeAssistant] = None) -> Dict[str, Dict[str, Any]]|None:
        ...
    
    @overload
    async def connect_and_get_data(self, ble_device, hass: Optional[HomeAssistant] = None) -> Dict[str, Dict[str, Any]]|None:
        ...
    
    async def connect_and_get_data(self, ble_device = None, address = None, hass: Optional[HomeAssistant] = None) -> Dict[str, Dict[str, Any]]|None:
        if ble_device is None:
            if address is None:
                raise ValueError("Need either device or address!")
            ble_device = bluetooth.async_ble_device_from_address(hass or self.hass, address, connectable=True)
        data = {}
        services = self.get_services()
        if services and len(services) > 0:
            for uuid in self.get_services():
                data[uuid] = self._get_data(ble_device, uuid)
        else:
            return self._get_data(ble_device)
        return data

    @abstractmethod
    async def parse_raw_data(self, uuid: str, raw_data: bytearray|None) -> Dict[str, Any]|None:
        pass

    async def _get_data(self, ble_device, uuid: Optional[str] = None) -> Dict[str, Any]|None:
        raw_data = self._get_raw_data(ble_device, uuid)
        try:
            data = self.parse_raw_data(uuid, raw_data)
            return data
        except Exception as e:
            _LOGGER.error("Error parsing data %s: %s", raw_data, str(e))
            return None

    async def _get_raw_data(self, ble_device, uuid: str) -> bytearray|None:
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
        