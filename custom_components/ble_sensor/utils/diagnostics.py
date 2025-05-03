"""Diagnostics support for BLE Sensor."""
from __future__ import annotations

import logging
from typing import Any, Dict
import time

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    async_scanner_count,
    BluetoothScanningMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant

from custom_components.ble_sensor.utils.const import CONF_DEVICE_TYPE, DOMAIN, CONF_MAC

_LOGGER = logging.getLogger(__name__)

TO_REDACT = {CONF_MAC}

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    mac_address = entry.data[CONF_MAC].lower()
    
    # Get Bluetooth environment information
    scanner_count = async_scanner_count(hass)
    active_scanners = async_scanner_count(hass, BluetoothScanningMode.ACTIVE)
    passive_scanners = async_scanner_count(hass, BluetoothScanningMode.PASSIVE)
    
    bluetooth_info = {
        "scanner_available": bool(scanner_count),
        "active_scanners": active_scanners,
        "passive_scanners": passive_scanners,
    }
    
    # Check if device is currently discoverable
    discovered_devices = {
        info.address: {
            "name": info.name,
            "rssi": info.rssi,
            "connectable": info.connectable,
            "time_since_update": time.time() - info.time,
            "advertisement_data": {
                "manufacturer_data": {
                    k.hex(): v.hex() for k, v in info.manufacturer_data.items()
                } if info.manufacturer_data else {},
                "service_data": {
                    k: v.hex() for k, v in info.service_data.items()
                } if info.service_data else {},
                "service_uuids": info.service_uuids,
                "local_name": info.name,
            }
        }
        for info in bluetooth.async_discovered_service_info(hass)
        if info.address.lower() == mac_address
    }
    
    # Get device info
    device_info = {
        "device_type": entry.data[CONF_DEVICE_TYPE],
        "model": coordinator.device.model,
        "manufacturer": coordinator.device.manufacturer,
        "name": coordinator.device.name,
        "available": coordinator.device.available,
        "initialized": coordinator.device_type._is_initialized if hasattr(coordinator.device_type, '_is_initialized') else None,
        "polling_required": coordinator.device_type.requires_polling(),
        "characteristics": coordinator.device_type.get_characteristics(),
        "services": coordinator.device_type.get_services(),
    }
    
    # Get connection info
    connection_info = {
        "connected": coordinator.ble_connection.connected if coordinator.ble_connection else False,
        "available": coordinator.ble_connection.available if coordinator.ble_connection else False,
        "connection_attempts": coordinator.device_type._connection_attempts if hasattr(coordinator.device_type, '_connection_attempts') else None,
        "consecutive_errors": coordinator.ble_connection._consecutive_errors if hasattr(coordinator.ble_connection, '_consecutive_errors') else None,
    }
    
    # Get coordinator info
    coordinator_info = {
        "last_update_success": coordinator.last_update_success,
        "last_update": coordinator.last_update.isoformat() if coordinator.last_update else None,
        "update_interval": str(coordinator.update_interval) if coordinator.update_interval else None,
        "has_value": coordinator.data is not None,
    }
    
    # Build diagnostics data
    diagnostic_data = {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "bluetooth_environment": bluetooth_info,
        "discovered_advertisements": discovered_devices,
        "device_info": device_info,
        "connection_info": connection_info,
        "coordinator_info": coordinator_info,
    }
    
    # Include device data if available
    if coordinator.device.data:
        diagnostic_data["device_data"] = coordinator.device.data
    
    return diagnostic_data
