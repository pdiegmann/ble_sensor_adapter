"""Device types for BLE Sensor integration."""
from custom_components.ble_sensor.devices.base import DeviceType
from custom_components.ble_sensor.devices.petkit_fountain import PetkitFountain

# Simplified device registry - currently only supports Petkit Fountain
DEFAULT_DEVICE_TYPE = "petkit_fountain"

def get_device_type(device_type_name: str = None) -> DeviceType:
    """Get device type instance. Currently only supports Petkit Fountain."""
    # Since we only have one device type, default to it if none specified
    if device_type_name is None or device_type_name == DEFAULT_DEVICE_TYPE:
        return PetkitFountain()

    # For future extensibility, raise error for unsupported types
    raise ValueError(f"Unsupported device type: {device_type_name}. Only '{DEFAULT_DEVICE_TYPE}' is supported.")

def get_supported_device_types() -> list[str]:
    """Get list of supported device types."""
    return [DEFAULT_DEVICE_TYPE]
