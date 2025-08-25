"""The BLE Sensor Adapter integration."""
import asyncio
import logging
from datetime import timedelta

from custom_components.ble_sensor.coordinator import BLESensorCoordinator
from custom_components.ble_sensor.utils.const import (CONF_DEVICES,
                                                      CONF_SCAN_INTERVAL,
                                                      DEFAULT_SCAN_INTERVAL,
                                                      DOMAIN)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

# Use new import path for Config to avoid deprecation warning
# Fallback to old import for compatibility with older HA versions
try:
    from homeassistant.core_config import Config
except ImportError:
    from homeassistant.core import Config

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.SELECT]

async def async_setup(hass: HomeAssistant, config: Config):
    """Set up this integration using YAML is not supported."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up this integration using UI."""
    _LOGGER.info("Setting up BLE Sensor integration with entry ID: %s", entry.entry_id)
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    # Get devices from config entry data
    devices = entry.data.get(CONF_DEVICES, [])
    _LOGGER.info("Found %d devices in config entry data", len(devices))
    
    if not devices:
        # Fallback for single device config (legacy support)
        from custom_components.ble_sensor.utils.const import (CONF_DEVICE_TYPE,
                                                              CONF_MAC)
        if CONF_MAC in entry.data and CONF_DEVICE_TYPE in entry.data:
            devices = [{
                "address": entry.data[CONF_MAC],
                "type": entry.data[CONF_DEVICE_TYPE],
                "name": f"Device {entry.data[CONF_MAC]}",
                "id": entry.data[CONF_MAC]
            }]
            _LOGGER.info("Using legacy single device config: %s", devices[0])

    update_interval = timedelta(
        seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )

    _LOGGER.info("Creating coordinator with update interval: %s", update_interval)
    coordinator = BLESensorCoordinator(
        hass,
        _LOGGER,
        devices=devices,
        update_interval=update_interval
    )

    # Store coordinator in hass data
    hass.data[DOMAIN][entry.entry_id] = coordinator
    _LOGGER.info("Coordinator created and stored with %d devices", len(coordinator.device_configs))

    # Set up platforms
    _LOGGER.info("Setting up platforms: %s", PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Add update listener
    if not entry.update_listeners:
        entry.add_update_listener(async_reload_entry)

    return True

async def async_update_options(hass, config_entry):
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unloaded

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
