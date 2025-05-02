"""Device types for BLE Sensor integration."""
from typing import Dict, Type

from custom_components.ble_sensor.devices.device_types.base import DeviceType

from custom_components.ble_sensor.devices.device_types.petkit_fountain import PetkitFountain
from custom_components.ble_sensor.devices.device_types.soil_tester import SoilTester

# Map of device type name to device type class
DEVICE_TYPE_MAP: Dict[str, Type[DeviceType]] = {
    "petkit_fountain": PetkitFountain,
    "soil_tester": SoilTester,
}

def get_device_type(device_type_name: str) -> DeviceType:
    """Get device type instance by name."""
    device_type_class = DEVICE_TYPE_MAP.get(device_type_name)
    if device_type_class is None:
        raise ValueError(f"Unknown device type: {device_type_name}")
    return device_type_class()
