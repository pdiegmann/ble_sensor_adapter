"""The BLE Scanner integration."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.const import Platform

from ble_scanner.const import DOMAIN, CONF_DEVICES, CONF_LOG_LEVEL, LOGGER_NAME
from ble_scanner.coordinator import BLEScannerCoordinator

_LOGGER = logging.getLogger(LOGGER_NAME)

# Define the platform that this integration will support
PLATFORMS: list[Platform] = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BLE Scanner from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Set logger level based on config
    log_level_str = entry.options.get(CONF_LOG_LEVEL, entry.data.get(CONF_LOG_LEVEL, "info")).upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    _LOGGER.setLevel(log_level)
    # Also set level for bleak logger if needed, can be noisy
    logging.getLogger("bleak").setLevel(max(log_level, logging.WARNING)) # Avoid bleak debug spam unless component is in debug

    _LOGGER.info("Setting up BLE Scanner integration")
    _LOGGER.debug(f"Config Entry Data: {entry.data}")
    _LOGGER.debug(f"Config Entry Options: {entry.options}")

    devices_config = entry.options.get(CONF_DEVICES, [])
    if not devices_config:
        _LOGGER.warning("No devices configured for BLE Scanner. Please configure devices via integration options.")
        # Allow setup without devices, can be added later via options flow

    # Create the coordinator
    coordinator = BLEScannerCoordinator(hass, entry)

    # Fetch initial data so we have data when entities subscribe
    # However, coordinator setup handles the first refresh
    # await coordinator.async_config_entry_first_refresh()
    # Handled internally by coordinator now

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms (sensor)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload integration when options changed
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info("BLE Scanner integration setup complete")
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading BLE Scanner integration")
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Clean up coordinator and data
        coordinator: BLEScannerCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.stop_scan()
        _LOGGER.info("BLE Scanner coordinator stopped and data removed")

    _LOGGER.info(f"BLE Scanner integration unload status: {unload_ok}")
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    _LOGGER.info("Reloading BLE Scanner integration due to options update")
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
    _LOGGER.info("BLE Scanner integration reloaded")

