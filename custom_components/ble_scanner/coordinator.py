"""DataUpdateCoordinator for the BLE Scanner integration using active connections."""
import logging
from datetime import timedelta, datetime
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS # Standard constant for MAC address

# Import Bleak components
from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice

from custom_components.ble_scanner.const import (
    DEVICE_TYPE_PETKIT_FOUNTAIN,
    DOMAIN,
    CONF_POLLING_INTERVAL,
    DEFAULT_POLLING_INTERVAL,
    ATTR_LAST_UPDATED,
    ATTR_RSSI,
    LOGGER_NAME,
    CONF_DEVICE_ADDRESS, # Specific constant used in config flow
    CONF_DEVICE_TYPE, # Constant for device type identification
)
# Import base handler and factory function (assuming it exists)
# Ensure this path is correct and get_device_handler exists
from custom_components.ble_scanner.devices import HANDLER_MAP, BaseDeviceHandler, get_device_handler


_LOGGER = logging.getLogger(LOGGER_NAME)

# Type hint for the data returned by the coordinator (data for a single device)
CoordinatorData = Dict[str, Any]


class BleScannerCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Class to manage fetching data from a specific BLE device."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.entry = entry
        self._device_address = entry.data[CONF_DEVICE_ADDRESS].lower() # Store device MAC
        self._device_type = entry.data.get(CONF_DEVICE_TYPE) # Store device type

        # Get polling interval from config entry, default if not set
        polling_interval_seconds = entry.options.get(
            CONF_POLLING_INTERVAL,
            entry.data.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL)
        )
        # Ensure a minimum polling interval (e.g., 15 seconds)
        update_interval = timedelta(seconds=max(15, polling_interval_seconds))

        # Instantiate the appropriate device handler
        # This assumes get_device_handler exists and returns a BaseDeviceHandler instance
        # based on entry.data (which should contain type and potentially other config)
        try:
            # Pass the specific device config part of the entry data if needed
            # Assuming entry.data contains necessary info like type, name, address
            device_config = entry.data
            _LOGGER.debug(f"HANDLER_MAP keys: {list(HANDLER_MAP.keys())}")
            _LOGGER.debug(f"self._device_type value: {self._device_type!r}")
            _LOGGER.debug(f"device_config type: {type(device_config)}, value: {device_config}")
            _LOGGER.debug(f"self._device_type type: {type(self._device_type)}, value: {self._device_type}")
            handler_class = get_device_handler(self._device_type) # Get the class
            if handler_class:
                try:
                    # Instantiate the handler class - assuming all handlers now take (config, logger)
                    self._device_handler: BaseDeviceHandler = handler_class(device_config, _LOGGER)

                    # Use device name from handler instance if available, otherwise address
                    coordinator_name = f"{DOMAIN} {self._device_handler.name or self._device_address}"
                    _LOGGER.debug(f"Successfully instantiated handler: {type(self._device_handler).__name__}")

                except Exception as init_err:
                    _LOGGER.error(f"Failed to instantiate handler {handler_class.__name__} for {self._device_type} ({self._device_address}): {init_err}", exc_info=True)
                    self._device_handler = None # Indicate handler is missing due to init error
                    coordinator_name = f"{DOMAIN} {self._device_address} (Handler Init Error)"

            else:
                # Handler class not found by get_device_handler
                _LOGGER.error(f"Device handler class not found for type {self._device_type} ({self._device_address})")
                self._device_handler = None # Indicate handler is missing
                coordinator_name = f"{DOMAIN} {self._device_address} (Handler Class Not Found)"

        except ImportError:
             _LOGGER.error(f"Device handler module not found for type {self._device_type} ({self._device_address})", exc_info=True)
             self._device_handler = None # Indicate handler is missing
             coordinator_name = f"{DOMAIN} {self._device_address} (Handler Module Error)"
        except Exception as e:
            # Catch other potential errors during the process
            _LOGGER.error(f"Unexpected error setting up device handler for {self._device_type} ({self._device_address}): {e}", exc_info=True)
            self._device_handler = None # Indicate handler is missing
            coordinator_name = f"{DOMAIN} {self._device_address} (Handler Setup Error)"

        super().__init__(
            hass,
            _LOGGER,
            name=coordinator_name,
            update_interval=update_interval,
        )
        _LOGGER.info(
            f"Initialized BLE Coordinator for {self.name} with update interval {update_interval}"
        )
        # Add listener for config entry option changes (e.g., polling interval)
        entry.add_update_listener(self._async_options_updated)


    @staticmethod
    async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Handle options update."""
        # This is called by HA when options are saved.
        # We need to find the coordinator instance and update its interval.
        # This assumes the coordinator is stored in hass.data
        coordinator_key = f"{DOMAIN}_{entry.entry_id}"
        if coordinator_key in hass.data:
            coordinator: BleScannerCoordinator = hass.data[coordinator_key]
            _LOGGER.debug(f"[{coordinator.name}] Options updated, reconfiguring interval.")
            new_polling_interval = entry.options.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL)
            new_update_interval = timedelta(seconds=max(15, new_polling_interval))
            coordinator.update_interval = new_update_interval
            _LOGGER.info(f"[{coordinator.name}] Update interval changed to {new_update_interval}")
            # Optionally trigger a refresh immediately
            # await coordinator.async_request_refresh()
        else:
             _LOGGER.warning(f"Coordinator for entry {entry.entry_id} not found during options update.")


    async def _async_update_data(self) -> CoordinatorData:
        """Fetch data from the BLE device."""
        if not self._device_handler:
            _LOGGER.error(f"[{self.name}] Device handler not available, cannot update.")
            raise UpdateFailed("Device handler not initialized.")

        _LOGGER.debug(f"[{self.name}] Attempting to fetch data")

        _LOGGER.info(f"[{self.name}] Starting update cycle for {self._device_address}") # Added log
        # 1. Get BLEDevice
        _LOGGER.debug(f"[{self.name}] Searching for BLE device with address: {self._device_address}") # Added log
        ble_device: BLEDevice | None = bluetooth.async_ble_device_from_address(
            self.hass, self._device_address, connectable=True
        )
        if not ble_device:
            _LOGGER.warning(f"[{self.name}] Device {self._device_address} not found or not connectable. Will retry.")
            _LOGGER.error(f"[{self.name}] BLE device {self._device_address} not found by bluetooth.async_ble_device_from_address. Is it in range and powered on?") # Added log
            # Return previous data if available, otherwise None to indicate no update
            return self.data if self.data else None

        # 2. Connect and Fetch Data
        _LOGGER.debug(f"[{self.name}] Found BLE device: {ble_device.name} ({ble_device.address}). Attempting connection...") # Added log
        client = BleakClient(ble_device)
        try:
            # Set a reasonable timeout for the connection attempt
            async with client: # Default connect timeout is often long, manage explicitly if needed
                if not client.is_connected:
                    _LOGGER.warning(f"[{self.name}] Failed to connect.")
                    raise UpdateFailed(f"Failed to connect to {self._device_address}")
                _LOGGER.info(f"[{self.name}] Successfully connected to {ble_device.address}. Preparing to fetch data.") # Added log

                _LOGGER.debug(f"[{self.name}] Connected. Fetching data...")
                # Call the device-specific fetch logic
                fetched_data = await self._device_handler.async_fetch_data(client)

                # Add metadata
                fetched_data[ATTR_LAST_UPDATED] = datetime.now().isoformat()
                # Get RSSI from the discovered device object
                if hasattr(ble_device, "rssi") and ble_device.rssi is not None:
                     fetched_data[ATTR_RSSI] = ble_device.rssi
                # Don't try to get RSSI from active connection, rely on discovery

                _LOGGER.debug(f"[{self.name}] Data fetched successfully: {fetched_data}")
                return fetched_data

        except (BleakError, TimeoutError) as err:
            # Log specific connection/communication errors as warnings and retry
            _LOGGER.warning(f"[{self.name}] Connection/communication error: {err}. Will retry.")
            _LOGGER.error(f"[{self.name}] Caught BleakError/TimeoutError during update: {err}", exc_info=True) # Added log
            # Return previous data if available, otherwise None to indicate no update
            return self.data if self.data else None
        except Exception as err:
            # Log other unexpected errors and fail the update
            _LOGGER.exception(f"[{self.name}] Unexpected error during update: {err}")
            _LOGGER.critical(f"[{self.name}] Caught UNEXPECTED Exception during update: {err}", exc_info=True) # Added log
            raise UpdateFailed(f"Unexpected error: {err}") from err
        # No finally block needed here, 'async with client' handles disconnection

    # No other methods needed (async_start, async_stop, _async_handle_bluetooth_event, get_last_seen are removed)
