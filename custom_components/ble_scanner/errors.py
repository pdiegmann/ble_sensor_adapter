"""Custom exceptions for BLE Scanner integration."""

from homeassistant.exceptions import HomeAssistantError

class BLEScannerError(HomeAssistantError):
    """Base class for BLE Scanner errors."""

class DeviceNotFoundError(BLEScannerError):
    """Raised when a configured device cannot be found."""

class ConnectionError(BLEScannerError):
    """Raised when connection to a device fails."""

class ParsingError(BLEScannerError):
    """Error occurred during BLE data parsing."""

class UnsupportedDeviceTypeError(BLEScannerError):
    """Raised when an unsupported device type is configured."""

