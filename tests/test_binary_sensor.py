"""Test the BLE Sensor binary sensors."""
from unittest.mock import MagicMock, patch
import pytest

from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNAVAILABLE
from custom_components.ble_sensor.binary_sensor import BLEBinarySensor
from custom_components.ble_sensor.coordinator import BLESensorDataUpdateCoordinator

async def test_binary_sensor_state(hass_mock, mock_config_entry):
    """Test binary sensor state updates."""
    coordinator = BLESensorDataUpdateCoordinator(
        hass_mock,
        mock_config_entry,
        update_interval=30
    )
    
    # Create a test binary sensor
    binary_sensor = BLEBinarySensor(
        coordinator,
        "test_power",
        "Test Power",
        "power_status"
    )

    # Test initial state
    assert binary_sensor.available is False
    assert binary_sensor.state == STATE_UNAVAILABLE

    # Test ON state
    coordinator.data = {"power_status": True}
    assert binary_sensor.state == STATE_ON
    assert binary_sensor.available is True

    # Test OFF state
    coordinator.data = {"power_status": False}
    assert binary_sensor.state == STATE_OFF
    assert binary_sensor.available is True

    # Test missing data
    coordinator.data = {"other_key": True}
    assert binary_sensor.state is None

async def test_binary_sensor_device_info(hass_mock, mock_config_entry):
    """Test binary sensor device info."""
    coordinator = BLESensorDataUpdateCoordinator(
        hass_mock,
        mock_config_entry,
        update_interval=30
    )
    
    binary_sensor = BLEBinarySensor(
        coordinator,
        "test_power",
        "Test Power",
        "power_status"
    )
    
    device_info = binary_sensor.device_info
    assert device_info is not None
    assert "identifiers" in device_info
    assert "name" in device_info

async def test_binary_sensor_unique_id(hass_mock, mock_config_entry):
    """Test binary sensor unique ID generation."""
    coordinator = BLESensorDataUpdateCoordinator(
        hass_mock,
        mock_config_entry,
        update_interval=30
    )
    
    binary_sensor = BLEBinarySensor(
        coordinator,
        "test_power",
        "Test Power",
        "power_status"
    )
    
    assert binary_sensor.unique_id is not None
    assert "test_power" in binary_sensor.unique_id