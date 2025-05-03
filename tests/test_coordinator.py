"""Test the BLE Sensor coordinator."""
from unittest.mock import patch, MagicMock
import pytest

from homeassistant.core import HomeAssistant
from custom_components.ble_sensor.coordinator import BLESensorDataUpdateCoordinator
from custom_components.ble_sensor.utils.const import DOMAIN

async def test_coordinator_update(hass_mock, mock_bleak, mock_config_entry):
    """Test coordinator update functionality."""
    coordinator = BLESensorDataUpdateCoordinator(
        hass_mock,
        mock_config_entry,
        update_interval=30
    )

    # Test successful update
    mock_bleak.read_gatt_char.return_value = bytes([0x01, 0x02, 0x03])
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True

    # Test failed update
    mock_bleak.read_gatt_char.side_effect = Exception("Connection failed")
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False

async def test_coordinator_initialization(hass_mock, mock_config_entry):
    """Test coordinator initialization."""
    coordinator = BLESensorDataUpdateCoordinator(
        hass_mock,
        mock_config_entry,
        update_interval=30
    )
    
    assert coordinator.domain == DOMAIN
    assert coordinator.config_entry == mock_config_entry
    assert coordinator.update_interval.total_seconds() == 30

@pytest.mark.asyncio
async def test_coordinator_stop(hass_mock, mock_config_entry):
    """Test coordinator cleanup on stop."""
    coordinator = BLESensorDataUpdateCoordinator(
        hass_mock,
        mock_config_entry,
        update_interval=30
    )
    
    # Mock the internal state
    coordinator._client = MagicMock()
    
    await coordinator.async_stop()
    assert coordinator._client is None