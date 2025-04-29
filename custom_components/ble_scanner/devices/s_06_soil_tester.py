"""Active connection handler for S-06 Soil Tester devices."""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from .base import BaseDeviceHandler
from ..const import (
    LOGGER_NAME,
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

    def _parse_data(self, data: bytes):
        """Parse data read from the characteristic (assuming Efento format)."""
        if not data or len(data) < 23:
            self.logger.warning(f"S-06 data too short to parse: {len(data)} bytes. Data: {data.hex()}")
            return False # Indicate parsing failure

        try:
            parsed_data = {}

            # Based on _decode_s06 in the example main.py
            # Measurement Slot 1: Temperature (°C) - Bytes 17:19 (Big Endian)
            temp_raw = int.from_bytes(data[17:19], byteorder='big')
            if temp_raw == 0xFFFF or temp_raw == 0x0000:
                 self.logger.debug("Ignoring invalid temperature value (0xFFFF or 0x0000)")
                 parsed_data[KEY_S06_TEMP] = None
            else:
                parsed_data[KEY_S06_TEMP] = round(temp_raw / 100.0, 2)

            # Measurement Slot 2: Humidity (%) - Bytes 19:21 (Big Endian)
            rh_raw = int.from_bytes(data[19:21], byteorder='big')
            if rh_raw == 0xFFFF or rh_raw == 0x0000:
                self.logger.debug("Ignoring invalid humidity value (0xFFFF or 0x0000)")
                parsed_data[KEY_S06_RH] = None
            else:
                parsed_data[KEY_S06_RH] = round(rh_raw / 100.0, 2)

            # Measurement Slot 3: Pressure (hPa) - Bytes 21:23 (Big Endian)
            pressure_raw = int.from_bytes(data[21:23], byteorder='big')
            if pressure_raw == 0xFFFF or pressure_raw == 0x0000:
                self.logger.debug("Ignoring invalid pressure value (0xFFFF or 0x0000)")
                parsed_data[KEY_S06_PRESSURE] = None
            else:
                parsed_data[KEY_S06_PRESSURE] = round(pressure_raw / 100.0, 2)

            # Battery Level - Byte 3
            battery_byte = data[3]
            parsed_data[KEY_S06_BATTERY] = round((battery_byte / 255.0) * 100.0, 2)

            # Update latest data
            self._latest_data.update(parsed_data)
            self.logger.debug(f"Successfully parsed S-06 data: {parsed_data}")
            return True # Indicate success

        except IndexError:
            self.logger.error(f"Error parsing S-06 data for {self.device_id}: Data length incorrect during parsing. Data: {data.hex()}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error parsing S-06 data for {self.device_id}: {e}", exc_info=True)
            return False

    async def update(self, ble_device: BLEDevice) -> None:
        """Connect to the device, read characteristic, and parse data."""
        async with self._update_lock:
            if not await self._ensure_connected(ble_device):
                self.mark_unavailable()
                return

            try:
                self.logger.debug(f"Reading characteristic {S06_CHARACTERISTIC_UUID} for {self.device_id}")
                data = await self._client.read_gatt_char(S06_CHARACTERISTIC_UUID)
                self.logger.debug(f"Received data from S-06 characteristic: {data.hex()}")

                if self._parse_data(data):
                    self._last_update_time = datetime.now()
                    self._is_available = True
                    self.logger.info(f"Update successful for {self.device_id}. Latest data: {self._latest_data}")
                else:
                    # Parsing failed, mark unavailable?
                    self.mark_unavailable()
                    self.logger.error(f"Failed to parse data from S-06 device {self.device_id}")
                    # Raise error to coordinator?
                    raise ValueError("Failed to parse S-06 data")

            except BleakError as e:
                self.logger.error(f"BleakError during update for {self.device_id}: {e}")
                self.mark_unavailable()
                await self.disconnect()
                raise
            except Exception as e:
                self.logger.error(f"Unexpected error during update for {self.device_id}: {e}", exc_info=True)
                self.mark_unavailable()
                await self.disconnect()
                raise
            finally:
                # Disconnect after update cycle (for polling coordinator)
                await self.disconnect()

