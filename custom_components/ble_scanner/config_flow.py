# custom_components/ble_scanner/config_flow.py
"""Config flow for BLE Scanner integration."""
import logging
from typing import Any, Dict, Optional # Keep Dict, Any

import voluptuous as vol
# Remove bleak imports not needed for basic config

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME
# Remove callback as it's not used directly here now
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
# Remove Select Selectors as we won't select device/type here
)

# Use absolute imports consistently
from .const import (
    CONF_DEVICE_ADDRESS,
    CONF_DEVICE_TYPE,
    CONF_POLLING_INTERVAL,
    DEFAULT_POLLING_INTERVAL,
    DOMAIN,
    LOGGER_NAME,
    # SUPPORTED_DEVICE_TYPES, # Remove type selection from config flow
)

_LOGGER = logging.getLogger(LOGGER_NAME)


class BLEScannerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BLE Scanner."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        # No need to store discovered devices or selected address here anymore
        pass

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        # Check if an entry already exists, making this a singleton integration
        # Using DOMAIN as the unique identifier for the single instance
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: Dict[str, str] = {}

        if user_input is not None:
            # User has submitted the configuration (polling interval)
            polling_interval = user_input.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL)
            _LOGGER.debug(f"Creating BLE Scanner entry with polling interval: {polling_interval}")
            return self.async_create_entry(
                title="BLE Scanner", # Fixed title for the single instance
                data={CONF_POLLING_INTERVAL: polling_interval},
            )

        # Show form to configure the integration (just polling interval)
        config_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_POLLING_INTERVAL, default=DEFAULT_POLLING_INTERVAL
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=30, max=3600, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="seconds"
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="user", # Use the user step ID
            data_schema=config_schema,
            errors=errors,
            last_step=True, # Final configuration step before creation
        )

    # Optional: Add Bluetooth discovery step if needed for automatic triggering
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle bluetooth discovery."""
        # This step might need rethinking or removal in the new model.
        # For now, let's just prevent configuration via discovery if already configured.
        address = discovery_info.address
        _LOGGER.debug(f"Discovered device via Bluetooth: {discovery_info.name} ({address})")

        # If the singleton instance is already configured, abort discovery flow.
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        # We might want to trigger the user step instead, but for now,
        # let's prevent auto-configuration via discovery if not already set up.
        # If we wanted discovery to *initiate* the singleton setup, we'd call
        # return await self.async_step_user() here, potentially passing discovery info.
        # However, the current goal is just *one* config entry, usually user-initiated.
        _LOGGER.info("BLE Scanner not configured. Please add it manually via Integrations.")
        return self.async_abort(reason="manual_setup_required")


# Options flow is not needed for this simple singleton configuration
