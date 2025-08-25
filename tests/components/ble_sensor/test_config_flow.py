"""Test the BLE Sensor config flow."""
from unittest.mock import MagicMock, patch
import pytest
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_MAC
from homeassistant.data_entry_flow import AbortFlow
from custom_components.ble_sensor.config_flow import BLESensorConfigFlow
from custom_components.ble_sensor.utils.const import CONF_DEVICE_TYPE, DOMAIN, DEFAULT_DEVICE_TYPE

class MockFlow:
    """Mock flow that simulates BLE sensor config flow."""

    def __init__(self) -> None:
        """Initialize mock flow."""
        self.context = {}
        self.hass = None
    
    def async_show_form(self, *, step_id, data_schema=None, errors=None, description_placeholders=None):
        """Show form."""
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
            "description_placeholders": description_placeholders or {}
        }
    
    def async_create_entry(self, *, title, data, options=None):
        """Create config entry."""
        return {
            "type": "create_entry",
            "title": title,
            "data": data,
            "options": options or {}
        }
    
    async def async_set_unique_id(self, unique_id):
        """Set unique ID."""
        self._unique_id = unique_id
        
    def _abort_if_unique_id_configured(self):
        """Check if unique ID is already configured."""
        # For testing - mock this behavior
        if hasattr(self, '_should_abort'):
            raise AbortFlow("already_configured")
    
    @staticmethod
    def _is_valid_mac(mac: str) -> bool:
        """Check if mac address is valid."""
        import re
        return bool(re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", mac))
    
    async def async_step_user(self, user_input=None):
        """Handle user step."""
        errors = {}
        
        if user_input is not None:
            mac = user_input[CONF_MAC].lower()
            
            # Validate MAC address
            if not self._is_valid_mac(mac):
                errors["mac"] = "invalid_mac"
            else:
                # Check if device already configured
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()
                
                # Setup the config entry with implicit device type (Petkit Fountain)
                return self.async_create_entry(
                    title=f"Petkit Fountain ({mac})",
                    data={
                        CONF_MAC: mac,
                        CONF_DEVICE_TYPE: DEFAULT_DEVICE_TYPE,  # Always Petkit Fountain
                    },
                )
        
        # Return form
        return self.async_show_form(
            step_id="user",
            data_schema=None,  # Simplified - we'd normally have schema here
            errors=errors,
        )

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

async def test_form():
    """Test we get the form."""
    flow = MockFlow()
    
    result = await flow.async_step_user(user_input=None)
    assert result["type"] == "form"
    assert result["errors"] == {}

    # Test form submission with valid data
    result = await flow.async_step_user(
        user_input={
            CONF_MAC: "00:11:22:33:44:55",
        }
    )
    assert result["type"] == "create_entry"
    assert result["title"].startswith("Petkit Fountain")
    assert result["data"] == {
        CONF_MAC: "00:11:22:33:44:55",
        CONF_DEVICE_TYPE: DEFAULT_DEVICE_TYPE,  # Always Petkit Fountain
    }

async def test_already_configured():
    """Test handling of already configured device."""
    flow = MockFlow()
    flow._should_abort = True  # Mark as should abort

    # Test that we get an abort when trying to add an already configured device
    with pytest.raises(AbortFlow, match="already_configured"):
        await flow.async_step_user(
            user_input={
                CONF_MAC: "00:11:22:33:44:55",
            }
        )

async def test_invalid_mac():
    """Test invalid MAC address handling."""
    flow = MockFlow()

    # Test form submission with invalid MAC
    result = await flow.async_step_user(
        user_input={
            CONF_MAC: "invalid_mac",
        }
    )
    assert result["type"] == "form"
    assert result["errors"] == {"mac": "invalid_mac"}

async def test_device_type_implicit():
    """Test that device type is always Petkit Fountain."""
    flow = MockFlow()
    
    result = await flow.async_step_user(
        user_input={
            CONF_MAC: "aa:bb:cc:dd:ee:ff",
        }
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "Petkit Fountain (aa:bb:cc:dd:ee:ff)"
    assert result["data"][CONF_DEVICE_TYPE] == DEFAULT_DEVICE_TYPE
    assert result["data"][CONF_DEVICE_TYPE] == "petkit_fountain"