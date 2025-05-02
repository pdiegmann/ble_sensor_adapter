"""The BLE Sensor integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from custom_components.ble_sensor.const import DOMAIN, SIGNAL_DEVICE_UNAVAILABLE
from custom_components.ble_sensor.coordinator import BLESensorDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BLE Sensor from a config entry."""
    # Create coordinator instance for this entry
    coordinator = BLESensorDataUpdateCoordinator(hass, entry)
    
    # Store coordinator in hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Start the coordinator
    await coordinator.async_start()
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Set up entry reload listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    # Clean up when Home Assistant stops
    @callback
    async def _async_stop(_: Any) -> None:
        """Stop the coordinator when Home Assistant stops."""
        await coordinator.async_stop()
        async_dispatcher_send(hass, f"{SIGNAL_DEVICE_UNAVAILABLE}_{entry.entry_id}")
    
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Stop the coordinator
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_stop()
        
        # Remove entry from hass data
        hass.data[DOMAIN].pop(entry.entry_id)
        
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)