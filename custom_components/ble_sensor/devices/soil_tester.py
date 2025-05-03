"""Implementation for S-06 Soil Tester device type."""
from __future__ import annotations

import asyncio
import logging
import struct
from typing import Any, Dict, List, Optional, Type, Union

from bleak import BleakClient
from bleak.exc import BleakError

from homeassistant.components.binary_sensor import BinarySensorEntityDescription, BinarySensorDeviceClass
from homeassistant.const import (
    UnitOfTemperature,
    PERCENTAGE,
    UnitOfPressure,
    EntityCategory
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass
)
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.switch import SwitchEntityDescription

from custom_components.ble_sensor.devices.device import BLEDevice, DeviceData
from custom_components.ble_sensor.utils.const import (
    KEY_S06_TEMP,
    KEY_S06_RH,
    KEY_S06_PRESSURE,
    KEY_S06_BATTERY,
)
from custom_components.ble_sensor.devices.base import DeviceType

_LOGGER = logging.getLogger(__name__)

# S-06 BLE characteristics
S06_SERVICE_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
S06_CHARACTERISTIC_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

# Constants for retry logic
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
READ_TIMEOUT = 10  # seconds

class SoilTester(DeviceType):
    """S-06 Soil Tester device type implementation."""

    def __init__(self) -> None:
        """Initialize the device type."""
        super().__init__()
        self._name = "soil_tester"
        self._description = "S-06 Soil Tester"
        self._last_read_time = 0
        self._read_lock = asyncio.Lock()
    
    def get_binary_sensor_descriptions(self) -> List[BinarySensorEntityDescription]:
        return []
    
    def get_switch_descriptions(self) -> List[SwitchEntityDescription]:
        """Return switch entity descriptions for this device type."""
        return []
    
    def get_select_descriptions(self) -> List[SelectEntityDescription]:
        """Return select entity descriptions for this device type."""
        return []

    def get_sensor_descriptions(self) -> List[SensorEntityDescription]:
        """Return entity descriptions for this device type."""
        return [
            SensorEntityDescription(
                key=KEY_S06_TEMP,
                name="Temperature",
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                entity_category=None,
            ),
            SensorEntityDescription(
                key=KEY_S06_RH,
                name="Humidity",
                device_class=SensorDeviceClass.HUMIDITY,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=PERCENTAGE,
                entity_category=None,
            ),
            SensorEntityDescription(
                key=KEY_S06_PRESSURE,
                name="Pressure",
                device_class=SensorDeviceClass.PRESSURE,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=UnitOfPressure.HPA,
                entity_category=None,
            ),
            SensorEntityDescription(
                key=KEY_S06_BATTERY,
                name="Battery",
                device_class=SensorDeviceClass.BATTERY,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=PERCENTAGE,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        ]

    def get_characteristics(self) -> List[str]:
        """Return characteristic UUIDs this device uses."""
        return [S06_CHARACTERISTIC_UUID]

    def get_services(self) -> List[str]:
        """Return service UUIDs this device uses."""
        return [S06_SERVICE_UUID]

    def requires_polling(self) -> bool:
        """Return True if this device requires polling."""
        return True

    def create_device(self, mac_address: str) -> BLEDevice:
        """Create a device instance for this device type."""
        device = super().create_device(mac_address)
        device.manufacturer = "S-06"
        device.model = "Soil Tester"
        return device
    
    async def parse_raw_data(self, uuid: str, data: bytearray|None) -> Dict[str, Any]|None:
        if not data:
            raise ValueError("No data received")
            
        _LOGGER.debug(f"Received data from S-06 characteristic: {data.hex()}")
        
        if len(data) < 23:
            raise ValueError(f"Data too short: {len(data)} bytes")
            
        result = {}
        # Parse the data
        try:
            # Temperature (°C) - Bytes 17:19 (Big Endian)
            temp_raw = int.from_bytes(data[17:19], byteorder='big')
            if temp_raw != 0xFFFF and temp_raw != 0x0000:
                result[KEY_S06_TEMP] = round(temp_raw / 100.0, 2)
            
            # Humidity (%) - Bytes 19:21 (Big Endian)
            rh_raw = int.from_bytes(data[19:21], byteorder='big')
            if rh_raw != 0xFFFF and rh_raw != 0x0000:
                result[KEY_S06_RH] = round(rh_raw / 100.0, 2)
            
            # Pressure (hPa) - Bytes 21:23 (Big Endian)
            pressure_raw = int.from_bytes(data[21:23], byteorder='big')
            if pressure_raw != 0xFFFF and pressure_raw != 0x0000:
                result[KEY_S06_PRESSURE] = round(pressure_raw / 100.0, 2)
            
            # Battery Level - Byte 3
            battery_raw = data[3]
            result[KEY_S06_BATTERY] = round((battery_raw / 255.0) * 100.0, 2)
                
            _LOGGER.debug(f"Successfully parsed S-06 data: {result}")
            return result
            
        except (struct.error, ValueError) as ex:
            _LOGGER.warning(f"Error parsing S-06 data: {ex}")

        return result
        