"""Config flow for BLE Scanner integration."""
import logging
import voluptuous as vol
from typing import Any, Dict, Optional, List

from homeassistant import config_entries
from homeassistant.core import callback
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

# Use absolute imports consistently
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

# --- Schemas --- #

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_DEVICE_NAME): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
    vol.Optional(CONF_DEVICE_ADDRESS): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
    vol.Required(CONF_DEVICE_TYPE): SelectSelector(
        SelectSelectorConfig(options=[SelectOptionDict(value=t, label=t) for t in SUPPORTED_DEVICE_TYPES], mode="dropdown")
    ),
    vol.Optional(CONF_POLLING_INTERVAL, default=DEFAULT_POLLING_INTERVAL): NumberSelector(
        NumberSelectorConfig(min=30, max=3600, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="seconds")
    ),
})

LOG_LEVEL_SCHEMA = vol.Schema({
    vol.Optional(CONF_LOG_LEVEL, default=DEFAULT_LOG_LEVEL): SelectSelector(
        SelectSelectorConfig(options=["debug", "info", "warning", "error", "critical"], mode="dropdown")
    )
})

# --- Main Config Flow --- #

class BLEScannerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BLE Scanner."""

    VERSION = 1

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> config_entries.FlowResult:
        """Handle the initial setup step (only log level)."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            # Store log level in data, devices will be in options
            return self.async_create_entry(title="BLE Scanner", data=user_input, options={CONF_DEVICES: []})

        return self.async_show_form(
            step_id="user", data_schema=LOG_LEVEL_SCHEMA
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "BLEScannerOptionsFlowHandler":
        """Get the options flow for this handler."""
        return BLEScannerOptionsFlowHandler(config_entry)

# --- Options Flow --- #

class BLEScannerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle BLE Scanner options (Log Level and Devices)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        # Options contain both log_level and devices list
        self.options = dict(config_entry.options)
        # Ensure devices list exists
        if CONF_DEVICES not in self.options:
            self.options[CONF_DEVICES] = []
        self.devices = self.options[CONF_DEVICES]

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> config_entries.FlowResult:
        """Manage the main options menu (Global Settings or Device Management)."""
        # Streamlined menu
        return self.async_show_menu(
            step_id="init",
            menu_options=["modify_log_level", "manage_devices"],
        )

    async def async_step_modify_log_level(self, user_input: Optional[Dict[str, Any]] = None) -> config_entries.FlowResult:
        """Handle modification of the log level."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Update only the log level in options
            self.options[CONF_LOG_LEVEL] = user_input[CONF_LOG_LEVEL]
            _LOGGER.debug(f"Updating log level option to: {self.options[CONF_LOG_LEVEL]}")
            # Create entry with updated options
            return self.async_create_entry(title="", data=self.options)

        # Use the schema defined earlier, pre-filling with current value
        log_level_schema = vol.Schema({
            vol.Optional(CONF_LOG_LEVEL, default=self.options.get(CONF_LOG_LEVEL, DEFAULT_LOG_LEVEL)): SelectSelector(
                SelectSelectorConfig(options=["debug", "info", "warning", "error", "critical"], mode="dropdown")
            )
        })

        return self.async_show_form(
            step_id="modify_log_level", data_schema=log_level_schema, errors=errors
        )

    async def async_step_manage_devices(self, user_input: Optional[Dict[str, Any]] = None) -> config_entries.FlowResult:
        """Show device list and offer actions (Add/Remove)."""
        # This step now acts as the device management hub
        return self.async_show_menu(
            step_id="manage_devices",
            menu_options=["add_device", "remove_device"],
            description_placeholders={"devices_list": self._get_devices_list_str()}
        )

    def _get_devices_list_str(self) -> str:
        """Format device list for display."""
        if not self.devices:
            return "No devices configured."
        lines = []
        for i, device in enumerate(self.devices):
            # Use a consistent identifier (address if available, else name)
            identifier = device.get(CONF_DEVICE_ADDRESS)
            if not identifier:
                 identifier = f"Name: {device.get(CONF_DEVICE_NAME, 'Unknown')}"
            else:
                 identifier = f"Address: {identifier}"

            lines.append(
                f"{i + 1}. {device.get(CONF_DEVICE_NAME, 'Unnamed')} ({identifier}) - "
                f"Type: {device.get(CONF_DEVICE_TYPE)}, Interval: {device.get(CONF_POLLING_INTERVAL)}s"
            )
        return "\n".join(lines)

    async def async_step_add_device(self, user_input: Optional[Dict[str, Any]] = None) -> config_entries.FlowResult:
        """Handle adding a new device."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Basic validation: Ensure name or address is provided
            if not user_input.get(CONF_DEVICE_NAME) and not user_input.get(CONF_DEVICE_ADDRESS):
                errors["base"] = "name_or_address_required"
            # Ensure address is unique if provided
            elif user_input.get(CONF_DEVICE_ADDRESS) and any(
                d.get(CONF_DEVICE_ADDRESS) == user_input.get(CONF_DEVICE_ADDRESS)
                for d in self.devices
            ):
                 errors[CONF_DEVICE_ADDRESS] = "address_already_configured"
            # Ensure name is unique if address is not provided
            elif not user_input.get(CONF_DEVICE_ADDRESS) and any(
                d.get(CONF_DEVICE_NAME) == user_input.get(CONF_DEVICE_NAME) and not d.get(CONF_DEVICE_ADDRESS)
                for d in self.devices
            ):
                 errors[CONF_DEVICE_NAME] = "name_must_be_unique_without_address"
            else:
                self.devices.append(user_input)
                self.options[CONF_DEVICES] = self.devices # Update the list in options
                _LOGGER.debug(f"Adding device, updated options: {self.options}")
                # Create entry with updated options
                return self.async_create_entry(title="", data=self.options)

        return self.async_show_form(
            step_id="add_device", data_schema=DEVICE_SCHEMA, errors=errors
        )

    async def async_step_remove_device(self, user_input: Optional[Dict[str, Any]] = None) -> config_entries.FlowResult:
        """Handle removing a device."""
        errors: Dict[str, str] = {}

        if not self.devices:
             # Show message and return to manage_devices menu
             return self.async_show_menu(
                 step_id="manage_devices",
                 menu_options=["add_device"], # Only show add if list is empty
                 description_placeholders={"devices_list": "No devices configured to remove."}
             )

        # Create options for the selector using index as key
        device_options = [
            SelectOptionDict(value=str(i), label=f"{dev.get(CONF_DEVICE_NAME, 'Unnamed')} ({dev.get(CONF_DEVICE_ADDRESS, dev.get(CONF_DEVICE_NAME))})")
            for i, dev in enumerate(self.devices)
        ]

        if user_input is not None:
            try:
                selected_index = int(user_input["device_to_remove"])
                if 0 <= selected_index < len(self.devices):
                    removed_device = self.devices.pop(selected_index)
                    _LOGGER.debug(f"Removed device: {removed_device}")
                    self.options[CONF_DEVICES] = self.devices # Update the list in options
                    # Create entry with updated options
                    return self.async_create_entry(title="", data=self.options)
                else:
                    errors["base"] = "invalid_selection"
            except (ValueError, KeyError):
                errors["base"] = "invalid_selection"

        remove_schema = vol.Schema({
            vol.Required("device_to_remove"): SelectSelector(SelectSelectorConfig(options=device_options, mode="dropdown"))
        })

        return self.async_show_form(
            step_id="remove_device", data_schema=remove_schema, errors=errors
        )

