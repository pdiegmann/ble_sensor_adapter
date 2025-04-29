"""Base class for device-specific BLE connection handlers."""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_ADDRESS, CONF_NAME

from ..const import ATTR_LAST_UPDATED, ATTR_RSSI

class BaseDeviceHandler:
    """Base class for handling active BLE connections and data parsing."""

    def __init__(self, hass: HomeAssistant, config: Dict[str, Any], logger: logging.Logger):
        """Initialize the base handler."""
        self.hass = hass
        self.config = config
        self.logger = logger
        self._address = config.get(CONF_ADDRESS, "").lower()
        self._name = config.get(CONF_NAME, "")
        self._device_id = self._address if self._address else self._name.lower()
        self._client: Optional[BleakClient] = None
        self._latest_data: Dict[str, Any] = {}
        self._last_update_time: Optional[datetime] = None
        self._is_available: bool = False
        self._connection_lock = asyncio.Lock() # Lock for connection/disconnection
        self._update_lock = asyncio.Lock() # Lock for update process
        self._rssi: Optional[int] = None # Store last known RSSI if available

    @property
    def device_id(self) -> str:
        """Return the unique identifier for this device."""
        return self._device_id

    @property
    def is_connected(self) -> bool:
        """Return True if the client is currently connected."""
        return self._client is not None and self._client.is_connected

    @property
    def last_update_time(self) -> Optional[datetime]:
        """Return the timestamp of the last successful update."""
        return self._last_update_time

    def get_latest_data(self) -> Dict[str, Any]:
        """Return the latest data dictionary, including availability status."""
        # Ensure metadata is included
        data = self._latest_data.copy()
        if self._last_update_time:
            data[ATTR_LAST_UPDATED] = self._last_update_time.isoformat()
        if self._rssi is not None:
            data[ATTR_RSSI] = self._rssi
        # Add an availability key? No, sensors check coordinator.get_last_seen
        return data

    def update_address(self, address: str):
        """Update the address if found via discovery by name."""
        if not self._address and address:
            self.logger.info(f"Updating address for {self.device_id} to {address}")
            self._address = address.lower()
            # Update device_id only if it was based on name
            if self.device_id == self._name.lower():
                 self._device_id = self._address

    def mark_unavailable(self):
        """Mark the device as unavailable."""
        self.logger.debug(f"Marking device {self.device_id} as unavailable")
        self._is_available = False
        # Optionally clear data or keep stale data?
        # Keep stale data, sensors will show unavailable based on timestamp

    async def _ensure_connected(self, ble_device: BLEDevice) -> bool:
        """Ensure the client is connected to the device."""
        async with self._connection_lock:
            if self.is_connected:
                return True

            self.logger.info(f"Attempting to connect to {self.device_id} ({ble_device.address})")
            try:
                self._client = BleakClient(ble_device)
                connected = await self._client.connect()
                if connected:
                    self.logger.info(f"Successfully connected to {self.device_id}")
                    self._is_available = True
                    # Store RSSI if available from the BLEDevice object
                    if hasattr(ble_device, "rssi") and ble_device.rssi is not None:
                        self._rssi = ble_device.rssi
                    return True
                else:
                    self.logger.error(f"Failed to connect to {self.device_id}")
                    self._client = None
                    self._is_available = False
                    return False
            except BleakError as e:
                self.logger.error(f"BleakError during connection to {self.device_id}: {e}")
                self._client = None
                self._is_available = False
                return False
            except Exception as e:
                self.logger.error(f"Unexpected error during connection to {self.device_id}: {e}", exc_info=True)
                self._client = None
                self._is_available = False
                return False

    async def disconnect(self) -> None:
        """Disconnect the client if connected."""
        async with self._connection_lock:
            if self.is_connected and self._client:
                self.logger.info(f"Disconnecting from {self.device_id}")
                try:
                    await self._client.disconnect()
                except BleakError as e:
                    self.logger.warning(f"BleakError during disconnection from {self.device_id}: {e}")
                except Exception as e:
                    self.logger.error(f"Unexpected error during disconnection from {self.device_id}: {e}", exc_info=True)
                finally:
                    self._client = None
                    self._is_available = False # Mark unavailable on disconnect
            else:
                self.logger.debug(f"Disconnect called but client not connected for {self.device_id}")
            # Always clear client and availability on explicit disconnect call
            self._client = None
            self._is_available = False

    async def update(self, ble_device: BLEDevice) -> None:
        """Connect to the device, perform update logic, and store data."""
        async with self._update_lock:
            if not await self._ensure_connected(ble_device):
                self.mark_unavailable()
                return

            try:
                # --- Device-specific update logic goes here --- #
                # This method should be overridden by subclasses
                # Example: Read characteristics, subscribe to notifications, send commands
                self.logger.debug(f"Performing update for {self.device_id} (Base Handler - No specific logic)")
                # Placeholder: Read RSSI if possible (might require active connection feature)
                try:
                    if self.is_connected and self._client:
                        # Reading RSSI might not be standard/reliable via client
                        # Use RSSI from discovery (ble_device) if available
                        if hasattr(ble_device, "rssi") and ble_device.rssi is not None:
                             self._rssi = ble_device.rssi
                             self._latest_data[ATTR_RSSI] = self._rssi
                        pass
                except Exception as rssi_err:
                    self.logger.debug(f"Could not read RSSI for {self.device_id}: {rssi_err}")

                # --- End of device-specific logic --- #

                self._last_update_time = datetime.now()
                self._is_available = True # Mark available on successful update
                self.logger.debug(f"Update successful for {self.device_id}, data: {self._latest_data}")

            except BleakError as e:
                self.logger.error(f"BleakError during update for {self.device_id}: {e}")
                self.mark_unavailable()
                # Consider disconnecting on error?
                await self.disconnect() # Disconnect on update error
                raise # Re-raise the exception for the coordinator
            except Exception as e:
                self.logger.error(f"Unexpected error during update for {self.device_id}: {e}", exc_info=True)
                self.mark_unavailable()
                await self.disconnect() # Disconnect on update error
                raise # Re-raise the exception for the coordinator

    # --- Methods to be implemented by subclasses --- #

    async def _read_data(self):
        """Placeholder for reading data from characteristics."""
        raise NotImplementedError

    async def _subscribe_to_notifications(self):
        """Placeholder for subscribing to notifications."""
        raise NotImplementedError

    def _notification_callback(self, sender, data):
        """Placeholder for handling incoming notifications."""
        raise NotImplementedError

    async def _send_command(self, command_bytes: bytes):
        """Placeholder for sending commands."""
        raise NotImplementedError

