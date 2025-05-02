import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from custom_components.ble_sensor.coordinator import BLESensorDataUpdateCoordinator
from custom_components.ble_sensor.utils.const import CONF_DEVICE_TYPE, DOMAIN
from custom_components.ble_sensor.devices.device_types import get_device_type
from homeassistant.components.switch import SwitchEntity
from custom_components.ble_sensor.utils.const import KEY_PF_DND_STATE, KEY_PF_POWER_STATUS
from custom_components.ble_sensor.entities.entity import BLESensorEntity

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
    for description in device_type.get_switch_descriptions():
        entity = BLESwitchEntity(coordinator, description)
        entities.append(entity)
            
    if entities:
        async_add_entities(entities)


class BLESwitchEntity(BLESensorEntity, SwitchEntity):
    """Representation of a BLE switch."""

    def __init__(self, coordinator, description):
        """Initialize the BLE switch."""
        super().__init__(coordinator, description)

    @property
    def is_on(self):
        """Return true if the switch is on."""
        if not self.coordinator.data:
            return None
            
        state = self.coordinator.data.get(self._key)
        if state is None:
            return None
            
        # Handle different types of state values
        if isinstance(state, bool):
            return state
        elif isinstance(state, str):
            return state.lower() in ("on", "true", "1")
        return bool(state)

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        if self._key == KEY_PF_POWER_STATUS:
            await self.coordinator.device_type.async_set_power_status(
                self.coordinator.ble_connection.client, True
            )
        elif self._key == KEY_PF_DND_STATE:
            await self.coordinator.device_type.async_set_dnd_state(
                self.coordinator.ble_connection.client, True
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        if self._key == KEY_PF_POWER_STATUS:
            await self.coordinator.device_type.async_set_power_status(
                self.coordinator.ble_connection.client, False
            )
        elif self._key == KEY_PF_DND_STATE:
            await self.coordinator.device_type.async_set_dnd_state(
                self.coordinator.ble_connection.client, False
            )
        await self.coordinator.async_request_refresh()