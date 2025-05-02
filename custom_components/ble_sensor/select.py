import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from custom_components.ble_sensor.coordinator import BLESensorDataUpdateCoordinator
from custom_components.ble_sensor.utils.const import CONF_DEVICE_TYPE, DOMAIN
from custom_components.ble_sensor.devices.device_types import get_device_type
from custom_components.ble_sensor.utils.const import KEY_PF_MODE
from homeassistant.components.select import SelectEntity

from custom_components.ble_sensor.entity import BLESensorEntity

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: BLESensorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Get device type
    device_type = get_device_type(entry.data[CONF_DEVICE_TYPE])
    
    # Create entities
    _LOGGER.debug("Setting up select entities for device type: %s", device_type.__class__.__name__)
    entities = []
    select_descriptions = device_type.get_select_descriptions()
    _LOGGER.debug("Found %d select descriptions: %s", len(select_descriptions), select_descriptions)
    for description in select_descriptions:
        entity = BLESelectEntity(coordinator, description)
        entities.append(entity)
            
    if entities:
        _LOGGER.debug("Adding %d select entities", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.debug("No select entities to add for this device type.")

class BLESelectEntity(BLESensorEntity, SelectEntity):
    """Representation of a BLE select."""

    def __init__(self, coordinator, description):
        """Initialize the BLE select."""
        super().__init__(coordinator, description)
        self._attr_options = description.options

    @property
    def current_option(self):
        """Return the current selected option."""
        if not self.coordinator.data:
            return None
        
        return self.coordinator.data.get(self._key)  # use self._key here

    async def async_select_option(self, option):
        """Change the selected option."""
        if self._key == KEY_PF_MODE:  # use self._key here
            await self.coordinator.device_type.async_set_mode(
                self.coordinator.ble_connection.client, option
            )
        await self.coordinator.async_request_refresh()