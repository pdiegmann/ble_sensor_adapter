"""Test the BLE Sensor binary sensors."""
from unittest.mock import MagicMock, patch
import pytest
import logging

from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNAVAILABLE
from custom_components.ble_sensor.binary_sensor import BLESensorBinarySensorEntity
from custom_components.ble_sensor.coordinator import BLESensorDataUpdateCoordinator
from homeassistant.components.binary_sensor import BinarySensorEntityDescription

_LOGGER = logging.getLogger(__name__)

async def test_binary_sensor_state(hass_mock, mock_config_entry):
    """Test binary sensor state updates."""
    with patch("custom_components.ble_sensor.coordinator.get_device_type") as mock_get_device_type:
        # Configure device type mock
        device_type = MagicMock()
        device_type.requires_polling.return_value = True
        device_type.create_device.return_value = MagicMock()
        mock_get_device_type.return_value = device_type

        devices = [{
            "id": "test_device",
            "address": "00:11:22:33:44:55",
            "type": "petkit_fountain",
            "name": "Test Device"
        }]
        coordinator = BLESensorDataUpdateCoordinator(
            hass_mock,
            _LOGGER,
            devices
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

        # Test initial state (unavailable)
        assert binary_sensor.available is False
        assert binary_sensor.is_on is None

        # Test ON state and available
        coordinator.data = {"power_status": True}
        coordinator._device_status = {binary_sensor._device_id: True}
        assert binary_sensor.is_on is True
        assert binary_sensor.available is True

        # Test OFF state
        coordinator.data = {"power_status": False}
        assert binary_sensor.is_on is False

        # Test missing data
        coordinator.data = {"other_key": True}
        assert binary_sensor.is_on is None

async def test_binary_sensor_device_info(hass_mock, mock_config_entry):
    """Test binary sensor device info."""
    with patch("custom_components.ble_sensor.coordinator.get_device_type") as mock_get_device_type:
        # Configure device type mock
        device_type = MagicMock()
        device_type.requires_polling.return_value = True
        device_type.create_device.return_value = MagicMock()
        mock_get_device_type.return_value = device_type

        devices = [{
            "id": "test_device",
            "address": "00:11:22:33:44:55",
            "type": "petkit_fountain",
            "name": "Test Device"
        }]
        coordinator = BLESensorDataUpdateCoordinator(
            hass_mock,
            _LOGGER,
            devices
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
    with patch("custom_components.ble_sensor.coordinator.get_device_type") as mock_get_device_type:
        # Configure device type mock
        device_type = MagicMock()
        device_type.requires_polling.return_value = True
        device_type.create_device.return_value = MagicMock()
        mock_get_device_type.return_value = device_type

        devices = [{
            "id": "test_device",
            "address": "00:11:22:33:44:55",
            "type": "petkit_fountain",
            "name": "Test Device"
        }]
        coordinator = BLESensorDataUpdateCoordinator(
            hass_mock,
            _LOGGER,
            devices
        )
    
        description = BinarySensorEntityDescription(
            key="power_status",
            name="Test Power"
        )
        binary_sensor = BLESensorBinarySensorEntity(coordinator, description)
    
        assert binary_sensor.unique_id is not None
        assert "power_status" in binary_sensor.unique_id