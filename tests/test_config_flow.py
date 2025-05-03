"""Test the BLE Sensor config flow."""
from unittest.mock import patch
import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_MAC
from custom_components.ble_sensor.config_flow import BLESensorConfigFlow
from custom_components.ble_sensor.utils.const import CONF_DEVICE_TYPE, DOMAIN

async def test_form(hass_mock, mock_bluetooth):
    """Test we get the form."""
    flow = BLESensorConfigFlow()
    flow.hass = hass_mock

    result = await flow.async_step_user(user_input=None)
    assert result["type"] == "form"
    assert result["step_id"] == "user"

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

async def test_invalid_mac(hass_mock, mock_bluetooth):
    """Test invalid MAC address handling."""
    flow = BLESensorConfigFlow()
    flow.hass = hass_mock

    # Test form submission with invalid MAC
    result = await flow.async_step_user(
        user_input={
            CONF_MAC: "invalid_mac",
            CONF_DEVICE_TYPE: "petkit_fountain",
        }
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_mac"}