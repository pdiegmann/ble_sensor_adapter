"""Data update coordinator for BLE Sensor."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Optional

from bleak.exc import BleakError

from custom_components.ble_sensor.devices import get_device_type
from custom_components.ble_sensor.utils.const import (CONF_DEVICE_TYPE,
                                                      CONF_MAC,
                                                      CONF_POLL_INTERVAL,
                                                      DEFAULT_DEVICE_TYPE,
                                                      DEFAULT_POLL_INTERVAL,
                                                      DOMAIN)
from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import (DataUpdateCoordinator,
                                                      UpdateFailed)

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
        devices: list[dict[str, Any]],
        update_interval: timedelta | None = None
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
        
        # Perform initial Bluetooth integration check
        # Note: Cannot call async method from sync __init__, so we defer this check

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from all configured devices."""
        result = {}

        # No devices configured
        if not self.device_configs:
            return result

        _LOGGER.info("Coordinator update cycle starting for %d devices", len(self.device_configs))

        # Check Bluetooth integration on first update cycle
        if not hasattr(self, '_bt_check_done'):
            await self._check_bluetooth_integration()
            self._bt_check_done = True

        # Try to update each device
        for device_config in self.device_configs:
            await self._update_single_device(device_config, result)

        return result

    async def _update_single_device(self, device_config, result):
        device_id = device_config.device_id
        address = device_config.address.upper()  # Normalize MAC address to uppercase
        # Validate MAC address format
        if not self._is_valid_mac_address(address):
            _LOGGER.error("Invalid MAC address format: %s", address)
            self._device_status[device_id] = False
            return

        # Skip devices that are not due for update yet
        if not self._is_update_due(device_id):
            _LOGGER.info("Device %s not due for update yet (last update: %s, interval: %s)",
                        device_id, self._last_update.get(device_id, 'never'), device_config.polling_interval)
            if device_id in self._device_data:
                result[device_id] = self._device_data[device_id]
            return

        _LOGGER.info("Processing device %s (%s) - due for update", device_id, address)

        # Get the device handler (simplified - we know it's Petkit Fountain)
        device_handler = get_device_type()  # Always returns Petkit Fountain handler

        # Get a fresh BLE device (don't reuse stored ones)
        try:
            ble_device = async_ble_device_from_address(
                self.hass, address, connectable=True
            )
        except Exception as e:
            _LOGGER.error(
                "Error looking up BLE device %s: %s",
                address, str(e), exc_info=True
            )
            self._device_status[device_id] = False
            return

        if not ble_device:
            _LOGGER.warning(
                "Device %s (%s) not currently reachable via Bluetooth. "
                "Ensure device is powered on, nearby, and not connected to other apps.",
                device_config.name,
                address
            )
            # Try alternative BLE device discovery methods
            try:
                await self._try_alternative_ble_discovery(address)
            except Exception as e:
                _LOGGER.debug("Alternative BLE discovery failed: %s", e)
            # Mark device as unavailable
            self._device_status[device_id] = False
            return

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
                _LOGGER.info("Successfully updated device %s with data: %s", device_id, data)
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

    def _get_min_update_interval(self, devices: list[dict[str, Any]] | None = None) -> timedelta:
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

    def get_device_data(self, device_id: str) -> dict[str, Any] | None:
        """Get the latest data for a device."""
        return self._device_data.get(device_id)

    def add_device(self, device_config: dict[str, Any]) -> str:
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

    def _is_valid_mac_address(self, mac: str) -> bool:
        """Validate MAC address format (XX:XX:XX:XX:XX:XX)."""
        pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        return bool(re.match(pattern, mac))
    
    async def _check_bluetooth_integration(self) -> None:
        """Check if Home Assistant's Bluetooth integration is properly configured."""
        try:
            from homeassistant.components.bluetooth import async_get_bluetooth
            bluetooth_manager = await async_get_bluetooth(self.hass)
            
            if not bluetooth_manager:
                _LOGGER.error(
                    "Home Assistant Bluetooth integration is not available. "
                    "Please ensure the 'bluetooth' integration is configured and enabled."
                )
                return
            
            # Check for available adapters
            adapters = getattr(bluetooth_manager, 'adapters', {})
            if not adapters:
                _LOGGER.warning(
                    "No Bluetooth adapters found. Ensure your system has a working Bluetooth adapter "
                    "and the bluetooth integration has discovered it."
                )
            else:
                _LOGGER.info(
                    "Bluetooth integration OK: Found %d adapter(s): %s", 
                    len(adapters), list(adapters.keys())
                )
                
        except ImportError:
            _LOGGER.error("Failed to import Bluetooth integration - check Home Assistant version compatibility")
        except Exception as e:
            _LOGGER.error("Error checking Bluetooth integration: %s", e, exc_info=True)
    
    async def _try_alternative_ble_discovery(self, address: str) -> None:
        """Try alternative methods to discover the BLE device."""
        try:
            from homeassistant.components.bluetooth import async_discovered_service_info
            
            # Check if device has been discovered recently
            discovered_devices = async_discovered_service_info(self.hass, connectable=True)
            
            # Look for our target device in discovered devices
            target_device = None
            for device_info in discovered_devices:
                if device_info.address.upper() == address.upper():
                    target_device = device_info
                    break
            
            if target_device:
                _LOGGER.info(
                    "Device %s found in discovered devices but not available via async_ble_device_from_address. "
                    "Device info: name=%s, rssi=%s", 
                    address, target_device.name, getattr(target_device, 'rssi', 'unknown')
                )
            else:
                _LOGGER.info(
                    "Device %s not found in %d discovered devices. "
                    "Available devices: %s", 
                    address, 
                    len(discovered_devices),
                    [f"{d.address}({d.name})" for d in discovered_devices[:5]]  # Show first 5
                )
                _LOGGER.info(
                    "TROUBLESHOOTING TIPS for device %s:\n"
                    "1. Ensure the Petkit fountain is powered ON and nearby (within 10 meters)\n"
                    "2. Make sure the fountain is NOT connected to the Petkit app on your phone\n"
                    "3. Try power cycling the fountain (turn off/on)\n"
                    "4. In Home Assistant, go to Settings > Devices & Services > Bluetooth integration\n"
                    "5. You may need to restart the Bluetooth integration or Home Assistant",
                    address
                )
                
        except Exception as e:
            _LOGGER.debug("Failed alternative BLE discovery: %s", e)
