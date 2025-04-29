"""Device handler factory and base class for active BLE connections."""
import logging
from typing import Type, Optional, Dict, Any

from homeassistant.core import HomeAssistant

from ble_scanner.const import (
    LOGGER_NAME,
    DEVICE_TYPE_PETKIT_FOUNTAIN,
    DEVICE_TYPE_S06_SOIL_TESTER,
)

# Import specific handlers
from ble_scanner.devices.petkit_fountain import PetkitFountainHandler
from ble_scanner.devices.s06_soil_tester import S06SoilTesterHandler
from ble_scanner.devices.base import BaseDeviceHandler

_LOGGER = logging.getLogger(LOGGER_NAME)

# Map device types to their handler classes
HANDLER_MAP: Dict[str, Type[BaseDeviceHandler]] = {
    DEVICE_TYPE_PETKIT_FOUNTAIN: PetkitFountainHandler,
    DEVICE_TYPE_S06_SOIL_TESTER: S06SoilTesterHandler,
}

def get_device_handler(device_type: str) -> Optional[Type[BaseDeviceHandler]]:
    """Get the appropriate handler class for a given device type."""
    handler = HANDLER_MAP.get(device_type)
    if not handler:
        _LOGGER.warning(f"No active connection handler registered for device type: {device_type}")
    return handler

