"""Base class for BLE devices."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from bleak import BleakClient

class BaseBLEDevice(ABC):
    """Base class for BLE devices."""

    def __init__(self, address: str, name: Optional[str] = None) -> None:
        """Initialize the device."""
        self.address = address
        self._name = name or f"BLE Device {address[-5:].replace(':', '')}"

    @property
    def name(self) -> str:
        """Return the device name."""
        return self._name

    @abstractmethod
    async def poll_data(self, client: BleakClient) -> Dict[str, Any]:
        """Poll the device for data.
        
        Args:
            client: Connected BleakClient instance
            
        Returns:
            Dict with sensor data
        """
        pass

    @abstractmethod
    def get_supported_sensors(self) -> List[Dict[str, Any]]:
        """Return a list of supported sensors.
        
        Returns:
            List of dictionaries with sensor information:
            {
                "key": "sensor_key",
                "name": "Sensor Name",
                "device_class": "temperature",  # Optional
                "state_class": "measurement",   # Optional
                "unit_of_measurement": "°C",    # Optional
                "icon": "mdi:thermometer",      # Optional
            }
        """
        pass

    def get_manufacturer(self) -> str:
        """Return the manufacturer name."""
        return "Generic"

    def get_model(self) -> str:
        """Return the model name."""
        return "BLE Device"