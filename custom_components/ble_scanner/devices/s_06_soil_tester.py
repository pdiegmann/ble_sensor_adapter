"""Active connection handler for S-06 Soil Tester devices."""
# import asyncio # No longer needed
import logging
from datetime import datetime # Keep for last update time
from typing import Any, Dict # Keep Optional if needed, remove if not
# from bleak.backends.device import BLEDevice # No longer needed
from bleak import BleakClient
from bleak.exc import BleakError

from custom_components.ble_scanner.devices.base import BaseDeviceHandler
from custom_components.ble_scanner.const import (
    # LOGGER_NAME, # Logger passed in __init__
    KEY_S06_TEMP,
    KEY_S06_RH,
    KEY_S06_PRESSURE,
    KEY_S06_BATTERY,
)

# Constants from main.py example
S06_SERVICE_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
S06_CHARACTERISTIC_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

class S06SoilTesterHandler(BaseDeviceHandler):
    """Handles connection and data parsing for S-06 Soil Testers."""

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """Initialize the S-06 Soil Tester handler."""
        super().__init__(config, logger)
        self._latest_data: Dict[str, Any] = {} # Store latest parsed data
        # Remove _last_update_time and _is_available, coordinator handles availability

    def _parse_data(self, data: bytes) -> bool: # Return bool indicating success/failure
        """Parse data read from the characteristic (assuming Efento format)."""
        if not data or len(data) < 23:
            self.logger.warning(f"[{self.device_id}] S-06 data too short to parse: {len(data)} bytes. Data: {data.hex()}")
            return False # Indicate parsing failure

        try:
            parsed_data = {}

            # Based on _decode_s06 in the example main.py
            # Measurement Slot 1: Temperature (°C) - Bytes 17:19 (Big Endian)
            temp_raw = int.from_bytes(data[17:19], byteorder='big')
            if temp_raw == 0xFFFF or temp_raw == 0x0000:
                 self.logger.debug(f"[{self.device_id}] Ignoring invalid temperature value (0xFFFF or 0x0000)")
                 parsed_data[KEY_S06_TEMP] = None
            else:
                parsed_data[KEY_S06_TEMP] = round(temp_raw / 100.0, 2)

            # Measurement Slot 2: Humidity (%) - Bytes 19:21 (Big Endian)
            rh_raw = int.from_bytes(data[19:21], byteorder='big')
            if rh_raw == 0xFFFF or rh_raw == 0x0000:
                self.logger.debug(f"[{self.device_id}] Ignoring invalid humidity value (0xFFFF or 0x0000)")
                parsed_data[KEY_S06_RH] = None
            else:
                parsed_data[KEY_S06_RH] = round(rh_raw / 100.0, 2)

            # Measurement Slot 3: Pressure (hPa) - Bytes 21:23 (Big Endian)
            pressure_raw = int.from_bytes(data[21:23], byteorder='big')
            if pressure_raw == 0xFFFF or pressure_raw == 0x0000:
                self.logger.debug(f"[{self.device_id}] Ignoring invalid pressure value (0xFFFF or 0x0000)")
                parsed_data[KEY_S06_PRESSURE] = None
            else:
                parsed_data[KEY_S06_PRESSURE] = round(pressure_raw / 100.0, 2)

            # Battery Level - Byte 3
            battery_byte = data[3]
            parsed_data[KEY_S06_BATTERY] = round((battery_byte / 255.0) * 100.0, 2)

            # Update latest data
            self._latest_data.update(parsed_data)
            self.logger.debug(f"[{self.device_id}] Successfully parsed S-06 data: {parsed_data}")
            return True # Indicate success

        except IndexError:
            self.logger.error(f"[{self.device_id}] Error parsing S-06 data: Data length incorrect during parsing. Data: {data.hex()}")
            return False
        except Exception as e:
            self.logger.error(f"[{self.device_id}] Unexpected error parsing S-06 data: {e}", exc_info=True)
            return False

    async def async_fetch_data(self, client: BleakClient) -> Dict[str, Any]:
        """
        Fetch data from the connected S-06 Soil Tester.

        Reads the specific characteristic and parses the data.
        """
        self.logger.debug(f"[{self.device_id}] Starting async_fetch_data")

        try:
            self.logger.debug(f"[{self.device_id}] Reading characteristic {S06_CHARACTERISTIC_UUID}")
            data = await client.read_gatt_char(S06_CHARACTERISTIC_UUID)
            self.logger.debug(f"[{self.device_id}] Received data from S-06 characteristic: {data.hex()}")

            if self._parse_data(data):
                # No need to set last_update_time or is_available here
                self.logger.info(f"[{self.device_id}] Data fetch successful. Latest data: {self._latest_data}")
                return self._latest_data.copy() # Return a copy of the latest data
            else:
                # Parsing failed
                self.logger.error(f"[{self.device_id}] Failed to parse data from S-06 device.")
                # Raise an error that the coordinator can catch as UpdateFailed
                raise ValueError("Failed to parse S-06 data")

        except BleakError as e:
            self.logger.error(f"[{self.device_id}] BleakError during data fetch: {e}")
            # Let the coordinator handle the UpdateFailed exception.
            raise # Re-raise the exception
        except Exception as e:
            self.logger.error(f"[{self.device_id}] Unexpected error during data fetch: {e}", exc_info=True)
            raise # Re-raise the exception
        # No finally block needed, coordinator manages connection lifecycle
