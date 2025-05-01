"""DataUpdateCoordinator for the BLE Scanner integration using active connections."""
import asyncio
import logging
from datetime import timedelta, datetime
from typing import Any, Dict, Optional, Callable, Set

import async_timeout
import bleak
from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.exc import BleakError

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.debounce import Debouncer
from homeassistant.const import CONF_ADDRESS, CONF_NAME

from custom_components.ble_scanner.const import (
    DOMAIN,
    CONF_DEVICES,
    CONF_DEVICE_NAME,
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_TYPE,
    CONF_POLLING_INTERVAL,
    DEFAULT_POLLING_INTERVAL,
    ATTR_LAST_UPDATED,
    ATTR_RSSI, # Keep RSSI from discovery if possible
    LOGGER_NAME,
)
from custom_components.ble_scanner.errors import DeviceNotFoundError, ParsingError, UnsupportedDeviceTypeError
# Import device-specific active connection handlers (to be created)
from custom_components.ble_scanner.devices import get_device_handler, BaseDeviceHandler


_LOGGER = logging.getLogger(LOGGER_NAME)

# How long to scan for devices if address is unknown (seconds)
DISCOVERY_SCAN_TIMEOUT = 5
# How long to attempt connection (seconds)
CONNECTION_TIMEOUT = 20
# Minimum time between updates enforced by coordinator
MIN_UPDATE_INTERVAL_SECONDS = 30 # Increased minimum due to connection overhead

class BLEScannerCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Class to manage fetching BLE data via active connections."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.config = entry.options
        self._devices_config = self.config.get(CONF_DEVICES, [])
        # Store discovered devices temporarily if needed for address lookup
        self._discovered_devices_cache: Dict[str, BLEDevice] = {}
        self._device_handlers: Dict[str, BaseDeviceHandler] = {}
        self._connection_locks: Dict[str, asyncio.Lock] = {}
        self._device_tasks: Dict[str, asyncio.Task] = {}
        self._stopping = False

        # Determine the shortest polling interval, minimum MIN_UPDATE_INTERVAL_SECONDS
        min_interval = DEFAULT_POLLING_INTERVAL
        if self._devices_config:
            min_interval = min(
                dev.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL)
                for dev in self._devices_config
            )
        update_interval_seconds = max(MIN_UPDATE_INTERVAL_SECONDS, min_interval)
        _LOGGER.info(f"Coordinator update interval set to {update_interval_seconds} seconds")

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval_seconds),
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=5.0, immediate=False
            ),
        )

        # Initialize handlers and locks for each configured device
        for device_conf in self._devices_config:
            device_id = self._get_device_identifier(device_conf)
            device_type = device_conf.get(CONF_DEVICE_TYPE)
            handler_cls = get_device_handler(device_type)
            if handler_cls:
                self._device_handlers[device_id] = handler_cls(hass, device_conf, self.logger)
                self._connection_locks[device_id] = asyncio.Lock()
            else:
                _LOGGER.error(f"No active connection handler found for device type: {device_type} ({device_id})")

    def _get_device_identifier(self, device_conf: Dict[str, Any]) -> str:
        """Get a unique identifier for the device config (address preferred)."""
        # Use address if available, otherwise name. Ensure lowercase.
        addr = device_conf.get(CONF_DEVICE_ADDRESS)
        name = device_conf.get(CONF_DEVICE_NAME)
        if addr:
            return addr.lower()
        elif name:
            return name.lower() # Less ideal, names can clash
        else:
            # Should not happen with config flow, but handle defensively
            return f"unknown_device_{hash(tuple(sorted(device_conf.items())))}"

    async def _find_device(self, address: Optional[str], name: Optional[str]) -> Optional[BLEDevice]:
        """Find a device by address or name using BleakScanner."""
        if address:
            try:
                # Try direct connection first if address is known
                # This might fail if device is not advertising, but worth a try
                # However, BleakClient often needs a BLEDevice object first.
                # So, let's scan briefly.
                _LOGGER.debug(f"Scanning for device with address: {address}")
                device = await bleak.BleakScanner.find_device_by_address(address, timeout=DISCOVERY_SCAN_TIMEOUT)
                if device:
                    _LOGGER.debug(f"Found device by address: {device}")
                    self._discovered_devices_cache[address.lower()] = device # Cache it
                    return device
                else:
                    _LOGGER.debug(f"Device not found by address {address} in scan.")
                    # Check cache from previous scans
                    return self._discovered_devices_cache.get(address.lower())
            except BleakError as e:
                _LOGGER.warning(f"BleakError while scanning for {address}: {e}")
                return None
        elif name:
            _LOGGER.debug(f"Scanning for device with name: {name}")
            try:
                # Scan for devices matching the name
                discovered = await bleak.BleakScanner.discover(timeout=DISCOVERY_SCAN_TIMEOUT)
                for device in discovered:
                    if device.name and device.name.lower() == name.lower():
                        _LOGGER.debug(f"Found device by name: {device}")
                        if device.address:
                             self._discovered_devices_cache[device.address.lower()] = device # Cache it
                        return device
                _LOGGER.debug(f"Device not found by name {name} in scan.")
                return None
            except BleakError as e:
                _LOGGER.warning(f"BleakError while scanning for {name}: {e}")
                return None
        else:
            _LOGGER.error("Cannot find device without address or name.")
            return None

    async def _update_single_device(self, device_id: str, handler: BaseDeviceHandler) -> Optional[Dict[str, Any]]:
        """Connect to and update data for a single device."""
        lock = self._connection_locks.get(device_id)
        if not lock:
            _LOGGER.error(f"No connection lock found for device {device_id}")
            return None

        if lock.locked():
            _LOGGER.debug(f"Update already in progress for {device_id}, skipping.")
            return handler.get_latest_data() # Return last known data

        async with lock:
            _LOGGER.debug(f"Attempting update for device: {device_id}")
            address = handler.config.get(CONF_DEVICE_ADDRESS)
            name = handler.config.get(CONF_DEVICE_NAME)
            ble_device = None

            # 1. Find the BLEDevice object
            # Check cache first
            if address and address.lower() in self._discovered_devices_cache:
                ble_device = self._discovered_devices_cache[address.lower()]
                _LOGGER.debug(f"Using cached BLEDevice for {address}")
            else:
                # If not cached or address unknown, perform discovery
                ble_device = await self._find_device(address, name)

            if not ble_device:
                _LOGGER.warning(f"Could not find device {device_id} (Address: {address}, Name: {name}). Marking unavailable.")
                handler.mark_unavailable()
                return handler.get_latest_data() # Return data (likely marked unavailable)

            # Update address in handler if found by name and address wasn't known
            if not address and ble_device.address:
                 handler.update_address(ble_device.address)
                 # Update main config? No, keep original config, handler knows address now.

            # 2. Connect and Fetch Data using the handler
            try:
                async with async_timeout.timeout(CONNECTION_TIMEOUT):
                    await handler.update(ble_device)
                _LOGGER.debug(f"Successfully updated data for {device_id}")
                return handler.get_latest_data()
            except asyncio.TimeoutError:
                _LOGGER.error(f"Timeout connecting to or fetching data from {device_id} ({ble_device.address})")
                handler.mark_unavailable()
            except BleakError as e:
                _LOGGER.error(f"BleakError for device {device_id} ({ble_device.address}): {e}")
                handler.mark_unavailable()
            except Exception as e:
                _LOGGER.error(f"Unexpected error updating device {device_id} ({ble_device.address}): {e}", exc_info=True)
                handler.mark_unavailable()

            return handler.get_latest_data() # Return data even if update failed (will be marked unavailable)

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from BLE devices by connecting to them."""
        _LOGGER.debug("Starting active connection update cycle")
        start_time = datetime.now()
        all_data = {}

        # Create tasks for each device update
        tasks = []
        for device_id, handler in self._device_handlers.items():
            tasks.append(self._update_single_device(device_id, handler))

        # Run updates concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results
        for i, device_id in enumerate(self._device_handlers.keys()):
            result = results[i]
            if isinstance(result, Exception):
                _LOGGER.error(f"Update task for {device_id} failed with exception: {result}")
                # Keep previous data if available
                if handler := self._device_handlers.get(device_id):
                    all_data[device_id] = handler.get_latest_data()
            elif result is not None:
                all_data[device_id] = result
            else:
                 # Keep previous data if update returned None unexpectedly
                 if handler := self._device_handlers.get(device_id):
                    all_data[device_id] = handler.get_latest_data()

        end_time = datetime.now()
        _LOGGER.debug(f"Active connection update cycle finished in {(end_time - start_time).total_seconds():.2f} seconds. Results: {all_data}")
        return all_data

    async def async_stop(self, *args) -> None:
        """Stop the coordinator and disconnect devices."""
        _LOGGER.info("Stopping BLE Scanner coordinator and disconnecting devices.")
        self._stopping = True
        # Cancel any pending refresh tasks
        self.async_cancel_debounced_refresh() # Use the correct DataUpdateCoordinator method

        # Disconnect all handlers
        disconnect_tasks = []
        for device_id, handler in self._device_handlers.items():
            lock = self._connection_locks.get(device_id)
            if lock:
                 disconnect_tasks.append(self._disconnect_device(device_id, handler, lock))

        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks, return_exceptions=True)

        _LOGGER.info("Coordinator stopped.")

    async def _disconnect_device(self, device_id: str, handler: BaseDeviceHandler, lock: asyncio.Lock):
        """Gracefully disconnect a single device handler."""
        async with lock: # Ensure no update is happening
            try:
                await handler.disconnect()
                _LOGGER.info(f"Disconnected handler for {device_id}")
            except Exception as e:
                _LOGGER.error(f"Error disconnecting handler for {device_id}: {e}")

    # Need to override this to ensure stop is called on shutdown
    async def _handle_refresh_interval(self) -> None:
        """Handle the refresh interval and stop if necessary."""
        if self._stopping:
            return
        await super()._handle_refresh_interval()

    # Keep get_last_seen if sensors need it, data comes from handler now
    def get_last_seen(self, device_id: str) -> Optional[datetime]:
        """Get the last successful update timestamp for a device."""
        handler = self._device_handlers.get(device_id.lower())
        if handler:
            return handler.last_update_time
        return None


