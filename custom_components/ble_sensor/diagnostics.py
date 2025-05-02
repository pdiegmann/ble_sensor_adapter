"""Diagnostics support for BLE Sensor."""
from __future__ import annotations

import logging
from typing import Any, Dict

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant

from custom_components.ble_sensor.const import CONF_DEVICE_TYPE, DOMAIN, CONF_MAC

_LOGGER = logging.getLogger(__name__)

TO_REDACT = {CONF_MAC}

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Get device info
    device_info = {
        "device_type": entry.data[CONF_DEVICE_TYPE],
        "model": coordinator.device.model,
        "manufacturer": coordinator.device.manufacturer,
        "name": coordinator.device.name,
        "available": coordinator.device.available,
    }
    
    # Get device data
    device_data = coordinator.device.data if coordinator.device.data else {}
    
    # Get connection info
    connection_info = {
        "connected": coordinator.ble_connection.connected if coordinator.ble_connection else False,
        "available": coordinator.ble_connection.available if coordinator.ble_connection else False,
    }
    
    # Build diagnostics data
    diagnostic_data = {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_info": device_info,
        "device_data": device_data,
        "connection_info": connection_info,
    }
    
    return diagnostic_data