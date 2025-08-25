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
from homeassistant.core import Config, HomeAssistant

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.SELECT]

async def async_setup(hass: HomeAssistant, config: Config):
    """Set up this integration using YAML is not supported."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    # Get devices from config entry data
    devices = entry.data.get(CONF_DEVICES, [])
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

    update_interval = timedelta(
        seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )

    coordinator = BLESensorCoordinator(
        hass,
        _LOGGER,
        devices=devices,
        update_interval=update_interval
    )

    # Store coordinator in hass data
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms
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
