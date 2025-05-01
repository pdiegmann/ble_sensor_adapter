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
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_TYPE,
    SUPPORTED_DEVICE_TYPES,
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

        # Discover available devices not already configured
        discovered_devices = bluetooth.async_get_scanner(self.hass).discovered_devices
        configured_addresses = {
            entry.unique_id for entry in self._async_current_entries()
        }

        available_devices = []
        for device in discovered_devices:
            if device.address not in configured_addresses:
                label = f"{device.name or 'Unknown Device'} ({dr.format_mac(device.address)})"
                available_devices.append(
                    SelectOptionDict(value=device.address, label=label)
                )

        device_type_options = [
            SelectOptionDict(value=dt, label=dt.replace("-", " ").title())
            for dt in SUPPORTED_DEVICE_TYPES
        ]
        _LOGGER.debug(f"Device type options: {device_type_options}")

        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICE_ADDRESS): vol.In([d.value for d in available_devices]),
                vol.Required(CONF_DEVICE_TYPE): vol.In([d.value for d in device_type_options]),
            }
        )

        if user_input is not None:
            _LOGGER.debug(f"User input received: {user_input}")
            address = user_input[CONF_DEVICE_ADDRESS]
            device_type = user_input[CONF_DEVICE_TYPE]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            # Retrieve device name for title (best effort)
            title = address
            try:
                scanner_devices = bluetooth.async_get_scanner(self.hass).discovered_devices
                for device in scanner_devices:
                    if device.address == address:
                        title = device.name or address
                        break
            except Exception as e:
                _LOGGER.warning(f"Could not retrieve device name for {address}: {e}")

            entry_data = {
                CONF_DEVICE_ADDRESS: address,
                CONF_DEVICE_TYPE: device_type,
            }
            _LOGGER.debug(f"Creating BLE Scanner entry for device: {title} ({address}), entry_data: {entry_data}")
            return self.async_create_entry(
                title=title,
                data=entry_data,
            )

        if not available_devices:
            errors["base"] = "no_devices_found"
            return self.async_show_form(step_id="user", errors=errors, last_step=True)

        if not device_type_options:
            errors["base"] = "no_device_types"
            return self.async_show_form(step_id="user", errors=errors, last_step=True)

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )


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
