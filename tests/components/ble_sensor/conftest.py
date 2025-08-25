"""Test configuration for ble_sensor."""
from dataclasses import dataclass, field
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from custom_components.ble_sensor.utils.const import CONF_DEVICE_TYPE, DOMAIN
from homeassistant.const import CONF_MAC, CONF_NAME


@dataclass
class MockConfigEntry:
    """Mock config entry."""
    domain: str
    data: Dict[str, Any]
    entry_id: str = "test_entry_id"
    title: str = "Test Device"
    options: Dict[str, Any] = field(default_factory=dict)

@pytest.fixture
def hass_mock():
    """Mock Home Assistant instance."""
    return MagicMock()

@pytest.fixture
def mock_bluetooth(hass_mock):
    """Mock bluetooth."""
    with patch("homeassistant.components.bluetooth.async_scanner_count", return_value=1), \
         patch("homeassistant.components.bluetooth.async_discovered_service_info", return_value=[]):
        yield

@pytest.fixture
def mock_bleak():
    """Mock bleak client."""
    with patch("bleak.BleakClient") as mock:
        client = MagicMock()
        mock.return_value.__aenter__.return_value = client
        yield client

@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_MAC: "00:11:22:33:44:55",
            CONF_DEVICE_TYPE: "petkit_fountain",
            CONF_NAME: "Test Device"
        }
    )
