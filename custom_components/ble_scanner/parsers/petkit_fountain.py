"""Parser for Petkit Fountain BLE data.

This parser attempts to identify Petkit devices based on advertised service data.
Full status updates typically require an active BLE connection and parsing notifications,
which is different from the passive scanning approach used by this component's coordinator.
This parser primarily extracts basic identification information available in advertisements.
"""
import logging
from typing import Optional, Dict, Any

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from ..const import (
    LOGGER_NAME,
    KEY_PF_WATER_LEVEL, # Keep existing placeholders
    KEY_PF_FILTER_LIFE,
    KEY_PF_WATER_TDS,
)

_LOGGER = logging.getLogger(LOGGER_NAME)

# --- Helper functions adapted from provided PetkitW5BLEMQTT/utils.py --- #

def bytes_to_unsigned_integers(byte_array):
    """Convert bytearray to list of unsigned integers."""
    return [b for b in byte_array]

def get_device_properties(device_integer_identifier: int) -> Optional[Dict[str, Any]]:
    """Return properties based on the integer identifier found in service data."""
    # Based on PetkitW5BLEMQTT/utils.py
    device_mapping = {
        205: {"name": "Petkit_W5C", "alias": "W5C", "product_name": "Eversweet Mini", "device_type": 14, "type_code": 2},
        206: {"name": "Petkit_W5", "alias": "W5", "product_name": "Eversweet Mini", "device_type": 14, "type_code": 1},
        213: {"name": "Petkit_W5N", "alias": "W5N", "product_name": "Eversweet Mini", "device_type": 14, "type_code": 3},
        214: {"name": "Petkit_W4X", "alias": "W4X", "product_name": "Eversweet 3 Pro", "device_type": 14, "type_code": 4},
        217: {"name": "Petkit_CTW2", "alias": "CTW2", "product_name": "Eversweet Solo 2", "device_type": 14, "type_code": 5},
        228: {"name": "Petkit_W4XUVC", "alias": "W4X", "product_name": "Eversweet 3 Pro (UVC)", "device_type": 14, "type_code": 6}
    }
    return device_mapping.get(device_integer_identifier)

# --- Main Parser Function --- #

def parse_petkit_fountain(device: BLEDevice, advertisement_data: AdvertisementData) -> Optional[Dict[str, Any]]:
    """Parses BLE advertisement data for Petkit Fountain devices.

    Focuses on identifying the device model from service data, as full status
    typically requires an active connection.

    Args:
        device: The BLEDevice object.
        advertisement_data: The AdvertisementData object.

    Returns:
        A dictionary containing parsed data (mainly identification), or None.
    """
    _LOGGER.debug(f"Attempting to parse Petkit Fountain data from {device.address}")
    _LOGGER.debug(f"Adv Data: Mfr={advertisement_data.manufacturer_data}, Svc={advertisement_data.service_data}")

    parsed_data = {}

    # Check Service Data - Iterate through service data UUIDs
    # The specific Petkit service UUID isn't explicitly listed in the provided constants,
    # but the logic in commands.py suggests parsing service data is key for identification.
    for uuid, data_bytes in advertisement_data.service_data.items():
        _LOGGER.debug(f"Checking service data UUID {uuid} with data {data_bytes.hex()}")
        # Check if data length is sufficient to contain the model code at index 5
        if len(data_bytes) >= 6:
            try:
                unsigned_bytes = bytes_to_unsigned_integers(data_bytes)
                model_code = unsigned_bytes[5]
                device_props = get_device_properties(model_code)

                # Check if the model code corresponds to a known Petkit device
                if device_props:
                    _LOGGER.info(f"Identified Petkit device model: {device_props.get('product_name', 'Unknown')} (Code: {model_code}) via service data UUID {uuid}")
                    parsed_data["model_code"] = model_code
                    parsed_data["model_name"] = device_props.get('product_name', 'Unknown')
                    parsed_data["alias"] = device_props.get('alias', 'Unknown')

                    # --- Placeholder for other data potentially in advertisement --- #
                    # Manufacturer data parsing could be added here if format is known
                    # Example: Check for battery level if Battery Service (0x180F) is present
                    battery_uuid = "0000180f-0000-1000-8000-00805f9b34fb"
                    if battery_uuid in advertisement_data.service_data:
                        battery_data = advertisement_data.service_data[battery_uuid]
                        if battery_data and len(battery_data) > 0:
                             parsed_data["battery"] = int(battery_data[0])
                             _LOGGER.debug(f"Found battery level: {parsed_data['battery']}%")

                    # --- Add notes about active connection needed for full data --- #
                    parsed_data["_notes"] = "Full status requires active connection; only basic identification and potentially battery level from advertisement."

                    # Initialize other expected keys to None, as they likely require active connection
                    # Based on PetkitW5BLEMQTT/parsers.py device_status and device_state
                    parsed_data["power_status"] = None
                    parsed_data["mode"] = None
                    parsed_data["dnd_state"] = None
                    parsed_data["warning_breakdown"] = None
                    parsed_data["warning_water_missing"] = None
                    parsed_data["warning_filter"] = None
                    parsed_data["pump_runtime"] = None
                    parsed_data[KEY_PF_FILTER_LIFE] = None # Placeholder key name
                    parsed_data["running_status"] = None
                    parsed_data[KEY_PF_WATER_LEVEL] = None # Placeholder key name - Not directly seen in provided parser code
                    parsed_data[KEY_PF_WATER_TDS] = None # Placeholder key name - Not directly seen in provided parser code

                    _LOGGER.debug(f"Parsed basic Petkit data: {parsed_data}")
                    # Return data from the first service UUID that successfully identifies a Petkit device
                    return parsed_data

            except IndexError:
                _LOGGER.debug(f"Service data for UUID {uuid} too short ({len(data_bytes)} bytes), skipping.")
            except Exception as e:
                _LOGGER.error(f"Error parsing service data for UUID {uuid}: {e}", exc_info=True)

    _LOGGER.debug(f"No relevant Petkit Fountain service data found in advertisement from {device.address}")
    return None

