"""Device class for BLE sensors."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import async_ble_device_from_address

from custom_components.ble_sensor.utils.const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_get_ble_device(hass: HomeAssistant, address: str) -> Optional[BLEDevice]:
    """Get a BLE device by address."""
    # Try to find the device in already discovered devices
    ble_device = async_ble_device_from_address(hass, address, connectable=True)
    if ble_device:
        return ble_device
    
    # Look for it in all discovered service infos
    for service_info in bluetooth.async_discovered_service_info(hass):
        if service_info.address == address:
            return service_info.device
    
    # Try one more direct scan
    try:
        return await bluetooth.async_scanner_device_by_address(hass, address, connectable=True)
    except Exception as ex:
        _LOGGER.error("Error scanning for device %s: %s", address, str(ex))
        return None

class BLEDevice():
    """Base class for BLE devices."""

    def __init__(
        self, 
        mac_address: str,
        device_type: str,
        model: str = "Generic BLE Device",
        manufacturer: str = "Unknown",
    ) -> None:
        """Initialize the BLE device."""
        self.mac_address = mac_address
        self.device_type = device_type
        self.model = model
        self.manufacturer = manufacturer
        self._data: Optional[Dict[str, Any]] = None
        self._available = False

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this device."""
        return f"{DOMAIN}_{self.device_type}_{self.mac_address}"

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return f"{self.model} ({self.mac_address})"

    @property
    def data(self) -> Optional[Dict[str, Any]]:
        """Return the device data."""
        return self._data

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self._available

    @available.setter
    def available(self, available: bool) -> None:
        """Set device availability."""
        self._available = available

    def update_from_data(self, data: Dict[str, Any]) -> bool:
        """Update device from data dictionary."""
        try:
            self._data = data
            return True
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error("Failed to parse data for %s: %s", self.mac_address, ex)
            return False

    def get_device_info(self) -> Dict[str, Any]:
        """Return device information for Home Assistant."""
        return {
            "identifiers": {(DOMAIN, self.mac_address)},
            "name": self.name,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "via_device": (DOMAIN, "bluetooth"),
        }