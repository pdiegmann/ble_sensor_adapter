"""The BLE Sensor Adapter integration."""
import asyncio
from datetime import timedelta
import logging
from custom_components.ble_sensor.devices.device import BLEDevice
from habluetooth import BluetoothScanningMode

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config, HomeAssistant
from homeassistant.components import bluetooth
from homeassistant.const import Platform

from custom_components.ble_sensor.coordinator import BLESensorCoordinator
from custom_components.ble_sensor.utils.const import CONF_DEVICE_TYPE, CONF_MAC, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.SELECT]

async def async_setup(hass: HomeAssistant, config: Config):
    """Set up this integration using YAML is not supported."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    update_interval = timedelta(
        seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )

    coordinator = BLESensorCoordinator(
        hass,
        _LOGGER,
        devices=[{
            CONF_MAC: entry.data[CONF_MAC],
            CONF_DEVICE_TYPE: entry.data[CONF_DEVICE_TYPE]
        }],
        update_interval=update_interval
    )
    await coordinator.async_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not entry.update_listeners:
        entry.add_update_listener(async_reload_entry)

    for device_config in coordinator.device_configs:
        device_id = device_config.device_id
        address = device_config.address

        # Register to receive callbacks when this device is discovered
        entry.async_on_unload(
            bluetooth.async_register_callback(
                hass,
                lambda service_info, change: coordinator.device_discovered(
                    service_info, device_config.device_id, change
                ),
                {"address": address},
                BluetoothScanningMode.ACTIVE
            )
        )
        
        entry.async_on_unload(
            bluetooth.async_track_unavailable(
                hass,
                lambda service_info, dev_id=device_id: coordinator.device_unavailable(
                    service_info, dev_id
                ),
                address,
                connectable=True
            )
        )

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
                if platform in coordinator.platforms
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