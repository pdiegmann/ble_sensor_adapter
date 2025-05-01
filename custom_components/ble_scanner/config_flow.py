# custom_components/ble_scanner/config_flow.py
"""Config flow for BLE Scanner integration."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

# Use absolute imports consistently
from .const import (
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_TYPE,
    CONF_POLLING_INTERVAL,
    DEFAULT_POLLING_INTERVAL,
    DOMAIN,
    LOGGER_NAME,
    SUPPORTED_DEVICE_TYPES,
)

_LOGGER = logging.getLogger(LOGGER_NAME)


class BLEScannerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BLE Scanner."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: Dict[str, BluetoothServiceInfoBleak] = {}
        self._selected_address: Optional[str] = None

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        # This flow is initiated by the user clicking "Add Integration"
        # We start discovery here.
        _LOGGER.debug("Starting user step, initiating BLE discovery")
        self._discovered_devices.clear()
        # Use connectable=True to potentially filter for devices we can interact with
        for service_info in async_discovered_service_info(self.hass, connectable=True):
            # Filter out devices without a name for user selection clarity
            # You might add more sophisticated filtering based on service UUIDs etc.
            # if service_info.name: # Keep devices even without name for now
            self._discovered_devices[service_info.address] = service_info
            _LOGGER.debug(f"Discovered connectable: {service_info.name} ({service_info.address})")

        if not self._discovered_devices:
            _LOGGER.warning("No connectable BLE devices found during initial scan.")
            # Also check non-connectable devices for broader discovery, might be needed for passive scanning
            _LOGGER.debug("Checking non-connectable devices...")
            for service_info in async_discovered_service_info(self.hass, connectable=False):
                 if service_info.address not in self._discovered_devices:
                    self._discovered_devices[service_info.address] = service_info
                    _LOGGER.debug(f"Discovered non-connectable: {service_info.name} ({service_info.address})")

        if not self._discovered_devices:
             _LOGGER.error("No BLE devices found during scan (connectable or non-connectable).")
             return self.async_abort(reason="no_devices_found")


        # If discovery yields results, proceed to device selection
        return await self.async_step_select_device()

    async def async_step_select_device(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle device selection step."""
        if user_input is not None:
            self._selected_address = user_input[CONF_DEVICE_ADDRESS]
            _LOGGER.debug(f"User selected device address: {self._selected_address}")

            # Abort if this device (by MAC address) is already configured
            await self.async_set_unique_id(self._selected_address)
            self._abort_if_unique_id_configured()

            return await self.async_step_device_config()

        # Prepare device list for selection
        discovered_devices_options = [
            SelectOptionDict(
                value=address,
                # Use name if available, otherwise address
                label=f"{service_info.name or 'Unknown Name'} ({address})",
            )
            for address, service_info in self._discovered_devices.items()
        ]

        # Sort options by label (name or address)
        discovered_devices_options.sort(key=lambda x: x["label"])


        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ADDRESS): SelectSelector(
                        SelectSelectorConfig(
                            options=discovered_devices_options, mode="dropdown"
                        )
                    )
                }
            ),
            description_placeholders={
                "devices_count": len(discovered_devices_options)
            },
            last_step=False, # Indicate there are more steps
        )

    async def async_step_device_config(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle device configuration step (type, interval)."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Combine selected address with user input for type/interval
            device_data = {
                CONF_DEVICE_ADDRESS: self._selected_address,
                CONF_DEVICE_TYPE: user_input[CONF_DEVICE_TYPE],
                CONF_POLLING_INTERVAL: user_input[CONF_POLLING_INTERVAL],
            }
            _LOGGER.debug(f"Creating config entry with data: {device_data}")

            # Get device name from discovery results for the title
            device_info = self._discovered_devices.get(self._selected_address)
            # Use discovered name, fallback to type + address if no name
            title = device_info.name if device_info and device_info.name else f"{user_input[CONF_DEVICE_TYPE]} {self._selected_address}"

            return self.async_create_entry(title=title, data=device_data)

        # Schema for device type and polling interval
        device_config_schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_TYPE): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=t, label=t)
                            for t in SUPPORTED_DEVICE_TYPES
                        ],
                        mode="dropdown",
                    )
                ),
                vol.Optional(
                    CONF_POLLING_INTERVAL, default=DEFAULT_POLLING_INTERVAL
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=30,
                        max=3600,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="seconds",
                    )
                ),
            }
        )

        device_info = self._discovered_devices.get(self._selected_address)
        device_name = device_info.name if device_info and device_info.name else "Unknown Device"

        return self.async_show_form(
            step_id="device_config",
            data_schema=device_config_schema,
            description_placeholders={
                CONF_NAME: device_name,
                CONF_ADDRESS: self._selected_address,
            },
            errors=errors,
            last_step=True, # Final configuration step before creation
        )

    # Optional: Add Bluetooth discovery step if needed for automatic triggering
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle bluetooth discovery."""
        address = discovery_info.address
        _LOGGER.debug(f"Discovered device via Bluetooth: {discovery_info.name} ({address})")

        await self.async_set_unique_id(address)
        # Use CONF_ADDRESS consistently
        self._abort_if_unique_id_configured(updates={CONF_ADDRESS: address})

        # Check if device type is supported based on discovery (if possible)
        # This part is highly dependent on how devices advertise themselves
        # Example: if "Petkit" in discovery_info.name:
        #    supported = True # Or check service UUIDs etc.
        # else:
        #    supported = False
        # if not supported:
        #    return self.async_abort(reason="unsupported_device")

        # Store discovery info for later steps
        self._discovered_devices[address] = discovery_info
        self._selected_address = address

        # Directly proceed to device configuration step
        # Context allows skipping selection if triggered by discovery
        self.context["title_placeholders"] = {"name": discovery_info.name or address} # Use address if name is missing
        return await self.async_step_device_config()

# Remove the old Options Flow Handler as it's replaced by per-device config entries
# class BLEScannerOptionsFlowHandler(config_entries.OptionsFlow):
#    ... (Old code removed) ...
