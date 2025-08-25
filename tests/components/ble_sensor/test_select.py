"""Test the BLE Sensor select component."""
import logging
from asyncio import Future
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ble_sensor.coordinator import BLESensorCoordinator
from custom_components.ble_sensor.select import BLESelectEntity
from custom_components.ble_sensor.utils.const import KEY_PF_MODE
from homeassistant.components.select import SelectEntityDescription
from homeassistant.const import STATE_UNAVAILABLE

_LOGGER = logging.getLogger(__name__)

def create_mock_coro(return_value=None):
    """Create a mock coroutine function."""
    future = Future()
    future.set_result(return_value)
    return future

async def test_select_options(hass_mock, mock_config_entry):
    """Test select options and state."""
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

        description = SelectEntityDescription(
            key=KEY_PF_MODE,
            name="Test Mode",
            options=["Normal", "Smart", "Custom"]
        )
        select = BLESelectEntity(coordinator, description)

        # Test options
        assert select.options == ["Normal", "Smart", "Custom"]

        # Test initial state
        assert select.available is False
        assert select.current_option is None

        # Test state update
        coordinator.data = {KEY_PF_MODE: "Smart"}
        assert select.current_option == "Smart"
        coordinator._device_status = {select._device_id: True}
        assert select.available is True

async def test_select_select_option(hass_mock, mock_config_entry):
    """Test select option selection."""
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

        description = SelectEntityDescription(
            key=KEY_PF_MODE,
            name="Test Mode",
            options=["Normal", "Smart", "Custom"]
        )
        select = BLESelectEntity(coordinator, description)

        # Mock coordinator's device_type and ble_connection
        coordinator.device_type = MagicMock()
        coordinator.device_type.async_set_mode = MagicMock(return_value=create_mock_coro())
        coordinator.ble_connection = MagicMock()
        coordinator.ble_connection.client = MagicMock()
        coordinator.async_request_refresh = MagicMock(return_value=create_mock_coro())

        # Test selecting an option
        await select.async_select_option("Smart")
        coordinator.device_type.async_set_mode.assert_called_once_with(
            coordinator.ble_connection.client, "Smart"
        )
        coordinator.async_request_refresh.assert_called_once()

async def test_select_invalid_option(hass_mock, mock_config_entry):
    """Test selecting invalid option."""
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

        description = SelectEntityDescription(
            key=KEY_PF_MODE,
            name="Test Mode",
            options=["Normal", "Smart", "Custom"]
        )
        select = BLESelectEntity(coordinator, description)

        # Mock coordinator's device_type and ble_connection
        mock_async_set_mode = AsyncMock()
        coordinator.device_type = MagicMock()
        coordinator.device_type.async_set_mode = mock_async_set_mode
        coordinator.device_type.async_set_mode.side_effect = ValueError("Invalid mode")
        coordinator.ble_connection = MagicMock()
        coordinator.ble_connection.client = MagicMock()

        # Test selecting invalid option
        with pytest.raises(ValueError):
            await select.async_select_option("Invalid")
