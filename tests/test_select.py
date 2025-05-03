"""Test the BLE Sensor select component."""
from unittest.mock import MagicMock, patch
import pytest

from homeassistant.const import STATE_UNAVAILABLE
from custom_components.ble_sensor.select import BLESelectEntity
from custom_components.ble_sensor.coordinator import BLESensorDataUpdateCoordinator
from homeassistant.components.select import SelectEntityDescription

async def test_select_options(hass_mock, mock_config_entry):
    """Test select options and state."""
    coordinator = BLESensorDataUpdateCoordinator(
        hass_mock,
        mock_config_entry,
        update_interval=30
    )
    
    description = SelectEntityDescription(
        key="mode",
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
    coordinator.data = {"mode": "Smart"}
    assert select.current_option == "Smart"
    assert select.available is True

async def test_select_select_option(hass_mock, mock_config_entry):
    """Test select option selection."""
    coordinator = BLESensorDataUpdateCoordinator(
        hass_mock,
        mock_config_entry,
        update_interval=30
    )
    
    description = SelectEntityDescription(
        key="mode",
        name="Test Mode",
        options=["Normal", "Smart", "Custom"]
    )
    select = BLESelectEntity(coordinator, description)

    # Mock coordinator's device_type and ble_connection
    coordinator.device_type = MagicMock()
    coordinator.ble_connection = MagicMock()
    coordinator.ble_connection.client = MagicMock()
    
    # Test selecting an option
    await select.async_select_option("Smart")
    coordinator.device_type.async_set_mode.assert_called_once_with(
        coordinator.ble_connection.client, "Smart"
    )
    coordinator.async_request_refresh.assert_called_once()

async def test_select_invalid_option(hass_mock, mock_config_entry):
    """Test selecting invalid option."""
    coordinator = BLESensorDataUpdateCoordinator(
        hass_mock,
        mock_config_entry,
        update_interval=30
    )
    
    description = SelectEntityDescription(
        key="mode",
        name="Test Mode",
        options=["Normal", "Smart", "Custom"]
    )
    select = BLESelectEntity(coordinator, description)

    # Mock coordinator's device_type and ble_connection
    coordinator.device_type = MagicMock()
    coordinator.ble_connection = MagicMock()
    coordinator.ble_connection.client = MagicMock()

    # Test selecting invalid option
    with pytest.raises(ValueError):
        await select.async_select_option("Invalid")