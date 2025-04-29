"""Parser for S-06 Soil Tester BLE data.

Based on the provided main.py example, this parser expects data in a format
similar to the Efento BLE logger standard, extracting temperature, relative humidity,
pressure, and battery level from specific byte positions in the advertisement data.
"""
import logging
from typing import Optional, Dict, Any

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from ..const import (
    LOGGER_NAME,
    KEY_S06_TEMP,
    KEY_S06_RH, # Renamed from MOISTURE based on analysis
    KEY_S06_PRESSURE, # Added based on analysis
    KEY_S06_BATTERY, # Added based on analysis
    # KEY_S06_CONDUCTIVITY, # Removed
    # KEY_S06_PH, # Removed
)

_LOGGER = logging.getLogger(LOGGER_NAME)

# --- Main Parser Function --- #

def parse_s06_soil_tester(device: BLEDevice, advertisement_data: AdvertisementData) -> Optional[Dict[str, Any]]:
    """Parses BLE advertisement data for S-06 Soil Tester devices.

    Expects data format similar to Efento BLE standard as seen in the example.

    Args:
        device: The BLEDevice object.
        advertisement_data: The AdvertisementData object.

    Returns:
        A dictionary containing parsed sensor data (temp, rh, pressure, battery),
        or None if the data doesn't match the expected format.
    """
    _LOGGER.debug(f"Attempting to parse S-06 Soil Tester data from {device.address}")

    # The example code checks manufacturer data or service data starting with 0x5A or 0xAA
    # and length >= 23. We need to check both manufacturer and service data fields.

    data_to_parse = None

    # Check Manufacturer Data first
    if advertisement_data.manufacturer_data:
        for mfr_id, mfr_data in advertisement_data.manufacturer_data.items():
            _LOGGER.debug(f"Checking S-06 Manufacturer data {mfr_id}: {mfr_data.hex()}")
            if len(mfr_data) >= 23 and (mfr_data[0] == 0x5A or mfr_data[0] == 0xAA):
                _LOGGER.debug(f"Found potential S-06 data in Manufacturer data {mfr_id}")
                data_to_parse = mfr_data
                break # Use the first match

    # If not found in manufacturer data, check Service Data
    if data_to_parse is None and advertisement_data.service_data:
        for uuid, svc_data in advertisement_data.service_data.items():
            _LOGGER.debug(f"Checking S-06 Service data {uuid}: {svc_data.hex()}")
            # Example used FF01/FF02, but pattern check is more robust
            if len(svc_data) >= 23 and (svc_data[0] == 0x5A or svc_data[0] == 0xAA):
                 _LOGGER.debug(f"Found potential S-06 data in Service data {uuid}")
                 data_to_parse = svc_data
                 break # Use the first match

    if data_to_parse is None:
        _LOGGER.debug(f"No matching S-06 data pattern found in advertisement from {device.address}")
        return None

    try:
        parsed_data = {}

        # Based on _decode_s06 in the example main.py
        # Measurement Slot 1: Temperature (°C) - Bytes 17:19 (Big Endian)
        temp_raw = int.from_bytes(data_to_parse[17:19], byteorder=\'big\')
        # Check for invalid values (often max/min int values)
        if temp_raw == 0xFFFF or temp_raw == 0x0000:
             _LOGGER.debug("Ignoring invalid temperature value (0xFFFF or 0x0000)")
             parsed_data[KEY_S06_TEMP] = None
        else:
            parsed_data[KEY_S06_TEMP] = round(temp_raw / 100.0, 2)

        # Measurement Slot 2: Humidity (%) - Bytes 19:21 (Big Endian)
        rh_raw = int.from_bytes(data_to_parse[19:21], byteorder=\'big\')
        if rh_raw == 0xFFFF or rh_raw == 0x0000:
            _LOGGER.debug("Ignoring invalid humidity value (0xFFFF or 0x0000)")
            parsed_data[KEY_S06_RH] = None
        else:
            parsed_data[KEY_S06_RH] = round(rh_raw / 100.0, 2)

        # Measurement Slot 3: Pressure (hPa) - Bytes 21:23 (Big Endian)
        pressure_raw = int.from_bytes(data_to_parse[21:23], byteorder=\'big\')
        if pressure_raw == 0xFFFF or pressure_raw == 0x0000:
            _LOGGER.debug("Ignoring invalid pressure value (0xFFFF or 0x0000)")
            parsed_data[KEY_S06_PRESSURE] = None
        else:
            parsed_data[KEY_S06_PRESSURE] = round(pressure_raw / 100.0, 2)

        # Battery Level - Byte 3
        battery_byte = data_to_parse[3]
        parsed_data[KEY_S06_BATTERY] = round((battery_byte / 255.0) * 100.0, 2)

        _LOGGER.debug(f"Successfully parsed S-06 Soil Tester data: {parsed_data}")
        return parsed_data

    except IndexError:
        _LOGGER.error(f"Error parsing S-06 Soil Tester data for {device.address}: Data length incorrect ({len(data_to_parse)} bytes, expected >= 23). Data: {data_to_parse.hex()}")
        return None # Indicate parsing failure
    except Exception as e:
        _LOGGER.error(f"Unexpected error parsing S-06 Soil Tester data for {device.address}: {e}", exc_info=True)
        return None # Indicate parsing failure

