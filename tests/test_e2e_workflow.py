"""End-to-end workflow test for BLE Sensor integration."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def test_complete_integration_workflow():
    """Test the complete integration workflow from config to entities."""

    # Step 1: Test device type system
    from custom_components.ble_sensor.devices import get_device_type
    from custom_components.ble_sensor.utils.const import (DEFAULT_DEVICE_TYPE,
                                                          DOMAIN,
                                                          KEY_PF_BATTERY,
                                                          KEY_PF_POWER_STATUS)

    device_handler = get_device_type()
    assert device_handler.name == "petkit_fountain"

    # Step 2: Test coordinator initialization
    from datetime import timedelta

    from custom_components.ble_sensor.coordinator import (BLESensorCoordinator,
                                                          DeviceConfig)

    mock_hass = MagicMock()
    mock_logger = MagicMock()

    # Create device configuration
    devices = [{
        "address": "00:11:22:33:44:55",
        "type": DEFAULT_DEVICE_TYPE,
        "name": "Test Petkit Fountain",
        "id": "test_device"
    }]

    coordinator = BLESensorCoordinator(
        hass=mock_hass,
        logger=mock_logger,
        devices=devices,
        update_interval=timedelta(seconds=60)
    )

    assert len(coordinator.device_configs) == 1
    assert coordinator.device_configs[0].device_type == DEFAULT_DEVICE_TYPE
    assert coordinator.device_configs[0].name == "Test Petkit Fountain"

    # Step 3: Test entity descriptions generation
    sensor_descriptions = device_handler.get_sensor_descriptions()
    binary_sensor_descriptions = device_handler.get_binary_sensor_descriptions()
    switch_descriptions = device_handler.get_switch_descriptions()
    select_descriptions = device_handler.get_select_descriptions()

    # Validate key entities exist
    sensor_keys = [desc.key for desc in sensor_descriptions]
    switch_keys = [desc.key for desc in switch_descriptions]

    assert KEY_PF_BATTERY in sensor_keys  # Battery should be a sensor
    assert KEY_PF_POWER_STATUS in switch_keys  # Power status is a switch

    # Step 4: Test device availability and data access
    device_id = "test_device"

    # Initially should be unavailable
    assert coordinator.is_device_available(device_id) is False
    assert coordinator.get_device_data(device_id) is None

    # Step 5: Test coordinator data storage
    test_data = {
        KEY_PF_BATTERY: 85,
        KEY_PF_POWER_STATUS: "on"
    }
    coordinator._device_data[device_id] = test_data
    coordinator._device_status[device_id] = True

    assert coordinator.is_device_available(device_id) is True
    assert coordinator.get_device_data(device_id) == test_data
    assert coordinator.get_device_data(device_id)[KEY_PF_BATTERY] == 85

async def test_config_flow_to_coordinator_workflow():
    """Test the workflow from config flow to coordinator setup."""
    from custom_components.ble_sensor.utils.const import (CONF_DEVICE_TYPE,
                                                          CONF_MAC,
                                                          DEFAULT_DEVICE_TYPE)

    # Step 1: Simulate config flow completion
    config_data = {
        CONF_MAC: "aa:bb:cc:dd:ee:ff",
        CONF_DEVICE_TYPE: DEFAULT_DEVICE_TYPE
    }

    # Step 2: Test device configuration creation
    from custom_components.ble_sensor.coordinator import DeviceConfig

    device_config = DeviceConfig(
        device_id=config_data[CONF_MAC],
        name=f"Petkit Fountain {config_data[CONF_MAC]}",
        address=config_data[CONF_MAC],
        device_type=config_data[CONF_DEVICE_TYPE],
        polling_interval=60
    )

    assert device_config.device_type == DEFAULT_DEVICE_TYPE
    assert device_config.address == "aa:bb:cc:dd:ee:ff"

    # Step 3: Test coordinator with this configuration
    from custom_components.ble_sensor.coordinator import BLESensorCoordinator

    mock_hass = MagicMock()
    mock_logger = MagicMock()

    devices = [{
        "address": device_config.address,
        "type": device_config.device_type,
        "name": device_config.name,
        "id": device_config.device_id
    }]

    coordinator = BLESensorCoordinator(
        hass=mock_hass,
        logger=mock_logger,
        devices=devices
    )

    # Validate coordinator setup
    assert len(coordinator.device_configs) == 1
    created_config = coordinator.device_configs[0]
    assert created_config.device_type == DEFAULT_DEVICE_TYPE
    assert created_config.address == config_data[CONF_MAC]

def test_entity_setup_workflow():
    """Test entity setup workflow based on device type."""
    from custom_components.ble_sensor.devices import get_device_type

    # Step 1: Get device handler (simplified)
    device_handler = get_device_type()  # Always returns Petkit Fountain

    # Step 2: Get all entity descriptions
    sensor_descriptions = device_handler.get_sensor_descriptions()
    binary_sensor_descriptions = device_handler.get_binary_sensor_descriptions()
    switch_descriptions = device_handler.get_switch_descriptions()
    select_descriptions = device_handler.get_select_descriptions()

    # Step 3: Validate entities are available
    total_entities = (
        len(sensor_descriptions) +
        len(binary_sensor_descriptions) +
        len(switch_descriptions) +
        len(select_descriptions)
    )
    assert total_entities > 0

    # Step 4: Validate entity structure
    all_descriptions = (
        sensor_descriptions +
        binary_sensor_descriptions +
        switch_descriptions +
        select_descriptions
    )

    for desc in all_descriptions:
        assert hasattr(desc, 'key')
        assert hasattr(desc, 'name')
        assert desc.key is not None
        assert desc.name is not None

def test_component_integration_points():
    """Test integration with Home Assistant core components."""

    # Step 1: Test manifest configuration
    import json
    import os

    manifest_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "custom_components", "ble_sensor", "manifest.json"
    )

    with open(manifest_path) as f:
        manifest = json.load(f)

    # Validate integration type and dependencies
    assert manifest["integration_type"] == "device"
    assert manifest["config_flow"] is True
    assert "bluetooth" in manifest["dependencies"]

    # Step 2: Test domain consistency
    from custom_components.ble_sensor.utils.const import DOMAIN
    assert manifest["domain"] == DOMAIN

    # Step 3: Test Bluetooth configuration for Petkit
    bluetooth_config = manifest["bluetooth"]
    petkit_patterns = [
        config for config in bluetooth_config
        if any(
            "petkit" in str(value).lower()
            for value in config.values()
            if isinstance(value, str)
        )
    ]
    assert len(petkit_patterns) > 0

async def test_error_handling_workflow():
    """Test error handling in the integration workflow."""
    from custom_components.ble_sensor.devices import get_device_type

    # Step 1: Test unsupported device type error
    with pytest.raises(ValueError, match="Unsupported device type"):
        get_device_type("unsupported_device")

    # Step 2: Test MAC validation
    from custom_components.ble_sensor.config_flow import BLESensorConfigFlow

    invalid_macs = ["invalid", "00:11:22:33", "zz:yy:xx:ww:vv:uu"]
    for mac in invalid_macs:
        assert BLESensorConfigFlow._is_valid_mac(mac) is False

    # Step 3: Test coordinator with empty devices
    from custom_components.ble_sensor.coordinator import BLESensorCoordinator

    mock_hass = MagicMock()
    mock_logger = MagicMock()

    coordinator = BLESensorCoordinator(
        hass=mock_hass,
        logger=mock_logger,
        devices=[]  # Empty devices list
    )

    # Should handle empty device list gracefully
    update_result = await coordinator._async_update_data()
    assert update_result == {}

def test_architectural_simplification_validation():
    """Validate that architectural simplifications work correctly."""
    from custom_components.ble_sensor.devices import (
        DEFAULT_DEVICE_TYPE, get_device_type, get_supported_device_types)
    from custom_components.ble_sensor.utils.const import (
        DEVICE_TYPES, SUPPORTED_DEVICE_TYPES)

    # Step 1: Validate single device type focus
    supported_types = get_supported_device_types()
    assert len(supported_types) == 1
    assert supported_types[0] == DEFAULT_DEVICE_TYPE
    assert supported_types == SUPPORTED_DEVICE_TYPES

    # Step 2: Validate device handler consistency
    handler1 = get_device_type()
    handler2 = get_device_type(None)
    handler3 = get_device_type(DEFAULT_DEVICE_TYPE)

    assert handler1.name == handler2.name == handler3.name
    assert handler1.description == handler2.description == handler3.description

    # Step 3: Validate constants consistency
    assert DEFAULT_DEVICE_TYPE in DEVICE_TYPES
    assert DEFAULT_DEVICE_TYPE in SUPPORTED_DEVICE_TYPES
    assert len(SUPPORTED_DEVICE_TYPES) == 1

if __name__ == "__main__":
    pytest.main([__file__])
