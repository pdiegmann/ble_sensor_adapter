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
from custom_components.ble_sensor.devices.device_types.base import BaseDeviceData, DeviceType

_LOGGER = logging.getLogger(__name__)

# S-06 BLE characteristics
S06_SERVICE_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
S06_CHARACTERISTIC_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

# Constants for retry logic
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
READ_TIMEOUT = 10  # seconds

class SoilTesterData(BaseDeviceData):
    """S-06 Soil Tester data parser."""

    def parse_data(self) -> None:
        """Parse the raw data into usable data."""
        super().parse_data()
        
        # Ensure numeric values are properly rounded and within valid ranges
        if KEY_S06_TEMP in self._parsed_data and self._parsed_data[KEY_S06_TEMP] is not None:
            self._parsed_data[KEY_S06_TEMP] = round(float(self._parsed_data[KEY_S06_TEMP]), 2)
            # Validate temperature range (-40°C to 85°C typical for this sensor)
            if not -40 <= self._parsed_data[KEY_S06_TEMP] <= 85:
                self._parsed_data[KEY_S06_TEMP] = None
        
        if KEY_S06_RH in self._parsed_data and self._parsed_data[KEY_S06_RH] is not None:
            self._parsed_data[KEY_S06_RH] = round(float(self._parsed_data[KEY_S06_RH]), 2)
            # Validate humidity range (0-100%)
            if not 0 <= self._parsed_data[KEY_S06_RH] <= 100:
                self._parsed_data[KEY_S06_RH] = None
        
        if KEY_S06_PRESSURE in self._parsed_data and self._parsed_data[KEY_S06_PRESSURE] is not None:
            self._parsed_data[KEY_S06_PRESSURE] = round(float(self._parsed_data[KEY_S06_PRESSURE]), 2)
            # Validate pressure range (300-1100 hPa typical)
            if not 300 <= self._parsed_data[KEY_S06_PRESSURE] <= 1100:
                self._parsed_data[KEY_S06_PRESSURE] = None
                
        if KEY_S06_BATTERY in self._parsed_data and self._parsed_data[KEY_S06_BATTERY] is not None:
            self._parsed_data[KEY_S06_BATTERY] = round(float(self._parsed_data[KEY_S06_BATTERY]), 2)
            # Ensure battery percentage is between 0-100
            self._parsed_data[KEY_S06_BATTERY] = max(0, min(100, self._parsed_data[KEY_S06_BATTERY]))


class SoilTester(DeviceType):
    """S-06 Soil Tester device type implementation."""

    def __init__(self) -> None:
        """Initialize the device type."""
        super().__init__()
        self._name = "soil_tester"
        self._description = "S-06 Soil Tester"
        self._last_read_time = 0
        self._read_lock = asyncio.Lock()

    def get_device_data_class(self) -> Type[DeviceData]:
        """Return the data class for this device type."""
        return SoilTesterData
    
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

    async def async_custom_fetch_data(self, client: BleakClient) -> Dict[str, Any]:
        """Fetch data from the S-06 Soil Tester device with retry logic."""
        _LOGGER.debug("Starting S-06 Soil Tester data fetch")
        result = {}
        
        if not client or not client.is_connected:
            _LOGGER.error("Client not connected")
            raise BleakError("Client not connected")

        async with self._read_lock:  # Ensure only one read operation at a time
            for attempt in range(MAX_RETRIES):
                try:
                    # Read the characteristic
                    _LOGGER.debug(f"Reading characteristic {S06_CHARACTERISTIC_UUID} (attempt {attempt + 1}/{MAX_RETRIES})")
                    data = await asyncio.wait_for(
                        client.read_gatt_char(S06_CHARACTERISTIC_UUID),
                        timeout=READ_TIMEOUT
                    )
                    
                    if not data:
                        raise ValueError("No data received")
                        
                    _LOGGER.debug(f"Received data from S-06 characteristic: {data.hex()}")
                    
                    if len(data) < 23:
                        raise ValueError(f"Data too short: {len(data)} bytes")
                        
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
                        
                        # Validate the parsed values
                        if not self._validate_sensor_data(result):
                            raise ValueError("Invalid sensor values detected")
                            
                        _LOGGER.debug(f"Successfully parsed S-06 data: {result}")
                        return result
                        
                    except (struct.error, ValueError) as ex:
                        _LOGGER.warning(f"Error parsing S-06 data: {ex}")
                        if attempt == MAX_RETRIES - 1:
                            raise
                            
                except asyncio.TimeoutError:
                    _LOGGER.warning(
                        f"Timeout reading S-06 characteristic (attempt {attempt + 1}/{MAX_RETRIES})"
                    )
                    if attempt == MAX_RETRIES - 1:
                        raise
                except BleakError as ex:
                    _LOGGER.error(f"BLE error reading S-06 characteristic: {ex}")
                    raise
                except Exception as ex:
                    _LOGGER.error(f"Unexpected error reading S-06 characteristic: {ex}")
                    raise
                    
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY)
                    
        return result

    def _validate_sensor_data(self, data: Dict[str, Any]) -> bool:
        """Validate sensor data is within expected ranges."""
        if KEY_S06_TEMP in data:
            if not -40 <= data[KEY_S06_TEMP] <= 85:
                _LOGGER.warning(f"Invalid temperature value: {data[KEY_S06_TEMP]}°C")
                return False
                
        if KEY_S06_RH in data:
            if not 0 <= data[KEY_S06_RH] <= 100:
                _LOGGER.warning(f"Invalid humidity value: {data[KEY_S06_RH]}%")
                return False
                
        if KEY_S06_PRESSURE in data:
            if not 300 <= data[KEY_S06_PRESSURE] <= 1100:
                _LOGGER.warning(f"Invalid pressure value: {data[KEY_S06_PRESSURE]} hPa")
                return False
                
        if KEY_S06_BATTERY in data:
            if not 0 <= data[KEY_S06_BATTERY] <= 100:
                _LOGGER.warning(f"Invalid battery value: {data[KEY_S06_BATTERY]}%")
                return False
                
        return True
        