# custom_components/ble_scanner/__init__.py
"""The BLE Scanner integration."""
import asyncio
import logging

import voluptuous as vol # Import voluptuous for options schema
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.selector import ( # Import selectors for options flow
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, CONF_DEVICE_ADDRESS, CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL, LOGGER_NAME # Adjusted imports
from .coordinator import BLEScannerCoordinator

_LOGGER = logging.getLogger(LOGGER_NAME)

# Define the platform that this integration will support
PLATFORMS: list[Platform] = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BLE Scanner from a config entry (represents a single device)."""
    hass.data.setdefault(DOMAIN, {})
    address = entry.data[CONF_DEVICE_ADDRESS] # Get address from data
    _LOGGER.info(f"Setting up BLE Scanner for device: {address}")
    _LOGGER.debug(f"Config Entry Data for {address}: {entry.data}")
    _LOGGER.debug(f"Config Entry Options for {address}: {entry.options}")

    # Create the coordinator for this specific device entry
    # Pass the entry itself, coordinator will extract details
    coordinator = BLEScannerCoordinator(hass, entry)

    # Perform the first refresh to catch connection issues early
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        # Let HA handle retries
        _LOGGER.warning(f"Initial connection failed for {address}, setup will be retried")
        raise
    except UpdateFailed as err:
        # Log specific error but still raise ConfigEntryNotReady
        _LOGGER.error(f"Error connecting to device {address} during setup: {err}")
        raise ConfigEntryNotReady(f"Could not connect to {address}") from err


    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms (sensor) for this device entry
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up options listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    _LOGGER.info(f"BLE Scanner setup complete for device: {address}")
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    address = entry.data.get(CONF_DEVICE_ADDRESS, entry.entry_id) # Use address if available
    _LOGGER.info(f"Unloading BLE Scanner integration for device: {address}")

    # Unload platforms associated with this entry
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Clean up coordinator and data for this specific entry
        if entry.entry_id in hass.data[DOMAIN]:
             coordinator: BLEScannerCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
             await coordinator.async_stop() # Ensure coordinator stops BLE connections etc.
             _LOGGER.info(f"BLE Scanner coordinator stopped and data removed for device: {address}")
        else:
             _LOGGER.warning(f"Coordinator for {address} (entry_id: {entry.entry_id}) not found in hass.data during unload.")


    _LOGGER.info(f"BLE Scanner integration unload status for {address}: {unload_ok}")
    return unload_ok

async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    address = entry.data.get(CONF_DEVICE_ADDRESS, entry.entry_id)
    _LOGGER.debug(f"Options updated for {address}, reloading entry...")
    # Reload the entry to apply changes (e.g., polling interval)
    await hass.config_entries.async_reload(entry.entry_id)
    _LOGGER.debug(f"Entry {address} reloaded after options update.")

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
        device_name = self.config_entry.title or self.config_entry.data.get(CONF_DEVICE_ADDRESS)

        return self.async_show_form(
            step_id="device_options", # Matches strings.json key
            data_schema=options_schema,
            description_placeholders={"name": device_name},
            errors=errors, # Pass errors dictionary
        )
