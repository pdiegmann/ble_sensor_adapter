"""Bluetooth handling for BLE Sensor integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional, Dict

from bleak import BleakClient, BleakScanner, BleakError
from bleak.backends.device import BLEDevice

from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_register_callback,
    async_track_unavailable,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from custom_components.ble_sensor.utils.const import SIGNAL_DEVICE_AVAILABLE, SIGNAL_DEVICE_UNAVAILABLE

_LOGGER = logging.getLogger(__name__)

class BLEConnection:
    """Class to handle BLE connections."""

    def __init__(
        self, 
        hass: HomeAssistant, 
        mac_address: str, 
        entry_id: str,
        data_callback: Callable[[Dict[str, Any]], None],
    ) -> None:
        """Initialize BLE connection handler."""
        self.hass = hass
        self.mac_address = mac_address
        self.entry_id = entry_id
        self.data_callback = data_callback
        self.client: Optional[BleakClient] = None
        self.device: Optional[BLEDevice] = None
        self.connected = False
        self.available = False
        self._unsubscribe_tracking = None
        self._unsubscribe_callbacks = []
        self._reconnect_task = None
        self._stop_event = asyncio.Event()
        self._notification_callbacks = {}

    async def start(self) -> None:
        """Start the connection handler."""
        _LOGGER.info("Starting BLE connection handler for %s", self.mac_address)
        self._stop_event.clear()
        
        # Register for new device callbacks
        @callback
        def _async_device_callback(
            service_info: BluetoothServiceInfoBleak, change: BluetoothChange
        ) -> None:
            """Handle a device update."""
            if service_info.address.lower() == self.mac_address.lower():
                self.device = service_info.device
                self._handle_device_available()
                
        # Register for bluetooth callbacks
        unsubscribe = async_register_callback(
            self.hass,
            _async_device_callback,
            {"address": self.mac_address},
            BluetoothScanningMode.ACTIVE,
        )
        self._unsubscribe_callbacks.append(unsubscribe)
        
        # Check if the device is already available
        self.device = async_ble_device_from_address(self.hass, self.mac_address)
        if self.device:
            self._handle_device_available()
        
        # Start the connection manager
        self._reconnect_task = self.hass.async_create_task(self._connection_manager())

    async def stop(self) -> None:
        """Stop the connection handler."""
        self._stop_event.set()
        
        # Cancel reconnect task
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            
        # Disconnect from device
        await self._disconnect()
        
        # Unsubscribe from callbacks
        if self._unsubscribe_tracking is not None:
            self._unsubscribe_tracking()
            self._unsubscribe_tracking = None
            
        for unsubscribe in self._unsubscribe_callbacks:
            unsubscribe()
        self._unsubscribe_callbacks = []

    async def _connection_manager(self) -> None:
        """Manage the BLE connection."""
        while not self._stop_event.is_set():
            try:
                if self.device and not self.connected:
                    await self._connect()
                    
                if not self.connected or not self.available:
                    await asyncio.sleep(5)  # Wait before retry
                else:
                    await asyncio.sleep(30)  # Check connection periodically
                    
            except asyncio.CancelledError:
                break
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.error("Error in connection manager: %s", ex)
                await asyncio.sleep(5)  # Wait before retry

    async def _connect(self) -> None:
        """Connect to the BLE device."""
        if self.client and self.client.is_connected:
            return
            
        if not self.device:
            return
            
        _LOGGER.debug("Connecting to %s", self.mac_address)
        
        try:
            self.client = BleakClient(self.device)
            await self.client.connect()
            self.connected = True
            _LOGGER.info("Connected to %s", self.mac_address)
            
            # Subscribe to tracking unavailability
            self._unsubscribe_tracking = async_track_unavailable(
                self.hass, self._handle_device_unavailable, self.device
            )
            
            # Notify that device is available
            self._handle_device_available()
            
            # Set up notifications for all characteristics
            await self._setup_notifications()
            
        except (BleakError, asyncio.TimeoutError) as ex:
            _LOGGER.error("Failed to connect to %s: %s", self.mac_address, ex)
            await self._disconnect()

    async def _disconnect(self) -> None:
        """Disconnect from device."""
        self.connected = False
        
        if self.client and self.client.is_connected:
            try:
                await self.client.disconnect()
            except BleakError:
                pass
                
        self.client = None
        
        if self._unsubscribe_tracking is not None:
            self._unsubscribe_tracking()
            self._unsubscribe_tracking = None

    async def _setup_notifications(self) -> None:
        """Set up notifications for device characteristics."""
        if not self.client or not self.client.is_connected:
            return
            
        try:
            # Discover services and characteristics
            for service in self.client.services:
                for char in service.characteristics:
                    # Check if characteristic supports notifications
                    if "notify" in char.properties:
                        _LOGGER.debug(
                            "Setting up notifications for %s on %s",
                            char.uuid,
                            self.mac_address,
                        )
                        
                        # Create notification handler
                        def create_notification_handler(char_uuid):
                            async def notification_handler(sender, data):
                                """Handle notification received."""
                                try:
                                    _LOGGER.debug(
                                        "Notification from %s: %s",
                                        char_uuid,
                                        data.hex(),
                                    )
                                    # Process and forward data
                                    processed_data = {
                                        "characteristic": char_uuid,
                                        "data": data.hex(),
                                        "raw_data": data,
                                    }
                                    self.data_callback(processed_data)
                                except Exception as ex:  # pylint: disable=broad-except
                                    _LOGGER.error(
                                        "Error handling notification: %s", ex
                                    )
                            return notification_handler
                            
                        # Start notifications
                        handler = create_notification_handler(char.uuid)
                        self._notification_callbacks[char.uuid] = handler
                        await self.client.start_notify(char.uuid, handler)
                        
        except (BleakError, asyncio.TimeoutError) as ex:
            _LOGGER.error(
                "Failed to set up notifications for %s: %s", self.mac_address, ex
            )
            await self._disconnect()

    async def read_characteristic(self, uuid: str) -> bytearray:
        """Read characteristic data."""
        if not self.client or not self.client.is_connected:
            raise BleakError("Not connected")
            
        try:
            return await self.client.read_gatt_char(uuid)
        except (BleakError, asyncio.TimeoutError) as ex:
            _LOGGER.error(
                "Failed to read characteristic %s from %s: %s",
                uuid,
                self.mac_address,
                ex,
            )
            await self._disconnect()
            raise

    async def write_characteristic(
        self, uuid: str, data: bytearray, response: bool = False
    ) -> None:
        """Write to characteristic."""
        if not self.client or not self.client.is_connected:
            raise BleakError("Not connected")
            
        try:
            await self.client.write_gatt_char(uuid, data, response)
        except (BleakError, asyncio.TimeoutError) as ex:
            _LOGGER.error(
                "Failed to write to characteristic %s on %s: %s",
                uuid,
                self.mac_address,
                ex,
            )
            await self._disconnect()
            raise

    def _handle_device_available(self) -> None:
        """Handle when device becomes available."""
        if not self.available:
            self.available = True
            _LOGGER.debug("%s has become available", self.mac_address)
            async_dispatcher_send(
                self.hass, f"{SIGNAL_DEVICE_AVAILABLE}_{self.entry_id}"
            )

    @callback
    def _handle_device_unavailable(self, _: BLEDevice) -> None:
        """Handle when device becomes unavailable."""
        if self.available:
            self.available = False
            _LOGGER.debug("%s is no longer available", self.mac_address)
            async_dispatcher_send(
                self.hass, f"{SIGNAL_DEVICE_UNAVAILABLE}_{self.entry_id}"
            )
            
            # Disconnect and try to reconnect
            self.hass.async_create_task(self._disconnect())