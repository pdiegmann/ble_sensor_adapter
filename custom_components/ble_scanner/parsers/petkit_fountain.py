# --- Petkit Fountain Parser ---
import logging
from typing import Optional, Dict, Any

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS
from custom_components.ble_scanner.const import (
    LOGGER_NAME,
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_PETKIT_FOUNTAIN,
    KEY_PF_MODEL_CODE, KEY_PF_MODEL_NAME, KEY_PF_ALIAS, KEY_PF_BATTERY,
    KEY_PF_POWER_STATUS, KEY_PF_MODE, KEY_PF_DND_STATE, KEY_PF_WARN_BREAKDOWN,
    KEY_PF_WARN_WATER, KEY_PF_WARN_FILTER, KEY_PF_PUMP_RUNTIME,
    KEY_PF_FILTER_PERCENT, KEY_PF_RUNNING_STATUS,
    DOMAIN
)
from ..errors import ParsingError  # Use relative import
from .base import BaseParser  # Use relative import

_LOGGER = logging.getLogger(LOGGER_NAME)

# Constants (keep specific to this parser if possible)
PETKIT_MANUFACTURER_ID = 0x0483 # Example Manufacturer ID, verify correct one

class PetkitFountainParser(BaseParser):
    """Parser for Petkit Fountain advertisement data."""

    def parse(self, service_info: BluetoothServiceInfoBleak) -> Optional[Dict[str, Any]]:
        """Parse Petkit Fountain advertisement data."""
        _LOGGER.debug(f"Attempting to parse Petkit Fountain data for {service_info.address}")

        # Check if manufacturer data matches
        if PETKIT_MANUFACTURER_ID not in service_info.manufacturer_data:
            _LOGGER.debug(f"Manufacturer ID {PETKIT_MANUFACTURER_ID} not found for {service_info.address}")
            return None

        manufacturer_bytes = service_info.manufacturer_data[PETKIT_MANUFACTURER_ID]
        # Increased minimum length check based on observed data structure needs
        if not manufacturer_bytes or len(manufacturer_bytes) < 20:
            _LOGGER.debug(f"Manufacturer data too short for Petkit Fountain: {manufacturer_bytes.hex() if manufacturer_bytes else 'None'}")
            return None

        _LOGGER.debug(f"Raw Petkit manufacturer data ({service_info.address}): {manufacturer_bytes.hex()}")

        try:
            # --- Parsing Logic ---
            # Indices verified/adjusted based on common Petkit formats
            model_code = int.from_bytes(manufacturer_bytes[2:4], byteorder='little')
            alias_bytes = manufacturer_bytes[4:10]
            try:
                # Attempt decoding, remove null terminators, strip whitespace
                alias = alias_bytes.split(b'\x00', 1)[0].decode('utf-8').strip()
            except (UnicodeDecodeError, IndexError):
                alias = alias_bytes.hex() # Fallback
                _LOGGER.warning(f"Could not decode alias for {service_info.address}, using hex: {alias}")

            battery = manufacturer_bytes[10]
            power_status_raw = manufacturer_bytes[11]
            mode_raw = manufacturer_bytes[12]
            dnd_state_raw = manufacturer_bytes[13]
            warn_breakdown_raw = manufacturer_bytes[14]
            warn_water_raw = manufacturer_bytes[15]
            warn_filter_raw = manufacturer_bytes[16]
            # Pump runtime seems to be 2 bytes, little-endian
            pump_runtime = int.from_bytes(manufacturer_bytes[17:19], byteorder='little')
            filter_percent = manufacturer_bytes[19]

            # --- Data Interpretation ---
            power_status = "Plugged In" if power_status_raw == 1 else "Battery"
            mode = "Smart" if mode_raw == 1 else "Normal" # Check if other modes exist
            dnd_state = "Enabled" if dnd_state_raw == 1 else "Disabled"
            warn_breakdown = "Warning" if warn_breakdown_raw == 1 else "OK"
            warn_water = "Warning" if warn_water_raw == 1 else "OK"
            warn_filter = "Warning" if warn_filter_raw == 1 else "OK"
            # Determine running status based on warnings (adjust logic if needed)
            running_status = "Running" if warn_breakdown_raw == 0 and warn_water_raw == 0 else "Stopped/Warning"

            # Determine model name based on code
            model_name_map = {
                10: "Petkit Eversweet 3 Pro",
                # Add other known model codes and names here
            }
            model_name = model_name_map.get(model_code, f"Petkit Fountain {model_code}")

            # --- Assemble Result Dictionary ---
            data = {
                CONF_DEVICE_TYPE: DEVICE_TYPE_PETKIT_FOUNTAIN, # Crucial
                KEY_PF_MODEL_CODE: model_code,
                KEY_PF_MODEL_NAME: model_name,
                KEY_PF_ALIAS: alias,
                KEY_PF_BATTERY: battery,
                KEY_PF_POWER_STATUS: power_status,
                KEY_PF_MODE: mode,
                KEY_PF_DND_STATE: dnd_state,
                KEY_PF_WARN_BREAKDOWN: warn_breakdown,
                KEY_PF_WARN_WATER: warn_water,
                KEY_PF_WARN_FILTER: warn_filter,
                KEY_PF_PUMP_RUNTIME: pump_runtime,
                KEY_PF_FILTER_PERCENT: filter_percent,
                KEY_PF_RUNNING_STATUS: running_status,
            }
            _LOGGER.debug(f"Parsed Petkit Fountain data for {service_info.address}: {data}")
            return data

        except IndexError as e:
             _LOGGER.error(f"Index error parsing Petkit Fountain data for {service_info.address} (Data: {manufacturer_bytes.hex()}): {e}", exc_info=True)
             raise ParsingError(f"Invalid data length for Petkit Fountain: {e}") from e
        except Exception as e:
            _LOGGER.error(f"Error parsing Petkit Fountain data for {service_info.address}: {e}", exc_info=True)
            # Raise specific ParsingError to be caught by coordinator
            raise ParsingError(f"Unexpected error parsing Petkit Fountain data: {e}") from e