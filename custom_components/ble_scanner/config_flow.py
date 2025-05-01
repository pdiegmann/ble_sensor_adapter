# custom_components/ble_scanner/config_flow.py
"""Config flow for BLE Scanner integration."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info, # Keep for potential future use?
)
from homeassistant.const import CONF_ADDRESS # Keep CONF_ADDRESS
# No CONF_NAME needed here
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SelectOptionDict,
)
import homeassistant.helpers.device_registry as dr # Import device registry helper


# Use absolute imports consistently
from custom_components.ble_scanner.const import (
    CONF_DEVICE_ADDRESS, # Keep this
    # CONF_DEVICE_TYPE, # Remove type selection
    # CONF_POLLING_INTERVAL, # Remove polling interval
    # DEFAULT_POLLING_INTERVAL, # Remove polling interval
    DOMAIN,
    LOGGER_NAME,
)

_LOGGER = logging.getLogger(LOGGER_NAME)


class BLEScannerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BLE Scanner."""

    VERSION = 1

    # Remove __init__ as it's not needed

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step: discover and select a device."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_DEVICE_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            # Retrieve device name for title (best effort)
            # Note: This relies on the device still being discoverable at this exact moment,
            # which might not always be true. Consider storing discovered names temporarily.
            title = address
            try:
                # Use async_scanner_devices which returns BLEDevice objects
                scanner_devices = bluetooth.async_scanner_devices(self.hass, True)
                for device in scanner_devices:
                    if device.address == address:
                        title = device.name or address # Use name if available
                        break
            except Exception as e:
                _LOGGER.warning(f"Could not retrieve device name for {address}: {e}")


            _LOGGER.debug(f"Creating BLE Scanner entry for device: {title} ({address})")
            return self.async_create_entry(
                title=title,
                data={CONF_DEVICE_ADDRESS: address},
            )

        # Discover available devices not already configured
        discovered_devices = bluetooth.async_scanner_devices(self.hass, connectable=True)
        configured_addresses = {
            entry.unique_id for entry in self._async_current_entries()
        }

        available_devices = []
        for device in discovered_devices:
            if device.address not in configured_addresses:
                 # Use device name if available, otherwise address
                label = f"{device.name or 'Unknown Device'} ({dr.format_mac(device.address)})"
                available_devices.append(
                    SelectOptionDict(value=device.address, label=label)
                )

        if not available_devices:
            # TODO: Add "no_devices_found" to strings.json
            errors["base"] = "no_devices_found"
            # Consider adding a manual entry option here or in a separate step
            # For now, show error if no devices discovered/available
            return self.async_show_form(step_id="user", errors=errors, last_step=True)


        # Sort devices by label for better UX
        available_devices.sort(key=lambda x: x["label"])

        # Show form to select the device
        data_schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_ADDRESS): SelectSelector(
                    SelectSelectorConfig(
                        options=available_devices,
                        mode=SelectSelectorMode.DROPDOWN,
                        # custom_value=True # Consider adding for manual entry later
                        # translation_key="device_select" # Consider adding for i18n
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            # Not the last step if we add confirmation or options later
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle bluetooth discovery."""
        address = discovery_info.address
        _LOGGER.debug(f"Discovered device via Bluetooth: {discovery_info.name} ({address})")

        # Set unique ID based on discovered address to check if already configured
        await self.async_set_unique_id(address, raise_on_progress=False)
        # Abort if this specific device is already configured
        self._abort_if_unique_id_configured(updates={CONF_ADDRESS: address})

        # Discovery is not used to initiate configuration flow for this integration.
        # User must manually add the integration.
        # TODO: Add "discovery_not_used" to strings.json
        return self.async_abort(reason="discovery_not_used")

# No options flow needed currently
