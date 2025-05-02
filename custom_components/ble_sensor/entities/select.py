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
    entities = []
    for description in device_type.get_sensor_descriptions():
        entity = BLESelectEntity(coordinator, description)
        entities.append(entity)
            
    if entities:
        async_add_entities(entities)

class BLESelectEntity(BLESensorEntity, SelectEntity):
    """Representation of a BLE select."""

    def __init__(self, coordinator, description):
        """Initialize the BLE select."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{coordinator.device.name} {description.name}"
        self._attr_unique_id = f"{coordinator.device.address}_{description.key}"
        self._attr_device_info = coordinator.device_info
        self._attr_options = description.options

    @property
    def current_option(self):
        """Return the current selected option."""
        return self.coordinator.data.get(self.entity_description.key)

    async def async_select_option(self, option):
        """Change the selected option."""
        if self.entity_description.key == KEY_PF_MODE:
            await self.coordinator.device_type.async_set_mode(
                self.coordinator.client, option
            )
        await self.coordinator.async_request_refresh()