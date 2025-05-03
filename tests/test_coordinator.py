"""Test the BLE Sensor coordinator."""
from unittest.mock import patch, MagicMock, AsyncMock
import pytest
from datetime import timedelta
from asyncio import Future

from homeassistant.core import HomeAssistant
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak, BluetoothChange
from custom_components.ble_sensor.coordinator import BLESensorDataUpdateCoordinator
from custom_components.ble_sensor.utils.const import DOMAIN, CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL

def create_mock_coro(return_value=None):
    """Create a mock coroutine function."""
    future = Future()
    future.set_result(return_value)
    return future

@pytest.fixture
def mock_device_type():
    """Mock device type."""
    device_type = MagicMock()
    device_type.requires_polling.return_value = True
    device_type.create_device.return_value = MagicMock()
    # Mock connect_and_get_data as an AsyncMock
    device_type.connect_and_get_data = AsyncMock(return_value={"test_key": "test_value"})
    return device_type

@pytest.fixture
def mock_ble_connection():
    """Mock BLE connection."""
    with patch("custom_components.ble_sensor.utils.bluetooth.BLEConnection") as mock:
        connection = AsyncMock()
        mock.return_value = connection
        yield connection

@pytest.fixture
def mock_bluetooth(hass):
    """Mock bluetooth."""
    with patch("homeassistant.components.bluetooth.async_get_scanner") as mock_scanner, \
         patch("homeassistant.components.bluetooth.async_scanner_count") as mock_scanner_count, \
         patch("habluetooth.BluetoothManager") as mock_bt_manager, \
         patch("homeassistant.components.bluetooth.api._get_manager", return_value=MagicMock()), \
         patch("homeassistant.components.bluetooth.async_ble_device_from_address", return_value=MagicMock()):
            
        mock_scanner_count.return_value = 1
        mock_scanner.return_value.discovered_devices = []
        mock_bt_manager.return_value = MagicMock()
        yield mock_scanner.return_value

async def test_coordinator_update(hass_mock, mock_config_entry, mock_device_type, mock_ble_connection, mock_bluetooth):
    """Test coordinator update functionality."""
    with patch("custom_components.ble_sensor.coordinator.get_device_type", return_value=mock_device_type):
        coordinator = BLESensorDataUpdateCoordinator(
            hass_mock,
            mock_config_entry
        )

        # Set up mock device data
        mock_data = {"test_key": "test_value"}
        device_id = coordinator.device_configs[0].device_id
        coordinator._device_data = {device_id: mock_data}
        coordinator._device_status = {device_id: True}
        coordinator._last_update = {device_id: 0}

        # Test successful update
        result = await coordinator._async_update_data()
        
        # The result should match what connect_and_get_data returns
        expected_result = {device_id: mock_data}
        assert result == expected_result
        assert coordinator.last_update_success is True

async def test_coordinator_initialization(hass_mock, mock_config_entry, mock_device_type, mock_ble_connection):
    """Test coordinator initialization."""
    with patch("custom_components.ble_sensor.coordinator.get_device_type", return_value=mock_device_type):
        coordinator = BLESensorDataUpdateCoordinator(
            hass_mock,
            mock_config_entry
        )
        
        assert coordinator.domain == DOMAIN
        assert coordinator.entry_id == mock_config_entry.entry_id
        assert len(coordinator.device_configs) == 1
        assert coordinator.device_configs[0].device_id == f"ble_sensor_{coordinator.mac_address}"

        # Test device availability checking
        device_id = coordinator.device_configs[0].device_id
        assert coordinator.is_device_available(device_id) is False
        coordinator._device_status[device_id] = True
        assert coordinator.is_device_available(device_id) is True

@pytest.mark.asyncio
async def test_coordinator_stop(hass_mock, mock_config_entry, mock_device_type, mock_ble_connection):
    """Test coordinator cleanup on stop."""
    with patch("custom_components.ble_sensor.coordinator.get_device_type", return_value=mock_device_type):
        coordinator = BLESensorDataUpdateCoordinator(
            hass_mock,
            mock_config_entry
        )
        
        # Set up test state
        coordinator._handlers = [MagicMock()]
        coordinator._initialization_complete = True
        coordinator.ble_connection = mock_ble_connection
        
        await coordinator.async_stop()
        
        # Verify cleanup
        assert len(coordinator._handlers) == 0
        assert coordinator._initialization_complete is False
        assert mock_ble_connection.stop.await_count == 1  # Using await_count for AsyncMock