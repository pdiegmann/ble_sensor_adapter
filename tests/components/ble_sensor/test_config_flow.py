"""Test the BLE Sensor config flow."""
from unittest.mock import MagicMock, patch
import pytest
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_MAC
from homeassistant.data_entry_flow import AbortFlow
from custom_components.ble_sensor.config_flow import BLESensorConfigFlow
from custom_components.ble_sensor.utils.const import CONF_DEVICE_TYPE, DOMAIN

class MockFlow(BLESensorConfigFlow):
    """Mock flow that can have a dict context."""

    def __init__(self) -> None:
        """Initialize mock flow."""
        super().__init__()
        self.context = {}

@pytest.fixture
def mock_bluetooth(hass):
    """Mock bluetooth."""
    with patch("homeassistant.components.bluetooth.async_get_scanner") as mock_scanner, \
         patch("homeassistant.components.bluetooth.async_scanner_count") as mock_scanner_count, \
         patch("habluetooth.BluetoothManager") as mock_bt_manager, \
         patch("homeassistant.components.bluetooth.api._get_manager", return_value=MagicMock()), \
         patch("homeassistant.components.bluetooth.async_discovered_service_info", return_value=[]):
            
        mock_scanner_count.return_value = 1
        mock_scanner.return_value.discovered_devices = []
        mock_bt_manager.return_value = MagicMock()
        yield mock_scanner.return_value

async def test_form(hass_mock, mock_bluetooth):
    """Test we get the form."""
    flow = MockFlow()
    flow.hass = hass_mock

    # Mock config entries to return no existing entries
    mock_config_entries = MagicMock()
    mock_config_entries.async_entry_for_domain_unique_id.return_value = None
    hass_mock.config_entries = mock_config_entries
    
    result = await flow.async_step_user(user_input=None)
    assert result["type"] == "form"
    assert result["errors"] == {}

    # Test form submission with valid data
    with patch(
        "custom_components.ble_sensor.config_flow.BLESensorConfigFlow._is_valid_mac",
        return_value=True,
    ):
        result = await flow.async_step_user(
            user_input={
                CONF_MAC: "00:11:22:33:44:55",
                CONF_DEVICE_TYPE: "petkit_fountain",
            }
        )
        assert result["type"] == "create_entry"
        assert result["title"].startswith("Petkit Fountain")
        assert result["data"] == {
            CONF_MAC: "00:11:22:33:44:55",
            CONF_DEVICE_TYPE: "petkit_fountain",
        }

async def test_already_configured(hass_mock, mock_bluetooth):
    """Test handling of already configured device."""
    flow = MockFlow()
    flow.hass = hass_mock

    # Mock config entries to return an existing entry
    mock_entry = MagicMock()
    mock_entry.data = {
        CONF_MAC: "00:11:22:33:44:55",
        CONF_DEVICE_TYPE: "petkit_fountain",
    }
    mock_config_entries = MagicMock()
    mock_config_entries.async_entry_for_domain_unique_id.return_value = mock_entry
    hass_mock.config_entries = mock_config_entries

    # Test that we get an abort when trying to add an already configured device
    with patch(
        "custom_components.ble_sensor.config_flow.BLESensorConfigFlow._is_valid_mac",
        return_value=True,
    ):
        with pytest.raises(AbortFlow, match="already_configured"):
            result = await flow.async_step_user(
                user_input={
                    CONF_MAC: "00:11:22:33:44:55",
                    CONF_DEVICE_TYPE: "petkit_fountain",
                }
            )

async def test_invalid_mac(hass_mock, mock_bluetooth):
    """Test invalid MAC address handling."""
    flow = MockFlow()
    flow.hass = hass_mock

    # Mock config entries to return no existing entries
    mock_config_entries = MagicMock()
    mock_config_entries.async_entry_for_domain_unique_id.return_value = None
    hass_mock.config_entries = mock_config_entries

    # Test form submission with invalid MAC
    result = await flow.async_step_user(
        user_input={
            CONF_MAC: "invalid_mac",
            CONF_DEVICE_TYPE: "petkit_fountain",
        }
    )
    assert result["type"] == "form"
    assert result["errors"] == {"mac": "invalid_mac"}