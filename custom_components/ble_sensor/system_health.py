"""System health for BLE Sensor integration."""
from __future__ import annotations

from typing import Any, Dict

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from custom_components.ble_sensor.utils.const import DOMAIN, SYSTEM_HEALTH_INFO

@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)

async def system_health_info(hass: HomeAssistant) -> Dict[str, Any]:
    """Get system health info."""
    # Count active devices
    device_count = 0
    available_count = 0
    
    # Check all entries
    for entry_id, coordinator in hass.data.get(DOMAIN, {}).items():
        device_count += 1
        if coordinator.device.available:
            available_count += 1
    
    # Store some system health info in hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][SYSTEM_HEALTH_INFO] = {
        "device_count": device_count,
        "available_count": available_count,
    }
    
    return {
        "total_devices": device_count,
        "available_devices": available_count,
    }