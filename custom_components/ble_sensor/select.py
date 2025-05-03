import logging
from typing import Any, Dict
from custom_components.ble_sensor.devices.base import DeviceType
from custom_components.ble_sensor.devices.device import async_get_ble_device
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from custom_components.ble_sensor.coordinator import BLESensorCoordinator
from custom_components.ble_sensor.utils.const import CONF_DEVICE_TYPE, CONF_MAC, DOMAIN
from custom_components.ble_sensor.devices import get_device_type
from custom_components.ble_sensor.utils.const import KEY_PF_MODE
from homeassistant.components.select import SelectEntity, SelectEntityDescription

from custom_components.ble_sensor.entity import BaseDeviceEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: BLESensorCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Get device type
    device_type = get_device_type(entry.data[CONF_DEVICE_TYPE])
    ble_device = await async_get_ble_device(hass, entry.data[CONF_MAC])
    
    # Create entities
    _LOGGER.debug("Setting up select entities for device type: %s", device_type.__class__.__name__)
    entities = []
    descriptions = device_type.get_sensor_descriptions()
    _LOGGER.debug("Found %d select descriptions: %s", len(descriptions), descriptions)
    for description in descriptions:
        entity = BLESelectEntity(coordinator, description, ble_device)
        entities.append(entity)
            
    if entities:
        _LOGGER.debug("Adding %d select entities", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.debug("No select entities to add for this device type.")

class BLESelectEntity(BaseDeviceEntity, SelectEntity):
    """Representation of a BLE select."""

    def __init__(self, coordinator: BLESensorCoordinator, description: SelectEntityDescription, device: Dict[str, Any]):
        """Initialize the BLE select."""
        super().__init__(coordinator, description, device)

    @property
    def current_option(self):
        """Return the current selected option."""
        return self.coordinator.data.get(self._key)

    async def async_select_option(self, option):
        """Change the selected option."""
        if self._key == KEY_PF_MODE:  # use self._key here
            await self.coordinator.device_type.async_set_mode(
                self.coordinator.ble_connection.client, option
            )
        await self.coordinator.async_request_refresh()
        