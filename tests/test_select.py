"""Test the BLE Sensor select component."""
from unittest.mock import MagicMock, patch
import pytest

from homeassistant.const import STATE_UNAVAILABLE
from custom_components.ble_sensor.select import BLESelect
from custom_components.ble_sensor.coordinator import BLESensorDataUpdateCoordinator

async def test_select_options(hass_mock, mock_config_entry):
    """Test select options and state."""
    coordinator = BLESensorDataUpdateCoordinator(
        hass_mock,
        mock_config_entry,
        update_interval=30
    )
    
    select = BLESelect(
        coordinator,
        "test_mode",
        "Test Mode",
        "mode",
        ["Normal", "Smart", "Custom"]
    )

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
    
    select = BLESelect(
        coordinator,
        "test_mode",
        "Test Mode",
        "mode",
        ["Normal", "Smart", "Custom"]
    )

    # Mock coordinator's async_set_option method
    coordinator.async_set_option = MagicMock()
    
    # Test selecting an option
    await select.async_select_option("Smart")
    coordinator.async_set_option.assert_called_once_with("mode", "Smart")

async def test_select_invalid_option(hass_mock, mock_config_entry):
    """Test selecting invalid option."""
    coordinator = BLESensorDataUpdateCoordinator(
        hass_mock,
        mock_config_entry,
        update_interval=30
    )
    
    select = BLESelect(
        coordinator,
        "test_mode",
        "Test Mode",
        "mode",
        ["Normal", "Smart", "Custom"]
    )

    # Test selecting invalid option
    with pytest.raises(ValueError):
        await select.async_select_option("Invalid")