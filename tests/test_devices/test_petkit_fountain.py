"""Test the Petkit Fountain device implementation."""
import pytest
from unittest.mock import MagicMock, patch

from custom_components.ble_sensor.devices.petkit_fountain import PetkitFountainData
from custom_components.ble_sensor.utils.const import (
    KEY_PF_BATTERY,
    KEY_PF_MODE,
    KEY_PF_POWER_STATUS,
    KEY_PF_DND_STATE,
)

@pytest.fixture
def mock_raw_data():
    """Mock raw data from device."""
    return {
        KEY_PF_BATTERY: 75,
        KEY_PF_MODE: 2,  # Smart mode
        KEY_PF_POWER_STATUS: 1,  # On
        KEY_PF_DND_STATE: 0,  # Off
    }

def test_parse_data(mock_raw_data):
    """Test parsing of raw device data."""
    device_data = PetkitFountainData(raw_data=mock_raw_data)
    
    assert device_data._parsed_data[KEY_PF_BATTERY] == 75
    assert device_data._parsed_data[KEY_PF_MODE] == "Smart"
    assert device_data._parsed_data[KEY_PF_POWER_STATUS] == True
    assert device_data._parsed_data[KEY_PF_DND_STATE] == False

def test_parse_data_battery_limits():
    """Test battery value limiting."""
    # Test battery value below 0
    device_data = PetkitFountainData(raw_data={KEY_PF_BATTERY: -10})
    assert device_data._parsed_data[KEY_PF_BATTERY] == 0

    # Test battery value above 100
    device_data = PetkitFountainData(raw_data={KEY_PF_BATTERY: 150})
    assert device_data._parsed_data[KEY_PF_BATTERY] == 100

def test_parse_data_mode():
    """Test mode parsing."""
    # Test normal mode
    device_data = PetkitFountainData(raw_data={KEY_PF_MODE: 1})
    assert device_data._parsed_data[KEY_PF_MODE] == "Normal"

    # Test smart mode
    device_data = PetkitFountainData(raw_data={KEY_PF_MODE: 2})
    assert device_data._parsed_data[KEY_PF_MODE] == "Smart"