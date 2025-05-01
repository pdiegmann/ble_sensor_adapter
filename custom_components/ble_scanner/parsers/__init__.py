# custom_components/ble_scanner/parsers/__init__.py
"""Parsers for BLE advertisement data."""
import logging
from typing import Optional, Dict, Any

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

# Need to import const from the parent directory
from ..const import (
    LOGGER_NAME,
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_PETKIT_FOUNTAIN,
    KEY_PF_MODEL_CODE, KEY_PF_MODEL_NAME, KEY_PF_ALIAS, KEY_PF_BATTERY,
    KEY_PF_POWER_STATUS, KEY_PF_MODE, KEY_PF_DND_STATE, KEY_PF_WARN_BREAKDOWN,
    KEY_PF_WARN_WATER, KEY_PF_WARN_FILTER, KEY_PF_PUMP_RUNTIME,
    KEY_PF_FILTER_PERCENT, KEY_PF_RUNNING_STATUS,
    DEVICE_TYPE_S06_SOIL_TESTER,
    KEY_S06_TEMP, KEY_S06_RH, KEY_S06_PRESSURE, KEY_S06_BATTERY,
)
# Import ParsingError if defined
from ..errors import ParsingError

from .base import BaseParser
from .petkit_fountain import PETKIT_MANUFACTURER_ID, PetkitFountainParser
from .s_06_soil_tester import S06SoilTesterParser
from ..devices.s_06_soil_tester import S06_SERVICE_UUID # Use relative import

_LOGGER = logging.getLogger(LOGGER_NAME)

# --- Main Parser Dispatch ---
# Maps identifiers (like manufacturer IDs or service UUIDs) to parser *classes*

# Using manufacturer ID for Petkit, adjust if needed
PARSERS = {
    PETKIT_MANUFACTURER_ID: PetkitFountainParser,
    # Add S06 identifier and parser class when implemented
    S06_SERVICE_UUID: S06SoilTesterParser,
}

def get_parser(service_info: BluetoothServiceInfoBleak) -> Optional[type[BaseParser]]:
    """Check advertisement data and return the appropriate parser class."""
    # Check manufacturer data first
    for mfr_id, parser_cls in PARSERS.items():
        if isinstance(mfr_id, int) and mfr_id in service_info.manufacturer_data:
            _LOGGER.debug(f"Found matching manufacturer ID {mfr_id} for {service_info.address}, using parser: {parser_cls.__name__}")
            return parser_cls

    # Check service UUIDs next (if parsers are identified by UUID)
    # for service_uuid, parser_cls in PARSERS.items():
    #    if isinstance(service_uuid, str) and service_uuid in service_info.service_uuids:
    #        _LOGGER.debug(f"Found matching service UUID {service_uuid} for {service_info.address}, using parser: {parser_cls.__name__}")
    #        return parser_cls

    _LOGGER.debug(f"No suitable parser class found for device {service_info.address}")
    return None

