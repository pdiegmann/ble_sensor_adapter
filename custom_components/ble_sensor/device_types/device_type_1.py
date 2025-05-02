"""Implementation for Device Type 1."""
from __future__ import annotations

from typing import Any, Dict, List, Type
import logging

from custom_components.ble_sensor.device_types.base import BaseDeviceData, DeviceType
from custom_components.ble_sensor.device import DeviceData

_LOGGER = logging.getLogger(__name__)

class DeviceType1Data(BaseDeviceData):
    """Device Type 1 data parser."""

    def parse_data(self) -> None:
        """Parse the raw data into usable data."""
        super().parse_data()
        
        try:
            # Example parsing - this should be customized for actual device
            if "raw_data" in self.raw_data:
                raw_bytes = self.raw_data["raw_data"]
                
                # Example: Extract temperature value from bytes 0-1
                if len(raw_bytes) >= 2:
                    self._parsed_data["temperature"] = int.from_bytes(
                        raw_bytes[0:2], byteorder="little"
                    ) / 100.0
                    
                # Example: Extract humidity value from bytes 2-3
                if len(raw_bytes) >= 4:
                    self._parsed_data["humidity"] = int.from_bytes(
                        raw_bytes[2:4], byteorder="little"
                    ) / 100.0
                    
                # Example: Extract battery level from byte 4
                if len(raw_bytes) >= 5:
                    self._parsed_data["battery"] = raw_bytes[4]
                    
                # Example: Extract button state from byte 5
                if len(raw_bytes) >= 6:
                    self._parsed_data["button_pressed"] = bool(raw_bytes[5])
        
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error("Error parsing DeviceType1 data: %s", ex)

class DeviceType1(DeviceType):
    """Device Type 1 implementation."""

    def __init__(self) -> None:
        """Initialize the device type."""
        super().__init__()
        self._name = "device_type_1"
        self._description = "Device Type 1"
        
    def get_device_data_class(self) -> Type[DeviceData]:
        """Return the data class for this device type."""
        return DeviceType1Data
        
    def get_entity_descriptions(self) -> List[Dict[str, Any]]:
        """Return entity descriptions for this device type."""
        return [
            {
                "key": "temperature",
                "name": "Temperature",
                "device_class": "temperature",
                "state_class": "measurement",
                "native_unit_of_measurement": "°C",
                "entity_category": None,
                "entity_type": "sensor",
            },
            {
                "key": "humidity",
                "name": "Humidity",
                "device_class": "humidity",
                "state_class": "measurement",
                "native_unit_of_measurement": "%",
                "entity_category": None,
                "entity_type": "sensor",
            },
            {
                "key": "battery",
                "name": "Battery",
                "device_class": "battery",
                "state_class": "measurement",
                "native_unit_of_measurement": "%",
                "entity_category": "diagnostic",
                "entity_type": "sensor",
            },
            {
                "key": "button_pressed",
                "name": "Button",
                "device_class": "button",
                "entity_category": None,
                "entity_type": "binary_sensor",
            },
        ]
        
    def get_characteristics(self) -> List[str]:
        """Return characteristic UUIDs this device uses."""
        # Replace with actual UUIDs for your device
        return [
            "00002a1c-0000-1000-8000-00805f9b34fb",  # Temperature
            "00002a6f-0000-1000-8000-00805f9b34fb",  # Humidity
        ]
        
    def get_services(self) -> List[str]:
        """Return service UUIDs this device uses."""
        # Replace with actual UUIDs for your device
        return [
            "00001809-0000-1000-8000-00805f9b34fb",  # Health Thermometer
            "0000180f-0000-1000-8000-00805f9b34fb",  # Battery Service
        ]