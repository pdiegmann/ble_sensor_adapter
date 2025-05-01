from typing import Any
from homeassistant import config_entries
# custom_components/ble_scanner/__init__.py
"""The BLE Scanner integration."""
import logging

import voluptuous as vol # Import voluptuous for options schema
from homeassistant.config_entries import ConfigEntry # Removed ConfigEntryState
from homeassistant.const import Platform # Removed CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
# Removed DeviceInfo import
from homeassistant.helpers.selector import ( # Import selectors for options flow
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
from homeassistant.helpers.update_coordinator import UpdateFailed # Removed DataUpdateCoordinator

from .const import DOMAIN, CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL, LOGGER_NAME # Removed CONF_DEVICE_ADDRESS
from .coordinator import BLEScannerCoordinator

_LOGGER = logging.getLogger(LOGGER_NAME)

# Define the platform that this integration will support
PLATFORMS: list[Platform] = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the single BLE Scanner integration instance from a config entry."""
    # Ensure DOMAIN key exists in hass.data
    hass.data.setdefault(DOMAIN, {})
    _LOGGER.info(f"Setting up BLE Scanner integration (Entry ID: {entry.entry_id})")
    _LOGGER.debug(f"Config Entry Data: {entry.data}")
    _LOGGER.debug(f"Config Entry Options: {entry.options}")

    # Create the single coordinator instance for the integration
    # Pass the entry itself; coordinator will extract polling interval etc.
    coordinator = BLEScannerCoordinator(hass, entry)

    # Perform the first refresh (might involve initial BLE scan or setup)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        # Let HA handle retries if the coordinator indicates it's not ready
        _LOGGER.warning("BLE Scanner coordinator not ready, setup will be retried")
        raise
    except UpdateFailed as err:
        # Log specific error but still raise ConfigEntryNotReady
        _LOGGER.error(f"Error during initial BLE Scanner setup: {err}")
        raise ConfigEntryNotReady(f"BLE Scanner setup failed: {err}") from err

    # Store the single coordinator instance
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Start the passive scanner
    await coordinator.async_start()

    # Set up platforms (e.g., sensor) associated with this integration instance
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up options listener to handle changes (e.g., polling interval)
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info("BLE Scanner integration setup complete.")
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the BLE Scanner integration instance."""
    _LOGGER.info(f"Unloading BLE Scanner integration (Entry ID: {entry.entry_id})")

    # Unload platforms associated with this integration instance
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Clean up the single coordinator and its data
        if entry.entry_id in hass.data[DOMAIN]:
             coordinator: BLEScannerCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
             await coordinator.async_stop() # Ensure coordinator stops BLE scanning etc.
             _LOGGER.info("BLE Scanner coordinator stopped and data removed.")
        else:
             _LOGGER.warning(f"Coordinator for BLE Scanner (entry_id: {entry.entry_id}) not found in hass.data during unload.")

    _LOGGER.info(f"BLE Scanner integration unload status: {unload_ok}")
    return unload_ok

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update for the single integration instance."""
    _LOGGER.debug(f"Options updated for BLE Scanner (Entry ID: {entry.entry_id}), reloading entry...")
    # Reload the entry to apply changes (e.g., polling interval)
    # This will trigger async_unload_entry and async_setup_entry
    await hass.config_entries.async_reload(entry.entry_id)
    _LOGGER.debug(f"BLE Scanner entry (Entry ID: {entry.entry_id}) reloaded after options update.")

# Add options flow definition
async def async_get_options_flow(
    config_entry: ConfigEntry,
) -> config_entries.OptionsFlow:
    """Create the options flow."""
    return BLEScannerOptionsFlowHandler(config_entry)


# --- Options Flow Handler ---
# Minimal options flow to adjust polling interval per device
class BLEScannerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle BLE Scanner options for a specific device."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage the options."""
        # This is the entry point for the options flow
        return await self.async_step_device_options()


    async def async_step_device_options(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the options step for the device."""
        errors = {}
        if user_input is not None:
            # Validate interval (optional, selector usually handles it)
            interval = user_input.get(CONF_POLLING_INTERVAL)
            if not (30 <= interval <= 3600):
                 errors["base"] = "invalid_interval" # Use base error key defined in strings.json
            else:
                # Update the options for the config entry
                _LOGGER.debug(f"Updating options for {self.config_entry.title} with: {user_input}")
                return self.async_create_entry(title="", data=user_input)

        # Get current interval from options or data (fallback to default)
        current_interval = self.config_entry.options.get(
            CONF_POLLING_INTERVAL, self.config_entry.data.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL)
        )

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_POLLING_INTERVAL, default=current_interval
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

        # Get device name for title/description
        # Use a generic description placeholder as it applies to the whole integration
        return self.async_show_form(
            step_id="device_options", # Keep step_id for strings.json compatibility if needed
            data_schema=options_schema,
            description_placeholders={"name": "BLE Scanner Integration"}, # Generic name
            errors=errors,
        )
