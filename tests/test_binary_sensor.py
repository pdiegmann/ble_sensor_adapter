"""Test the BLE Sensor binary sensors."""
from unittest.mock import MagicMock, patch
import pytest

from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNAVAILABLE
from custom_components.ble_sensor.binary_sensor import BLESensorBinarySensorEntity
from custom_components.ble_sensor.coordinator import BLESensorDataUpdateCoordinator
from homeassistant.components.binary_sensor import BinarySensorEntityDescription

async def test_binary_sensor_state(hass_mock, mock_config_entry):
    """Test binary sensor state updates."""
    coordinator = BLESensorDataUpdateCoordinator(
        hass_mock,
        mock_config_entry,
        update_interval=30
    )
    
    # Create a test binary sensor
    description = BinarySensorEntityDescription(
        key="power_status",
        name="Test Power"
    )
    binary_sensor = BLESensorBinarySensorEntity(
        coordinator,
        description
    )

    # Test initial state
    assert binary_sensor.available is False
    assert binary_sensor.is_on is None

    # Test ON state
    coordinator.data = {"power_status": True}
    assert binary_sensor.is_on is True

    # Test OFF state
    coordinator.data = {"power_status": False}
    assert binary_sensor.is_on is False

    # Test missing data
    coordinator.data = {"other_key": True}
    assert binary_sensor.is_on is None

async def test_binary_sensor_device_info(hass_mock, mock_config_entry):
    """Test binary sensor device info."""
    coordinator = BLESensorDataUpdateCoordinator(
        hass_mock,
        mock_config_entry,
        update_interval=30
    )
    
    description = BinarySensorEntityDescription(
        key="power_status",
        name="Test Power"
    )
    binary_sensor = BLESensorBinarySensorEntity(coordinator, description)
    
    device_info = binary_sensor.device_info
    assert device_info is not None
    assert "identifiers" in device_info

async def test_binary_sensor_unique_id(hass_mock, mock_config_entry):
    """Test binary sensor unique ID generation."""
    coordinator = BLESensorDataUpdateCoordinator(
        hass_mock,
        mock_config_entry,
        update_interval=30
    )
    
    description = BinarySensorEntityDescription(
        key="power_status",
        name="Test Power"
    )
    binary_sensor = BLESensorBinarySensorEntity(coordinator, description)
    
    assert binary_sensor.unique_id is not None
    assert "power_status" in binary_sensor.unique_id