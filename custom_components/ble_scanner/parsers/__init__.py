"""Parser registry for BLE device data."""
import logging
from typing import Callable, Optional, Dict, Any

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from ..const import (
    DEVICE_TYPE_PETKIT_FOUNTAIN,
    DEVICE_TYPE_S06_SOIL_TESTER,
    LOGGER_NAME
)
from .petkit_fountain import parse_petkit_fountain
from .s_06_soil_tester import parse_s06_soil_tester

_LOGGER = logging.getLogger(LOGGER_NAME)

# Type alias for parser functions
ParserFunc = Callable[[BLEDevice, AdvertisementData], Optional[Dict[str, Any]]]

# Map device types to their parser functions
PARSER_MAP: Dict[str, ParserFunc] = {
    DEVICE_TYPE_PETKIT_FOUNTAIN: parse_petkit_fountain,
    DEVICE_TYPE_S06_SOIL_TESTER: parse_s06_soil_tester,
}

def get_parser(device_type: str) -> Optional[ParserFunc]:
    """Return the parser function for the given device type."""
    parser = PARSER_MAP.get(device_type)
    if parser:
        _LOGGER.debug(f"Using parser {parser.__name__} for device type {device_type}")
    else:
        _LOGGER.warning(f"No parser found for device type: {device_type}")
    return parser

