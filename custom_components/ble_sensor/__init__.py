"""The BLE Sensor integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.bluetooth import (
    async_scanner_count,
    BluetoothChange,
    BluetoothScanningMode,
    async_register_scanner,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send

from custom_components.ble_sensor.utils.const import DOMAIN, SIGNAL_DEVICE_UNAVAILABLE
from custom_components.ble_sensor.coordinator import BLESensorDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.SELECT]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BLE Sensor from a config entry."""
    try:
        # Check if Bluetooth is available
        scanner_count = await async_scanner_count(hass)
        if not scanner_count:
            _LOGGER.error("No Bluetooth scanner found")
            raise ConfigEntryNotReady("No Bluetooth scanner available")

        # Ensure active scanning is enabled
        active_scanner_count = await async_scanner_count(hass, BluetoothScanningMode.ACTIVE)
        if active_scanner_count == 0:
            _LOGGER.debug("Registering active Bluetooth scanner")
            entry.async_on_unload(
                await async_register_scanner(hass, True, BluetoothScanningMode.ACTIVE)
            )

        # Create coordinator instance for this entry
        coordinator = BLESensorDataUpdateCoordinator(hass, entry)
        
        # Store coordinator in hass data
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = coordinator
        
        # Start the coordinator with timeout
        try:
            start_task = hass.async_create_task(coordinator.async_start())
            await asyncio.wait_for(start_task, timeout=30.0)  # 30 second timeout for startup
        except asyncio.TimeoutError:
            await coordinator.async_stop()
            raise ConfigEntryNotReady("Timeout waiting for device initialization")
        except Exception as ex:
            await coordinator.async_stop()
            _LOGGER.error("Failed to start coordinator: %s", ex)
            raise ConfigEntryNotReady(f"Failed to initialize: {ex}")
        
        # Set up platforms
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        
        # Set up entry reload listener
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))
        
        # Clean up when Home Assistant stops
        @callback
        async def _async_stop(_: Any) -> None:
            """Stop the coordinator when Home Assistant stops."""
            _LOGGER.debug("Cleaning up BLE Sensor integration")
            await coordinator.async_stop()
            async_dispatcher_send(hass, f"{SIGNAL_DEVICE_UNAVAILABLE}_{entry.entry_id}")
        
        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
        )
        
        return True

    except Exception as ex:
        _LOGGER.error("Error setting up BLE Sensor integration: %s", ex)
        raise ConfigEntryNotReady(f"Failed to set up integration: {ex}")


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    try:
        # Unload platforms
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        
        if unload_ok:
            # Stop the coordinator with timeout
            coordinator = hass.data[DOMAIN][entry.entry_id]
            try:
                stop_task = hass.async_create_task(coordinator.async_stop())
                await asyncio.wait_for(stop_task, timeout=10.0)  # 10 second timeout for cleanup
            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout while stopping coordinator")
            except Exception as ex:
                _LOGGER.error("Error stopping coordinator: %s", ex)
            
            # Remove entry from hass data
            hass.data[DOMAIN].pop(entry.entry_id)
            
        return unload_ok

    except Exception as ex:
        _LOGGER.error("Error unloading BLE Sensor integration: %s", ex)
        return False


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
