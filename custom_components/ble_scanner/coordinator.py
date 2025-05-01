"""DataUpdateCoordinator for the BLE Scanner integration using passive scanning."""
# Removed asyncio as active connections are removed
import logging
from datetime import timedelta, datetime # Keep datetime for potential timestamping
from typing import Any, Dict, Optional, Callable, Set, Tuple # Added Tuple

# Removed async_timeout, bleak imports (BleakClient, BLEDevice, AdvertisementData, BleakError)

import async_timeout
import bleak
from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakError

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
# Removed Debouncer as updates are event-driven
from homeassistant.const import CONF_ADDRESS # Keep address constant
# Import Bluetooth components
from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothServiceInfoBleak,
    async_register_scanner,
    async_get_advertisement_callback,
)

from custom_components.ble_scanner.const import (
    DOMAIN,
    # Removed CONF_DEVICES, CONF_DEVICE_NAME, CONF_DEVICE_TYPE
    CONF_POLLING_INTERVAL, # Keep for potential future use or cleanup interval
    DEFAULT_POLLING_INTERVAL,
    ATTR_LAST_UPDATED,
    ATTR_RSSI,
    LOGGER_NAME,
)
# Removed DeviceNotFoundError, UnsupportedDeviceTypeError (handled differently)
from custom_components.ble_scanner.errors import ParsingError
# Import parsers instead of active handlers
from custom_components.ble_scanner.parsers import get_parser, BaseParser


_LOGGER = logging.getLogger(LOGGER_NAME)

# Data structure for coordinator.data: Dict[str, Dict[str, Any]]
# Maps device address (lowercase) to a dictionary of its parsed sensor values
CoordinatorData = Dict[str, Dict[str, Any]]

# How long to wait before considering a device unavailable (seconds)
DEVICE_UNAVAILABLE_TIMEOUT = 1800 # 30 minutes


class BLEScannerCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Class to manage BLE data via passive scanning."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        # Use polling interval from data (set during config flow)
        # Might be used for cleanup tasks later, not for scanning interval
        self.polling_interval = entry.data.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL)
        self._scanner_unregister_callback: Optional[Callable] = None
        self._last_seen: Dict[str, datetime] = {} # Track last seen time for devices

        # Initialize with empty data
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # Update interval is not strictly needed for scanning,
            # but can be used for periodic cleanup of old devices.
            # Set it based on config, minimum 60s.
            update_interval=timedelta(seconds=max(60, self.polling_interval)),
            # No debouncer needed for event-driven updates
        )

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle discovery updates from Bluetooth integration."""
        address = service_info.address.lower()
        _LOGGER.debug(f"Received BLE update for {service_info.name} ({address})")

        parser_cls = get_parser(service_info)
        if not parser_cls:
            _LOGGER.debug(f"No parser found for device {address}, skipping.")
            return

        parser: BaseParser = parser_cls()
        try:
            parsed_data = parser.parse(service_info)
            if parsed_data is None:
                _LOGGER.debug(f"Parser for {address} returned None, skipping update.")
                return

            # Add metadata
            parsed_data[ATTR_LAST_UPDATED] = datetime.now().isoformat()
            parsed_data[ATTR_RSSI] = service_info.rssi

            _LOGGER.debug(f"Parsed data for {address}: {parsed_data}")

            # Update coordinator data
            # Ensure data dict exists
            if self.data is None:
                self.data = {}
            self.data[address] = parsed_data
            self._last_seen[address] = datetime.now() # Update last seen time

            # Notify listeners
            self.async_set_updated_data(self.data)

        except ParsingError as e:
            _LOGGER.error(f"Error parsing data for {address}: {e}")
        except Exception as e:
            _LOGGER.exception(f"Unexpected error processing BLE data for {address}: {e}")


    async def async_start(self) -> None:
        """Start the passive scanner."""
        _LOGGER.info("Starting BLE passive scanner")
        # Ensure data is initialized
        if self.data is None:
            self.data = {}
        # Register the scanner callback
        # Use async_get_advertisement_callback to wrap our handler
        wrapped_callback = async_get_advertisement_callback(self.hass, self._async_handle_bluetooth_event)
        self._scanner_unregister_callback = async_register_scanner(self.hass, wrapped_callback, connectable=False)
        _LOGGER.info("BLE passive scanner started and callback registered.")
        # Trigger an initial update (optional, might be useful for cleanup)
        await self.async_refresh()


    async def async_stop(self) -> None:
        """Stop the passive scanner."""
        _LOGGER.info("Stopping BLE passive scanner")
        if self._scanner_unregister_callback:
            self._scanner_unregister_callback()
            self._scanner_unregister_callback = None
            _LOGGER.info("BLE scanner callback unregistered.")
        # Perform any other cleanup if needed

    async def _async_update_data(self) -> CoordinatorData:
        """Periodically check for and remove stale devices."""
        _LOGGER.debug("Running periodic check for stale BLE devices.")
        now = datetime.now()
        stale_devices = [
            address
            for address, last_seen_time in self._last_seen.items()
            if (now - last_seen_time).total_seconds() > DEVICE_UNAVAILABLE_TIMEOUT
        ]

        updated = False
        if stale_devices:
            _LOGGER.info(f"Removing stale devices: {stale_devices}")
            current_data = self.data or {}
            for address in stale_devices:
                if address in current_data:
                    del current_data[address]
                    updated = True
                if address in self._last_seen:
                    del self._last_seen[address]
            self.data = current_data # Update self.data reference

        # Return the current data (potentially cleaned)
        # If data was changed, listeners will be notified by the coordinator base class
        # if the data object reference itself changed, or if we call async_set_updated_data.
        # Since we modify in place or reassign self.data, returning it should be sufficient.
        _LOGGER.debug(f"Stale device check complete. Current devices: {list(self.data.keys() if self.data else [])}")
        return self.data or {}


    # Keep get_last_seen if sensors need it, data comes from internal tracking now
    def get_last_seen(self, device_address: str) -> Optional[datetime]:
        """Get the last successful update timestamp for a device."""
        return self._last_seen.get(device_address.lower())

    # --- Methods below are removed as they relate to active connections ---
    # _get_device_identifier
    # _find_device
    # _update_single_device
    # _disconnect_device
    # _handle_refresh_interval (base class handles interval now for cleanup)
