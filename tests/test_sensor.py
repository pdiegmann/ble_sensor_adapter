"""Test the BLE Sensor sensors."""
from unittest.mock import MagicMock, patch
import pytest

from homeassistant.const import STATE_UNAVAILABLE
from custom_components.ble_sensor.sensor import BLESensor
from custom_components.ble_sensor.coordinator import BLESensorDataUpdateCoordinator

async def test_sensor_state(hass_mock, mock_config_entry):
    """Test sensor state updates."""
    coordinator = BLESensorDataUpdateCoordinator(
        hass_mock,
        mock_config_entry,
        update_interval=30
    )
    
    # Create a test sensor
    sensor = BLESensor(
        coordinator,
        "test_id",
        "Test Sensor",
        "test_key",
        "measurement",
        device_class="battery"
    )

    # Test initial state
    assert sensor.available is False
    assert sensor.state == STATE_UNAVAILABLE

    # Test state update
    coordinator.data = {"test_key": 75}
    assert sensor.state == 75
    assert sensor.available is True

    # Test invalid data
    coordinator.data = {"other_key": 50}
    assert sensor.state is None
    
async def test_sensor_device_info(hass_mock, mock_config_entry):
    """Test sensor device info."""
    coordinator = BLESensorDataUpdateCoordinator(
        hass_mock,
        mock_config_entry,
        update_interval=30
    )
    
    sensor = BLESensor(
        coordinator,
        "test_id",
        "Test Sensor",
        "test_key",
        "measurement"
    )
    
    device_info = sensor.device_info
    assert device_info is not None
    assert "identifiers" in device_info
    assert "name" in device_info

async def test_sensor_unique_id(hass_mock, mock_config_entry):
    """Test sensor unique ID generation."""
    coordinator = BLESensorDataUpdateCoordinator(
        hass_mock,
        mock_config_entry,
        update_interval=30
    )
    
    sensor = BLESensor(
        coordinator,
        "test_id",
        "Test Sensor",
        "test_key",
        "measurement"
    )
    
    assert sensor.unique_id is not None
    assert "test_id" in sensor.unique_id