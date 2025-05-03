"""Test the BLE Sensor sensors."""
from unittest.mock import MagicMock, patch
import pytest
import logging

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.components.sensor import SensorEntityDescription, SensorDeviceClass
from custom_components.ble_sensor.sensor import BLESensorAdapterSensor
from custom_components.ble_sensor.coordinator import BLESensorCoordinator

_LOGGER = logging.getLogger(__name__)

async def test_sensor_state(hass_mock, mock_config_entry):
    """Test sensor state updates."""
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
        coordinator = BLESensorCoordinator(
            hass_mock,
            _LOGGER,
            devices
        )

        # Create mock device
        device = MagicMock()
        device.name = "Test Device"
        device.address = "00:11:22:33:44:55"
        device.get_manufacturer.return_value = "Test Manufacturer"
        device.get_model.return_value = "Test Model"
    
        # Create a test sensor
        sensor = BLESensorAdapterSensor(
            coordinator,
            device,
            "battery",
            "Battery",
            device_class=SensorDeviceClass.BATTERY,
            unit_of_measurement="%"
        )

        # Test initial state (unavailable)
        assert sensor.available is False
        assert sensor.native_value is None

        # Test state update and available
        coordinator.data = {"battery": 75}
        coordinator._device_status = {sensor._device_id: True}
        assert sensor.native_value == 75
        assert sensor.available is True

        # Test missing data
        coordinator.data = {"other_key": 50}
        assert sensor.native_value is None

async def test_sensor_device_info(hass_mock, mock_config_entry):
    """Test sensor device info."""
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
        coordinator = BLESensorCoordinator(
            hass_mock,
            _LOGGER,
            devices
        )

        # Create mock device
        device = MagicMock()
        device.name = "Test Device"
        device.address = "00:11:22:33:44:55"
        device.get_manufacturer.return_value = "Test Manufacturer"
        device.get_model.return_value = "Test Model"
    
        sensor = BLESensorAdapterSensor(
            coordinator,
            device,
            "battery",
            "Battery"
        )
    
        device_info = sensor.device_info
        assert device_info is not None
        assert "identifiers" in device_info
        assert device_info["manufacturer"] == "Test Manufacturer"
        assert device_info["model"] == "Test Model"

async def test_sensor_attributes(hass_mock, mock_config_entry):
    """Test sensor attributes."""
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
        coordinator = BLESensorCoordinator(
            hass_mock,
            _LOGGER,
            devices
        )

        # Create mock device
        device = MagicMock()
        device.name = "Test Device"
        device.address = "00:11:22:33:44:55"
    
        sensor = BLESensorAdapterSensor(
            coordinator,
            device,
            "temperature",
            "Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            unit_of_measurement="°C"
        )
    
        assert sensor.device_class == SensorDeviceClass.TEMPERATURE
        assert sensor.native_unit_of_measurement == "°C"