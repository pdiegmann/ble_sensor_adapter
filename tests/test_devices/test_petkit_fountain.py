"""Test the Petkit Fountain device implementation."""
import pytest
from unittest.mock import MagicMock, patch

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