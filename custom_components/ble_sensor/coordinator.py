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

from custom_components.ble_sensor.device_types.petkit_fountain import PetkitFountain
from custom_components.ble_sensor.device_types.soil_tester import SoilTester

from custom_components.ble_sensor.bluetooth import BLEConnection
from custom_components.ble_sensor.const import (
    CONF_DEVICE_TYPE,
    CONF_MAC,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    SIGNAL_DEVICE_UPDATE,
    SIGNAL_DEVICE_AVAILABLE,
    SIGNAL_DEVICE_UNAVAILABLE,
)
from custom_components.ble_sensor.device import BLEDevice
from custom_components.ble_sensor.device_types import get_device_type

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
        self.device_type = get_device_type(self.device_type_name)
        self.device = self.device_type.create_device(self.mac_address)
        
        # Initialize BLE connection
        self.ble_connection = BLEConnection(
            hass, self.mac_address, self.entry_id, self._handle_device_data
        )
        
        # Set polling interval
        update_interval = timedelta(seconds=self.poll_interval)
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.mac_address}",
            update_interval=update_interval if self.device_type.requires_polling() else None,
        )
        
        self._available = False
        self._handlers = []

    async def async_start(self) -> None:
        """Start the coordinator."""
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
        await self.ble_connection.start()

    async def async_stop(self) -> None:
        """Stop the coordinator."""
        # Remove update listeners
        for handler in self._handlers:
            handler()
        self._handlers = []
        
        # Stop BLE connection
        await self.ble_connection.stop()

    @callback
    def _handle_device_data(self, data: Dict[str, Any]) -> None:
        """Handle received device data."""
        _LOGGER.debug("Received data from %s: %s", self.mac_address, data)
        
        if self.device.update_from_data(data):
            self.device.available = True
            self._available = True
            self.async_set_updated_data(self.device.data)
            
            # Send update signal
            async_dispatcher_send(
                self.hass, f"{SIGNAL_DEVICE_UPDATE}_{self.entry_id}", self.device.data
            )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data via polling if needed."""
        # Skip polling if device is not available or doesn't need polling
        if not self._available or not self.device_type.requires_polling():
            return self.device.data or {}
            
        try:
            # Special handling for Petkit Fountain and S-06 Soil Tester
            if isinstance(self.device_type, PetkitFountain) or isinstance(self.device_type, SoilTester):
                # Use the custom fetch method for Petkit devices
                data = await self.device_type.async_custom_fetch_data(self.ble_connection.client)
                if data:
                    self.device.update_from_data(data)
                    self.device.available = True
                return self.device.data or {}
                
            # For other devices, use the normal polling approach
            for uuid in self.device_type.get_characteristics():
                try:
                    data = await self.ble_connection.read_characteristic(uuid)
                    if data:
                        self._handle_device_data({
                            "characteristic": uuid,
                            "data": data.hex(),
                            "raw_data": data,
                        })
                except Exception as ex:
                    _LOGGER.error(
                        "Failed to read characteristic %s: %s", uuid, ex
                    )
                    
            return self.device.data or {}
        except Exception as ex:
            _LOGGER.error("Error updating device data: %s", ex)
            raise UpdateFailed(f"Error communicating with device: {ex}") from ex