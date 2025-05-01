"""Parser for S-06 Soil Tester BLE data.

Based on the provided main.py example, this parser expects data in a format
similar to the Efento BLE logger standard, extracting temperature, relative humidity,
pressure, and battery level from specific byte positions in the advertisement data.
"""
import logging
from typing import Optional, Dict, Any

# Imports needed for the original function (kept for reference, but not directly used by the class)
# from bleak.backends.device import BLEDevice
# from bleak.backends.scanner import AdvertisementData

# Imports needed for the Parser class
from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak

from custom_components.ble_scanner.const import (
    LOGGER_NAME,
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_S06_SOIL_TESTER,
    KEY_S06_TEMP,
    KEY_S06_RH, # Renamed from MOISTURE based on analysis
    KEY_S06_PRESSURE, # Added based on analysis
    KEY_S06_BATTERY, # Added based on analysis
    # KEY_S06_CONDUCTIVITY, # Removed
    # KEY_S06_PH, # Removed
)
from custom_components.ble_scanner.errors import ParsingError
from custom_components.ble_scanner.parsers.base import BaseParser


_LOGGER = logging.getLogger(LOGGER_NAME)

# --- S06 Soil Tester Parser Class ---

class S06SoilTesterParser(BaseParser):
    """Parser for S06 Soil Tester advertisement data based on Efento-like structure."""

    def parse(self, service_info: BluetoothServiceInfoBleak) -> Optional[Dict[str, Any]]:
        """Parse S06 Soil Tester advertisement data.

        Args:
            service_info: The BluetoothServiceInfoBleak object containing advertisement data.

        Returns:
            A dictionary containing parsed sensor data and device type,
            or None if the data doesn't match the expected format or parsing fails.

        Raises:
            ParsingError: If an unexpected error occurs during parsing.
        """
        _LOGGER.debug(f"Attempting to parse S-06 Soil Tester data for {service_info.address}")

        data_to_parse = None

        # Check Manufacturer Data first
        if service_info.manufacturer_data:
            for mfr_id, mfr_data in service_info.manufacturer_data.items():
                _LOGGER.debug(f"Checking S-06 Manufacturer data {mfr_id}: {mfr_data.hex()}")
                if len(mfr_data) >= 23 and (mfr_data[0] == 0x5A or mfr_data[0] == 0xAA):
                    _LOGGER.debug(f"Found potential S-06 data in Manufacturer data {mfr_id}")
                    data_to_parse = mfr_data
                    break # Use the first match

        # If not found in manufacturer data, check Service Data
        if data_to_parse is None and service_info.service_data:
            for uuid, svc_data in service_info.service_data.items():
                _LOGGER.debug(f"Checking S-06 Service data {uuid}: {svc_data.hex()}")
                # Example used FF01/FF02, but pattern check is more robust
                if len(svc_data) >= 23 and (svc_data[0] == 0x5A or svc_data[0] == 0xAA):
                     _LOGGER.debug(f"Found potential S-06 data in Service data {uuid}")
                     data_to_parse = svc_data
                     break # Use the first match

        if data_to_parse is None:
            _LOGGER.debug(f"No matching S-06 data pattern found in advertisement from {service_info.address}")
            return None

        try:
            parsed_data = {CONF_DEVICE_TYPE: DEVICE_TYPE_S06_SOIL_TESTER}

            # Measurement Slot 1: Temperature (°C) - Bytes 17:19 (Big Endian)
            temp_raw = int.from_bytes(data_to_parse[17:19], byteorder='big')
            if temp_raw != 0xFFFF and temp_raw != 0x0000: # Check for invalid values
                parsed_data[KEY_S06_TEMP] = round(temp_raw / 100.0, 2)
            else:
                _LOGGER.debug("Ignoring invalid temperature value (0xFFFF or 0x0000)")
                # Optionally set to None or omit if None is preferred
                # parsed_data[KEY_S06_TEMP] = None

            # Measurement Slot 2: Humidity (%) - Bytes 19:21 (Big Endian)
            rh_raw = int.from_bytes(data_to_parse[19:21], byteorder='big')
            if rh_raw != 0xFFFF and rh_raw != 0x0000: # Check for invalid values
                parsed_data[KEY_S06_RH] = round(rh_raw / 100.0, 2)
            else:
                _LOGGER.debug("Ignoring invalid humidity value (0xFFFF or 0x0000)")
                # parsed_data[KEY_S06_RH] = None

            # Measurement Slot 3: Pressure (hPa) - Bytes 21:23 (Big Endian)
            pressure_raw = int.from_bytes(data_to_parse[21:23], byteorder='big')
            if pressure_raw != 0xFFFF and pressure_raw != 0x0000: # Check for invalid values
                parsed_data[KEY_S06_PRESSURE] = round(pressure_raw / 100.0, 2)
            else:
                _LOGGER.debug("Ignoring invalid pressure value (0xFFFF or 0x0000)")
                # parsed_data[KEY_S06_PRESSURE] = None

            # Battery Level - Byte 3
            battery_byte = data_to_parse[3]
            parsed_data[KEY_S06_BATTERY] = round((battery_byte / 255.0) * 100.0, 2)

            # Only return data if at least one sensor value was successfully parsed
            if len(parsed_data) > 1: # More than just the device type
                _LOGGER.debug(f"Successfully parsed S-06 Soil Tester data: {parsed_data}")
                return parsed_data
            else:
                _LOGGER.debug(f"No valid sensor values found in S-06 data for {service_info.address}")
                return None

        except IndexError:
            _LOGGER.warning(f"Error parsing S-06 Soil Tester data for {service_info.address}: Data length incorrect ({len(data_to_parse)} bytes, expected >= 23). Data: {data_to_parse.hex()}")
            return None # Indicate parsing failure, but not an unexpected error
        except Exception as e:
            _LOGGER.error(f"Unexpected error parsing S-06 Soil Tester data for {service_info.address}: {e}", exc_info=True)
            # Raise ParsingError to signal a more critical failure
            raise ParsingError(f"Unexpected error parsing S06 data: {e}") from e