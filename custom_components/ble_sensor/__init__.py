"""The BLE Sensor Adapter integration."""
import logging
from habluetooth import BluetoothScanningMode
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.components import bluetooth
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from custom_components.ble_sensor import coordinator
from custom_components.ble_sensor.utils.const import DOMAIN, CONF_LOG_LEVEL

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BLE Sensor Adapter from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Set up logging level if configured
    log_level = entry.options.get(CONF_LOG_LEVEL, "info")
    logging.getLogger(DOMAIN).setLevel(getattr(logging, log_level.upper()))
    
    # Check if Bluetooth integration is available
    # if not bluetooth.async_scanner_count(hass, connectable=True):
    #     _LOGGER.error(
    #         "No connectable Bluetooth adapters found. This integration requires "
    #         "at least one Bluetooth adapter that can connect to devices"
    #     )
    #     raise ConfigEntryNotReady("No connectable Bluetooth adapters found")
    
    # Store the config entry in HASS data
    hass.data[DOMAIN][entry.entry_id] = entry.data
    
    # Forward the entry to the sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Set up entry update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    for device_config in coordinator.device_configs:
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
        
        # Track when devices go unavailable
        entry.async_on_unload(
            bluetooth.async_track_unavailable(
                hass,
                lambda service_info: coordinator.device_unavailable(
                    service_info, device_config.device_id
                ),
                address,
                connectable=True
            )
        )
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload entities
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # Remove entry from HASS data
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)