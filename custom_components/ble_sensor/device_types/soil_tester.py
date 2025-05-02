"""Implementation for S-06 Soil Tester device type."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Type

from bleak import BleakClient
from bleak.exc import BleakError

from custom_components.ble_sensor.device import BLEDevice, DeviceData
from custom_components.ble_sensor.const import (
    KEY_S06_TEMP,
    KEY_S06_RH,
    KEY_S06_PRESSURE,
    KEY_S06_BATTERY,
)
from custom_components.ble_sensor.device_types.base import BaseDeviceData, DeviceType

_LOGGER = logging.getLogger(__name__)

# S-06 BLE characteristics
S06_SERVICE_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
S06_CHARACTERISTIC_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

class SoilTesterData(BaseDeviceData):
    """S-06 Soil Tester data parser."""

    def parse_data(self) -> None:
        """Parse the raw data into usable data."""
        super().parse_data()
        
        # Additional processing can be added here if needed
        # Right now, most of the processing happens during the fetch operation
        
        # Convert temperature to Celsius if stored in a different unit
        if KEY_S06_TEMP in self._parsed_data and self._parsed_data[KEY_S06_TEMP] is not None:
            # Assuming temperature is already in the correct unit, just round for consistency
            self._parsed_data[KEY_S06_TEMP] = round(float(self._parsed_data[KEY_S06_TEMP]), 2)
        
        # Round humidity to 2 decimal places for consistency
        if KEY_S06_RH in self._parsed_data and self._parsed_data[KEY_S06_RH] is not None:
            self._parsed_data[KEY_S06_RH] = round(float(self._parsed_data[KEY_S06_RH]), 2)
        
        # Round pressure to 2 decimal places for consistency
        if KEY_S06_PRESSURE in self._parsed_data and self._parsed_data[KEY_S06_PRESSURE] is not None:
            self._parsed_data[KEY_S06_PRESSURE] = round(float(self._parsed_data[KEY_S06_PRESSURE]), 2)


class SoilTester(DeviceType):
    """S-06 Soil Tester device type implementation."""

    def __init__(self) -> None:
        """Initialize the device type."""
        super().__init__()
        self._name = "soil_tester"
        self._description = "S-06 Soil Tester"

    def get_device_data_class(self) -> Type[DeviceData]:
        """Return the data class for this device type."""
        return SoilTesterData

    def get_entity_descriptions(self) -> List[Dict[str, Any]]:
        """Return entity descriptions for this device type."""
        return [
            {
                "key": KEY_S06_TEMP,
                "name": "Temperature",
                "device_class": "temperature",
                "state_class": "measurement",
                "native_unit_of_measurement": "°C",
                "entity_category": None,
                "entity_type": "sensor",
            },
            {
                "key": KEY_S06_RH,
                "name": "Humidity",
                "device_class": "humidity",
                "state_class": "measurement",
                "native_unit_of_measurement": "%",
                "entity_category": None,
                "entity_type": "sensor",
            },
            {
                "key": KEY_S06_PRESSURE,
                "name": "Pressure",
                "device_class": "pressure",
                "state_class": "measurement",
                "native_unit_of_measurement": "hPa",
                "entity_category": None,
                "entity_type": "sensor",
            },
            {
                "key": KEY_S06_BATTERY,
                "name": "Battery",
                "device_class": "battery",
                "state_class": "measurement",
                "native_unit_of_measurement": "%",
                "entity_category": "diagnostic",
                "entity_type": "sensor",
            },
        ]

    def get_characteristics(self) -> List[str]:
        """Return characteristic UUIDs this device uses."""
        return [
            S06_CHARACTERISTIC_UUID,
        ]

    def get_services(self) -> List[str]:
        """Return service UUIDs this device uses."""
        return [
            S06_SERVICE_UUID,
        ]

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
        """Fetch data from the S-06 Soil Tester device.
        
        This is a more direct implementation than the Petkit fountain, as the S-06
        just requires reading from a characteristic without the complex initialization
        and notification handling.
        """
        _LOGGER.debug("Starting S-06 Soil Tester data fetch")
        result = {}
        
        try:
            # Read the characteristic
            _LOGGER.debug(f"Reading characteristic {S06_CHARACTERISTIC_UUID}")
            data = await client.read_gatt_char(S06_CHARACTERISTIC_UUID)
            _LOGGER.debug(f"Received data from S-06 characteristic: {data.hex()}")
            
            # Parse the data
            if not data or len(data) < 23:
                _LOGGER.warning(f"S-06 data too short to parse: {len(data)} bytes. Data: {data.hex()}")
                raise ValueError("Data too short to parse")
                
            # Measurement Slot 1: Temperature (°C) - Bytes 17:19 (Big Endian)
            temp_raw = int.from_bytes(data[17:19], byteorder='big')
            if temp_raw != 0xFFFF and temp_raw != 0x0000:  # Check for invalid values
                result[KEY_S06_TEMP] = round(temp_raw / 100.0, 2)
            
            # Measurement Slot 2: Humidity (%) - Bytes 19:21 (Big Endian)
            rh_raw = int.from_bytes(data[19:21], byteorder='big')
            if rh_raw != 0xFFFF and rh_raw != 0x0000:  # Check for invalid values
                result[KEY_S06_RH] = round(rh_raw / 100.0, 2)
            
            # Measurement Slot 3: Pressure (hPa) - Bytes 21:23 (Big Endian)
            pressure_raw = int.from_bytes(data[21:23], byteorder='big')
            if pressure_raw != 0xFFFF and pressure_raw != 0x0000:  # Check for invalid values
                result[KEY_S06_PRESSURE] = round(pressure_raw / 100.0, 2)
            
            # Battery Level - Byte 3
            battery_byte = data[3]
            result[KEY_S06_BATTERY] = round((battery_byte / 255.0) * 100.0, 2)
            
            _LOGGER.debug(f"Successfully parsed S-06 data: {result}")
            return result
            
        except BleakError as e:
            _LOGGER.error(f"BleakError during S-06 data fetch: {e}")
            raise
        except Exception as e:
            _LOGGER.error(f"Unexpected error during S-06 data fetch: {e}", exc_info=True)
            raise