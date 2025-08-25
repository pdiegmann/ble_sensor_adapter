"""Integration test for BLE Sensor component."""
from unittest.mock import MagicMock, patch

import pytest


def test_device_type_system():
    """Test the simplified device type system."""
    from custom_components.ble_sensor.devices import (
        DEFAULT_DEVICE_TYPE, get_device_type, get_supported_device_types)

    # Test default device type
    device_handler = get_device_type()
    assert device_handler.name == "petkit_fountain"
    assert device_handler.description == "Petkit Fountain"

    # Test explicit device type
    device_handler = get_device_type("petkit_fountain")
    assert device_handler.name == "petkit_fountain"

    # Test unsupported device type
    with pytest.raises(ValueError, match="Unsupported device type"):
        get_device_type("unknown_device")

    # Test supported device types
    supported = get_supported_device_types()
    assert supported == ["petkit_fountain"]
    assert DEFAULT_DEVICE_TYPE in supported

def test_constants_and_configuration():
    """Test that constants are properly configured."""
    from custom_components.ble_sensor.utils.const import (
        DEFAULT_DEVICE_TYPE, DEVICE_TYPES, DOMAIN, SUPPORTED_DEVICE_TYPES)

    assert DOMAIN == "ble_sensor"
    assert DEFAULT_DEVICE_TYPE == "petkit_fountain"
    assert "petkit_fountain" in DEVICE_TYPES
    assert DEVICE_TYPES["petkit_fountain"] == "Petkit Fountain"
    assert SUPPORTED_DEVICE_TYPES == ["petkit_fountain"]

def test_petkit_fountain_device():
    """Test Petkit Fountain device functionality."""
    from custom_components.ble_sensor.devices.petkit_fountain import \
        PetkitFountain

    device = PetkitFountain()
    assert device.name == "petkit_fountain"
    assert device.description == "Petkit Fountain"
    assert device.requires_polling() is True

    # Test entity descriptions are available
    sensors = device.get_sensor_descriptions()
    binary_sensors = device.get_binary_sensor_descriptions()
    switches = device.get_switch_descriptions()
    selects = device.get_select_descriptions()

    # Should have entities defined
    assert len(sensors) > 0
    assert len(binary_sensors) > 0
    assert len(switches) > 0
    assert len(selects) > 0

    # Test all entity descriptions are properly structured
    all_entities = device.get_entity_descriptions()
    assert len(all_entities) > 0

    for entity in all_entities:
        assert hasattr(entity, 'key')
        assert hasattr(entity, 'name')

def test_component_manifest():
    """Test that the component manifest is properly configured."""
    import json
    import os

    manifest_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "custom_components", "ble_sensor", "manifest.json"
    )

    with open(manifest_path) as f:
        manifest = json.load(f)

    # Validate required fields
    assert manifest["domain"] == "ble_sensor"
    assert manifest["name"] == "BLE Sensor"
    assert manifest["config_flow"] is True
    assert manifest["integration_type"] == "device"

    # Validate dependencies
    assert "bluetooth" in manifest["dependencies"]
    assert "bluetooth_adapters" in manifest["dependencies"]

    # Validate requirements
    requirements = manifest["requirements"]
    assert any("bleak" in req for req in requirements)
    assert any("bleak-retry-connector" in req for req in requirements)

    # Validate Bluetooth configuration for Petkit devices
    bluetooth_config = manifest["bluetooth"]
    assert len(bluetooth_config) > 0

    # Should have configuration for Petkit devices
    petkit_configs = [
        config for config in bluetooth_config
        if "local_name" in config and "petkit" in config["local_name"].lower()
    ]
    assert len(petkit_configs) >= 2  # Should have PETKIT* and petkit* patterns

def test_coordinator_device_config():
    """Test coordinator device configuration handling."""
    from custom_components.ble_sensor.coordinator import DeviceConfig
    from custom_components.ble_sensor.utils.const import (
        DEFAULT_DEVICE_TYPE, DEFAULT_POLL_INTERVAL)

    # Test device config creation
    config = DeviceConfig(
        device_id="test_device",
        name="Test Petkit Fountain",
        address="00:11:22:33:44:55",
        device_type=DEFAULT_DEVICE_TYPE,
        polling_interval=DEFAULT_POLL_INTERVAL
    )

    assert config.device_id == "test_device"
    assert config.name == "Test Petkit Fountain"
    assert config.address == "00:11:22:33:44:55"
    assert config.device_type == DEFAULT_DEVICE_TYPE
    assert config.polling_interval == DEFAULT_POLL_INTERVAL

def test_simplified_entity_creation():
    """Test that entity creation is simplified for single device type."""
    # This test validates our architectural simplification
    from custom_components.ble_sensor.devices import get_device_type

    # Should always get Petkit fountain handler
    handler1 = get_device_type()
    handler2 = get_device_type(None)
    handler3 = get_device_type("petkit_fountain")

    assert handler1.name == handler2.name == handler3.name == "petkit_fountain"

    # Entity descriptions should be consistent
    sensors1 = handler1.get_sensor_descriptions()
    sensors2 = handler2.get_sensor_descriptions()
    sensors3 = handler3.get_sensor_descriptions()

    assert len(sensors1) == len(sensors2) == len(sensors3)

def test_mac_address_validation():
    """Test MAC address validation functionality."""
    from custom_components.ble_sensor.config_flow import BLESensorConfigFlow

    # Valid MAC addresses
    valid_macs = [
        "00:11:22:33:44:55",
        "AA:BB:CC:DD:EE:FF",
        "aa:bb:cc:dd:ee:ff",
        "00-11-22-33-44-55",
        "AA-BB-CC-DD-EE-FF"
    ]

    # Invalid MAC addresses
    invalid_macs = [
        "invalid_mac",
        "00:11:22:33:44",  # Too short
        "00:11:22:33:44:55:66",  # Too long
        "GG:HH:II:JJ:KK:LL",  # Invalid hex
        "00:11:22:33:44:ZZ"  # Invalid hex
    ]

    for mac in valid_macs:
        assert BLESensorConfigFlow._is_valid_mac(mac) is True

    for mac in invalid_macs:
        assert BLESensorConfigFlow._is_valid_mac(mac) is False

if __name__ == "__main__":
    pytest.main([__file__])
