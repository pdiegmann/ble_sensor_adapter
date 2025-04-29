"""Config flow for BLE Scanner integration."""
import logging
import voluptuous as vol
from typing import Any, Dict, Optional

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectOptionDict,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from custom_components.ble_scanner.const import (
    DOMAIN,
    CONF_DEVICES,
    CONF_DEVICE_NAME,
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_TYPE,
    CONF_POLLING_INTERVAL,
    CONF_LOG_LEVEL,
    DEFAULT_POLLING_INTERVAL,
    DEFAULT_LOG_LEVEL,
    SUPPORTED_DEVICE_TYPES,
    LOGGER_NAME,
)

_LOGGER = logging.getLogger(LOGGER_NAME)

# Schema for individual device configuration
DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_DEVICE_NAME): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
    vol.Optional(CONF_DEVICE_ADDRESS): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)), # Optional, user might use name
    vol.Required(CONF_DEVICE_TYPE): SelectSelector(
        SelectSelectorConfig(options=[SelectOptionDict(value=t, label=t) for t in SUPPORTED_DEVICE_TYPES], mode="dropdown")
    ),
    vol.Optional(CONF_POLLING_INTERVAL, default=DEFAULT_POLLING_INTERVAL): NumberSelector(
        NumberSelectorConfig(min=30, max=3600, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="seconds")
    ),
})

# Schema for the main configuration step (log level + devices)
# We'll use options flow for devices later, initial setup just needs log level
CONFIG_SCHEMA = vol.Schema({
    vol.Optional(CONF_LOG_LEVEL, default=DEFAULT_LOG_LEVEL): SelectSelector(
        SelectSelectorConfig(options=["debug", "info", "warning", "error", "critical"], mode="dropdown")
    )
})

class BLEScannerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BLE Scanner."""

    VERSION = 1

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            # Validation could be added here if needed
            # For now, we just create the entry with the log level
            # Devices will be configured via options flow
            return self.async_create_entry(title="BLE Scanner", data=user_input, options={CONF_DEVICES: []})

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return BLEScannerOptionsFlowHandler(config_entry)


class BLEScannerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle BLE Scanner options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        # Combine existing data and options for editing
        self.current_config = dict(config_entry.data)
        self.current_config.update(config_entry.options)
        self.devices = self.current_config.get(CONF_DEVICES, [])

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["configure_global", "configure_devices"],
        )

    async def async_step_configure_global(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle global settings."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Update only the global settings, keep devices
            updated_options = {**self.config_entry.options, **user_input}
            _LOGGER.debug(f"Updating global options to: {updated_options}")
            return self.async_create_entry(title="", data=updated_options)

        global_schema = vol.Schema({
            vol.Optional(CONF_LOG_LEVEL, default=self.current_config.get(CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL)): SelectSelector(
                SelectSelectorConfig(options=["debug", "info", "warning", "error", "critical"], mode="dropdown")
            )
        })

        return self.async_show_form(
            step_id="configure_global", data_schema=global_schema, errors=errors
        )

    async def async_step_configure_devices(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Show current devices and allow adding/removing."""
        return self.async_show_menu(
            step_id="configure_devices",
            menu_options=["add_device", "remove_device"],
            description_placeholders={"devices_list": self._get_devices_list_str()}
        )

    def _get_devices_list_str(self) -> str:
        """Format device list for display."""
        if not self.devices:
            return "No devices configured."
        lines = []
        for i, device in enumerate(self.devices):
            identifier = device.get(CONF_DEVICE_ADDRESS, device.get(CONF_DEVICE_NAME, 'Unknown'))
            lines.append(f"{i + 1}. {device.get(CONF_DEVICE_NAME, 'Unnamed')} ({identifier}) - Type: {device.get(CONF_DEVICE_TYPE)}, Interval: {device.get(CONF_POLLING_INTERVAL)}s")
        return "\n".join(lines)

    async def async_step_add_device(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle adding a new device."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Basic validation: Ensure name or address is provided
            if not user_input.get(CONF_DEVICE_NAME) and not user_input.get(CONF_DEVICE_ADDRESS):
                errors["base"] = "name_or_address_required"
            else:
                self.devices.append(user_input)
                updated_options = {**self.config_entry.options, CONF_DEVICES: self.devices}
                _LOGGER.debug(f"Adding device, updated options: {updated_options}")
                return self.async_create_entry(title="", data=updated_options)

        return self.async_show_form(
            step_id="add_device", data_schema=DEVICE_SCHEMA, errors=errors
        )

    async def async_step_remove_device(self, user_input: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle removing a device."""
        errors: Dict[str, str] = {}

        if not self.devices:
             return self.async_abort(reason="no_devices_to_remove")

        device_options = {
            str(i): f"{dev.get(CONF_DEVICE_NAME, 'Unnamed')} ({dev.get(CONF_DEVICE_ADDRESS, dev.get(CONF_DEVICE_NAME))})"
            for i, dev in enumerate(self.devices)
        }

        if user_input is not None:
            try:
                selected_index = int(user_input["device_to_remove"])
                if 0 <= selected_index < len(self.devices):
                    removed_device = self.devices.pop(selected_index)
                    _LOGGER.debug(f"Removed device: {removed_device}")
                    updated_options = {**self.config_entry.options, CONF_DEVICES: self.devices}
                    return self.async_create_entry(title="", data=updated_options)
                else:
                    errors["base"] = "invalid_selection"
            except (ValueError, KeyError):
                errors["base"] = "invalid_selection"

        remove_schema = vol.Schema({
            vol.Required("device_to_remove"): SelectSelector(SelectSelectorConfig(options=list(device_options.items()), mode="dropdown"))
        })

        return self.async_show_form(
            step_id="remove_device", data_schema=remove_schema, errors=errors
        )

