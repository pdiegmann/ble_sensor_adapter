"""Base class for device-specific BLE connection handlers."""
import logging
from abc import ABC, abstractmethod # noqa: F401
from typing import Any, Dict

from bleak import BleakClient
from bleak.backends.device import BLEDevice # Keep for type hint if needed elsewhere
from bleak.exc import BleakError # Keep for exception handling if needed

# Removed HomeAssistant import as it's not used directly here
from homeassistant.const import CONF_ADDRESS, CONF_NAME

# Removed ATTR_LAST_UPDATED, ATTR_RSSI as coordinator handles metadata
# from custom_components.ble_scanner.const import ATTR_LAST_UPDATED, ATTR_RSSI


class BaseDeviceHandler(ABC):
    """
    Base class for device-specific BLE data fetching logic.

    The coordinator manages the connection lifecycle (connect/disconnect).
    This handler receives a connected BleakClient instance and is responsible
    for interacting with the device to fetch data.
    """

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """Initialize the base handler."""
        # Store config needed for identification or interaction logic
        self.config = config
        self._address = config.get(CONF_ADDRESS, "").lower()
        self._name = config.get(CONF_NAME, "")
        # Use address as the primary identifier if available
        self._device_id = self._address if self._address else self._name.lower() if self._name else "unknown_device"
        self.logger = logger # Store logger instance

    @property
    def device_id(self) -> str:
        """Return the unique identifier for this device (usually MAC address)."""
        return self._device_id

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @abstractmethod
    async def async_fetch_data(self, client: BleakClient) -> Dict[str, Any]:
        """
        Fetch data from the connected BLE device.

        This method must be implemented by subclasses.

        Args:
            client: A connected BleakClient instance.

        Returns:
            A dictionary containing the fetched sensor data.

        Raises:
            BleakError: If a Bluetooth communication error occurs.
            Exception: For other unexpected errors during data fetching.
        """
        raise NotImplementedError("Device handler must implement async_fetch_data")

    # --- Helper methods for subclasses (optional) ---

    # Example helper (subclasses might implement similar ones)
    # async def read_characteristic(self, client: BleakClient, uuid: str) -> bytes:
    #     """Helper to read a characteristic value."""
    #     try:
    #         value = await client.read_gatt_char(uuid)
    #         _LOGGER.debug(f"[{self.device_id}] Read {uuid}: {value.hex()}")
    #         return value
    #     except BleakError as e:
    #         _LOGGER.error(f"[{self.device_id}] BleakError reading {uuid}: {e}")
    #         raise
    #     except Exception as e:
    #         _LOGGER.error(f"[{self.device_id}] Error reading {uuid}: {e}", exc_info=True)
    #         raise

    # Subclasses can add methods for specific interactions like writing, subscribing etc.
    # def parse_temperature(self, data: bytes) -> float:
    #     """Example parsing logic."""
    #     # Implementation specific to device
    #     pass

