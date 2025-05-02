"""Config flow for BLE Sensor integration."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from custom_components.ble_sensor.utils.const import (
    CONF_DEVICE_TYPE,
    CONF_MAC,
    CONF_POLL_INTERVAL,
    CONF_RETRY_COUNT,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_RETRY_COUNT,
    DEVICE_TYPES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Validation schema for config flow
CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC): str,
        vol.Required(CONF_DEVICE_TYPE): vol.In(DEVICE_TYPES),
    }
)

# Validation schema for options flow
OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL
        ): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600)),
        vol.Optional(
            CONF_RETRY_COUNT, default=DEFAULT_RETRY_COUNT
        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
    }
)

class BLESensorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BLE Sensor integration."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: Dict[str, BluetoothServiceInfoBleak] = {}
        self._discovered_device: Optional[BluetoothServiceInfoBleak] = None

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            mac = user_input[CONF_MAC].lower()
            
            # Validate MAC address
            if not self._is_valid_mac(mac):
                errors[CONF_MAC] = "invalid_mac"
            else:
                # Check if device already configured
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()
                
                # Setup the config entry
                return self.async_create_entry(
                    title=f"{DEVICE_TYPES[user_input[CONF_DEVICE_TYPE]]} ({mac})",
                    data={
                        CONF_MAC: mac,
                        CONF_DEVICE_TYPE: user_input[CONF_DEVICE_TYPE],
                    },
                )
        
        # Return form with discovered devices
        return self.async_show_form(
            step_id="user",
            data_schema=self._get_user_form_schema(),
            errors=errors,
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle bluetooth discovery."""
        _LOGGER.debug("Discovered BLE device: %s", discovery_info.address)
        
        # Check if device already configured
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        
        # Store the device info
        self._discovered_device = discovery_info
        
        # Create context with device name
        self.context["title_placeholders"] = {
            "name": discovery_info.name or discovery_info.address
        }
        
        # Start the flow
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Confirm bluetooth discovery."""
        if user_input is None:
            return self.async_show_form(
                step_id="bluetooth_confirm",
                description_placeholders={
                    "name": self._discovered_device.name
                    or self._discovered_device.address
                },
            )

        # Get device type
        return await self.async_step_device_type()

    async def async_step_device_type(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Select device type."""
        if user_input is None:
            return self.async_show_form(
                step_id="device_type",
                data_schema=vol.Schema(
                    {vol.Required(CONF_DEVICE_TYPE): vol.In(DEVICE_TYPES)}
                ),
                description_placeholders={
                    "name": self._discovered_device.name
                    or self._discovered_device.address
                },
            )
            
        # Create entry
        mac = self._discovered_device.address.lower()
        device_type = user_input[CONF_DEVICE_TYPE]
        
        return self.async_create_entry(
            title=f"{DEVICE_TYPES[device_type]} ({mac})",
            data={
                CONF_MAC: mac,
                CONF_DEVICE_TYPE: device_type,
            },
        )

    @staticmethod
    def _is_valid_mac(mac: str) -> bool:
        """Check if mac address is valid."""
        return bool(re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", mac))

    def _get_user_form_schema(self) -> vol.Schema:
        """Return schema for the user form."""
        discovered_devices = {
            info.address: f"{info.name} ({info.address})"
            for info in async_discovered_service_info(self.hass)
            if info.connectable
        }
        
        if discovered_devices:
            schema = vol.Schema(
                {
                    vol.Required(CONF_MAC): vol.In(discovered_devices),
                    vol.Required(CONF_DEVICE_TYPE): vol.In(DEVICE_TYPES),
                }
            )
        else:
            schema = CONFIG_SCHEMA
            
        return schema

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BLESensorOptionsFlow:
        """Get the options flow for this handler."""
        return BLESensorOptionsFlow(config_entry)


class BLESensorOptionsFlow(config_entries.OptionsFlow):
    """Handle BLE Sensor options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry  # Store as instance variable, don't override self.config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
            
        # Fill with current values
        options = {
            CONF_POLL_INTERVAL: self._config_entry.options.get(
                CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
            ),
            CONF_RETRY_COUNT: self._config_entry.options.get(
                CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT
            ),
        }
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_POLL_INTERVAL,
                        default=options[CONF_POLL_INTERVAL],
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600)),
                    vol.Optional(
                        CONF_RETRY_COUNT,
                        default=options[CONF_RETRY_COUNT],
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                }
            ),
        )