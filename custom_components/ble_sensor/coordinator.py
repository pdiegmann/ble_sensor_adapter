"""Data update coordinator for BLE Sensor."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.ble_sensor.devices.petkit_fountain import PetkitFountain
from custom_components.ble_sensor.devices.soil_tester import SoilTester

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak, BluetoothChange
from bleak.exc import BleakError
from homeassistant.core import callback
import async_timeout

from custom_components.ble_sensor.utils.bluetooth import BLEConnection
from custom_components.ble_sensor.utils.const import (
    CONF_DEVICE_TYPE,
    CONF_MAC,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    SIGNAL_DEVICE_UPDATE,
    SIGNAL_DEVICE_AVAILABLE,
    SIGNAL_DEVICE_UNAVAILABLE,
)
from custom_components.ble_sensor.devices.device import BLEDevice
from custom_components.ble_sensor.devices import get_device_type

_LOGGER = logging.getLogger(__name__)

class BLESensorDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching BLE Sensor data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.hass = hass
        self.entry = entry
        self.entry_id = entry.entry_id
        
        # Extract configuration
        self.mac_address = entry.data[CONF_MAC]
        self.device_type_name = entry.data[CONF_DEVICE_TYPE]
        self.poll_interval = entry.options.get(
            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
        )
        
        # Create device type and device
        try:
            self.device_type = get_device_type(self.device_type_name)
            self.device = self.device_type.create_device(self.mac_address)
        except Exception as ex:
            _LOGGER.error("Failed to create device type: %s", ex)
            raise ConfigEntryNotReady from ex
        
        # Initialize BLE connection
        self.ble_connection = BLEConnection(
            hass, self.mac_address, self.entry_id, self._handle_device_data
        )
        
        # Set polling interval with a minimum of 30 seconds to prevent excessive connections
        update_interval = timedelta(seconds=max(30, self.poll_interval))
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.mac_address}",
            update_interval=update_interval if self.device_type.requires_polling() else None,
        )
        
        self._available = False
        self._handlers = []
        self._initialization_lock = asyncio.Lock()
        self._initialization_complete = False

    async def async_start(self) -> None:
        """Start the coordinator."""
        try:
            async with self._initialization_lock:
                if self._initialization_complete:
                    return

                # Register for availability updates
                @callback
                def async_device_available(_: Any = None) -> None:
                    """Handle when device becomes available."""
                    if not self._available:
                        self._available = True
                        _LOGGER.debug("%s has become available", self.mac_address)
                        self.async_set_updated_data(self.device.data)
                        
                self._handlers.append(
                    async_dispatcher_connect(
                        self.hass,
                        f"{SIGNAL_DEVICE_AVAILABLE}_{self.entry_id}",
                        async_device_available,
                    )
                )
                
                @callback
                def async_device_unavailable(_: Any = None) -> None:
                    """Handle when device becomes unavailable."""
                    if self._available:
                        self._available = False
                        self.device.available = False
                        _LOGGER.debug("%s is no longer available", self.mac_address)
                        self.async_update_listeners()
                        
                self._handlers.append(
                    async_dispatcher_connect(
                        self.hass,
                        f"{SIGNAL_DEVICE_UNAVAILABLE}_{self.entry_id}",
                        async_device_unavailable,
                    )
                )
                
                # Start the BLE connection
                try:
                    await self.ble_connection.start()
                except Exception as ex:
                    _LOGGER.error("Failed to start BLE connection: %s", ex)
                    raise ConfigEntryNotReady from ex

                self._initialization_complete = True

        except Exception as ex:
            _LOGGER.error("Failed to initialize coordinator: %s", ex)
            await self.async_stop()
            raise

    async def async_stop(self) -> None:
        """Stop the coordinator."""
        # Remove update listeners
        for handler in self._handlers:
            handler()
        self._handlers = []
        
        # Stop BLE connection
        try:
            await self.ble_connection.stop()
        except Exception as ex:
            _LOGGER.error("Error stopping BLE connection: %s", ex)

        self._initialization_complete = False

    @callback
    def _handle_device_data(self, data: Dict[str, Any]) -> None:
        """Handle received device data."""
        _LOGGER.debug("Received data from %s: %s", self.mac_address, data)
        
        try:
            if self.device.update_from_data(data):
                self.device.available = True
                self._available = True
                self.async_set_updated_data(self.device.data)
                
                # Send update signal
                async_dispatcher_send(
                    self.hass, f"{SIGNAL_DEVICE_UPDATE}_{self.entry_id}", self.device.data
                )
        except Exception as ex:
            _LOGGER.error("Error handling device data: %s", ex)

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from all configured devices."""
        result = {}
        
        # No devices configured
        if not self.device_configs:
            return result
            
        # Try to update each device
        for device_config in self.device_configs:
            device_id = device_config.device_id
            address = device_config.address
            device_type = device_config.device_type
            
            # Skip devices that are not due for update yet
            if not self._is_update_due(device_id):
                if device_id in self._device_data:
                    result[device_id] = self._device_data[device_id]
                continue
                
            # Get the device handler
            device_handler = self._get_device_handler(device_type)
            if not device_handler:
                _LOGGER.error(
                    "No handler available for device type: %s", 
                    device_type
                )
                continue
                
            # Get a fresh BLE device (don't reuse stored ones)
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, address, connectable=True
            )
            
            if not ble_device:
                _LOGGER.debug(
                    "Device %s (%s) not currently reachable", 
                    device_config.name, 
                    address
                )
                # Mark device as unavailable
                self._device_status[device_id] = False
                continue
                
            # Connect and get data
            try:
                data = await device_handler.connect_and_get_data(self.hass, address)
                
                if data:
                    # Store data and mark device as available
                    self._device_data[device_id] = data
                    self._device_status[device_id] = True
                    result[device_id] = data
                    
                    # Update last successful update timestamp
                    self._last_update[device_id] = time.time()
                else:
                    # No data received, mark device as unavailable
                    self._device_status[device_id] = False
                    
            except Exception as ex:
                _LOGGER.error(
                    "Error updating device %s (%s): %s",
                    device_config.name,
                    address,
                    str(ex),
                )
                # Mark device as unavailable on error
                self._device_status[device_id] = False
                
        return result
            

    @callback
    def device_discovered(self, service_info: BluetoothServiceInfoBleak, device_id: str, change: BluetoothChange) -> None:
        """Handle a discovered device."""
        # Log the discovery
        self._logger.debug(
            "Device %s discovered: %s (RSSI: %d)",
            device_id,
            service_info.address,
            service_info.advertisement.rssi
        )

        if not hasattr(self, '_devices_info'):
            self._devices_info = {}
        self._devices_info[device_id] = service_info
        
        # Mark the device as potentially available
        # The actual status will be determined during actual connection
        if device_id in self._device_status and not self._device_status[device_id]:
            # Only schedule an update if the device was previously unavailable
            # and is now seen again
            self._schedule_update_for_device(device_id)
    
    @callback
    def device_unavailable(self, service_info: BluetoothServiceInfoBleak, device_id: str) -> None:
        """Handle a device becoming unavailable."""
        self._logger.debug("Device %s unavailable: %s", device_id, service_info.address)
        
        # Mark the device as unavailable in your system
        if device_id in self._device_status:
            self._device_status[device_id] = False
        
        # Notify entities that depend on this device
        self.async_update_listeners()
        
        # Cancel any pending updates for this device
        if device_id in self._pending_updates:
            if self._pending_updates[device_id] is not None:
                self._pending_updates[device_id].cancel()
            self._pending_updates[device_id] = None

    def _schedule_update_for_device(self, device_id):
        """Schedule an update for a specific device."""
        # Cancel any existing update for this device
        if device_id in self._pending_updates and self._pending_updates[device_id]:
            self._pending_updates[device_id].cancel()
        
        # Schedule a new update
        self._pending_updates[device_id] = asyncio.create_task(
            self._update_device(device_id)
        )

    async def _update_device(self, device_id):
        """Update a specific device."""
        # Find the device config
        device_config = next(
            (d for d in self.device_configs if d.device_id == device_id), 
            None
        )
        if not device_config:
            return
            
        # Connect and update
        try:
            await self._async_update_data()
        except Exception as ex:
            _LOGGER.error(
                "Error updating device %s: %s", 
                device_id, 
                str(ex)
            )
    
    async def async_update_device(self, device_id: str) -> None:
        """Update data from a specific device."""
        if device_id not in self._devices_info:
            self._logger.warning("Tried to update unknown device: %s", device_id)
            return
        
        # Get the device config and service info
        device_config = next((d for d in self.device_configs if d.device_id == device_id), None)
        if not device_config:
            return
            
        service_info = self._devices_info[device_id]
        
        # Get a connectable BLE device
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, service_info.address, connectable=True
        )
        
        if not ble_device:
            self._logger.warning(
                "No connectable device found for %s", service_info.address
            )
            return
        
        # Get the appropriate device handler
        device_handler = self._get_device_handler(device_config.device_type)
        if not device_handler:
            self._logger.error("No handler for device type: %s", device_config.device_type)
            return
        
        # Connect and retrieve data
        try:
            async with async_timeout.timeout(30):  # 30 second timeout
                data = await device_handler.async_connect_and_get_data(ble_device)
            
            # Store the data and mark device as available
            self._device_data[device_id] = data
            self._device_status[device_id] = True
            
            # Update all listeners
            self.async_update_listeners()
            
        except (BleakError, TimeoutError, Exception) as error:
            self._logger.error(
                "Error connecting to %s (%s): %s",
                device_config.name,
                service_info.address,
                str(error),
            )
    
    # Update your existing async_update method to use the new per-device update function
    async def async_update(self):
        """Fetch all data from devices."""
        for device_id in self._device_ids:
            await self.async_update_device(device_id)