import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from custom_components.ble_sensor.coordinator import BLESensorDataUpdateCoordinator
from custom_components.ble_sensor.utils.const import CONF_DEVICE_TYPE, DOMAIN
from custom_components.ble_sensor.devices.device_types import get_device_type
from homeassistant.components.switch import SwitchEntity
from custom_components.ble_sensor.utils.const import KEY_PF_DND_STATE, KEY_PF_POWER_STATUS
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
        entity = BLESwitchEntity(coordinator, description)
        entities.append(entity)
            
    if entities:
        async_add_entities(entities)


class BLESwitchEntity(BLESensorEntity, SwitchEntity):
    """Representation of a BLE switch."""

    def __init__(self, coordinator, description):
        """Initialize the BLE switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{coordinator.device.name} {description.name}"
        self._attr_unique_id = f"{coordinator.device.address}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self):
        """Return true if the switch is on."""
        state = self.coordinator.data.get(self.entity_description.key)
        return state == "On"

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        if self.entity_description.key == KEY_PF_POWER_STATUS:
            await self.coordinator.device_type.async_set_power_status(
                self.coordinator.client, True
            )
        elif self.entity_description.key == KEY_PF_DND_STATE:
            await self.coordinator.device_type.async_set_dnd_state(
                self.coordinator.client, True
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        if self.entity_description.key == KEY_PF_POWER_STATUS:
            await self.coordinator.device_type.async_set_power_status(
                self.coordinator.client, False
            )
        elif self.entity_description.key == KEY_PF_DND_STATE:
            await self.coordinator.device_type.async_set_dnd_state(
                self.coordinator.client, False
            )
        await self.coordinator.async_request_refresh()