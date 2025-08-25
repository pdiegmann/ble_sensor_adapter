"""Data update coordinator for BLE Sensor."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Any, Dict, Optional, List
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryNotReady

from homeassistant.components.bluetooth import async_ble_device_from_address
from bleak.exc import BleakError

from custom_components.ble_sensor.utils.const import (
    CONF_DEVICE_TYPE,
    CONF_MAC,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_DEVICE_TYPE,
    DOMAIN,
)
from custom_components.ble_sensor.devices import get_device_type

_LOGGER = logging.getLogger(__name__)

@dataclass
class DeviceConfig:
    """Class to hold device configuration."""
    device_id: str
    name: str
    address: str
    device_type: str
    polling_interval: int = DEFAULT_POLL_INTERVAL

class BLESensorCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching BLE Sensor data."""

    def __init__(
        self, 
        hass: HomeAssistant, 
        logger: logging.Logger,
        devices: List[Dict[str, Any]],
        update_interval: Optional[timedelta] = None
    ) -> None:
        """Initialize the coordinator."""
        self.device_configs = []
        
        # Initialize data storage
        self._device_data = {}  # Stores the latest data for each device
        self._device_status = {}  # Stores whether each device is available
        self._last_update = {}  # Stores the timestamp of the last successful update

        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=update_interval or self._get_min_update_interval(devices),
        )

        for device in devices:
            self.add_device(device)

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
                
            # Get the device handler (simplified - we know it's Petkit Fountain)
            device_handler = get_device_type()  # Always returns Petkit Fountain handler
                
            # Get a fresh BLE device (don't reuse stored ones)
            ble_device = async_ble_device_from_address(
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
                data = await device_handler.async_custom_fetch_data(ble_device)                
                if data:
                    # Store data and mark device as available
                    self._device_data[device_id] = data
                    self._device_status[device_id] = True
                    result[device_id] = data
                    
                    # Update last successful update timestamp
                    self._last_update[device_id] = time.time()
                    _LOGGER.debug("Successfully updated device %s with data: %s", device_id, data)
                else:
                    # No data received, mark device as unavailable
                    self._device_status[device_id] = False
                    _LOGGER.warning("No data received from device %s", device_id)
                    
            except Exception as ex:
                _LOGGER.error(
                    "Error updating device %s (%s): %s",
                    device_config.name,
                    address,
                    str(ex),
                    exc_info=True
                )
                # Mark device as unavailable on error
                self._device_status[device_id] = False
                
        return result

    def _get_min_update_interval(self, devices: Optional[List[Dict[str, Any]]] = None) -> timedelta:
        """Get the minimum polling interval from all devices."""
        if not devices:
            devices = [
                {
                    "id": d.device_id,
                    "polling_interval": d.polling_interval
                } 
                for d in self.device_configs
            ]
        if not devices:
            return timedelta(seconds=DEFAULT_POLL_INTERVAL)
            
        min_interval = min(
            device.get("polling_interval", DEFAULT_POLL_INTERVAL) 
            for device in devices
        )
        
        # Ensure minimum interval is at least 30 seconds to avoid overwhelming
        return timedelta(seconds=max(min_interval, 30))
        
    def _is_update_due(self, device_id: str) -> bool:
        """Determine if a device is due for an update."""
        device_config = next(
            (d for d in self.device_configs if d.device_id == device_id), 
            None
        )
        
        if not device_config:
            return False
            
        last_update = self._last_update.get(device_id, 0)
        now = time.time()
        
        # Check if enough time has passed since the last update
        return (now - last_update) >= device_config.polling_interval
    
    def is_device_available(self, device_id: str) -> bool:
        """Return if device is available."""
        return self._device_status.get(device_id, False)
        
    def get_device_data(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest data for a device."""
        return self._device_data.get(device_id)
    
    def add_device(self, device_config: Dict[str, Any]) -> str:
        """Add a new device to be monitored."""
        address = device_config.get("address") or device_config.get("mac") or device_config.get("mac_address")
        device_id = device_config.get("id", address)
        
        # Check if device already exists
        if any(d.device_id == device_id for d in self.device_configs):
            return device_id
            
        # Create a new DeviceConfig and add it
        # Simplified: device type defaults to Petkit Fountain
        config = DeviceConfig(
            device_id=device_id,
            name=device_config.get("name", f"Petkit Fountain {address}"),
            address=address,
            device_type=device_config.get("type", DEFAULT_DEVICE_TYPE),
            polling_interval=device_config.get("polling_interval", DEFAULT_POLL_INTERVAL),
        )
        
        self.device_configs.append(config)
        
        # Initialize data stores for this device
        self._device_status[device_id] = False
        self._last_update[device_id] = 0
        
        # Recalculate update interval
        self.update_interval = self._get_min_update_interval()
        
        return device_id
        
    def remove_device(self, device_id: str) -> bool:
        """Remove a device from monitoring."""
        # Find the device
        device_index = next(
            (i for i, d in enumerate(self.device_configs) if d.device_id == device_id), 
            None
        )
        
        if device_index is None:
            return False
            
        # Remove the device
        self.device_configs.pop(device_index)
        
        # Clean up data stores
        if device_id in self._device_data:
            del self._device_data[device_id]
        if device_id in self._device_status:
            del self._device_status[device_id]
        if device_id in self._last_update:
            del self._last_update[device_id]
            
        # Recalculate update interval
        self.update_interval = self._get_min_update_interval()
        
        return True

