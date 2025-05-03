import logging
from custom_components.ble_sensor.devices.base import DeviceType
from custom_components.ble_sensor.devices.device import async_get_ble_device
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from custom_components.ble_sensor.coordinator import BLESensorCoordinator
from custom_components.ble_sensor.utils.const import CONF_DEVICE_TYPE, CONF_MAC, DOMAIN
from custom_components.ble_sensor.devices import get_device_type
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from custom_components.ble_sensor.utils.const import KEY_PF_DND_STATE, KEY_PF_POWER_STATUS
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
    ble_device = await async_get_ble_device(entry.data[CONF_MAC])
    
    # Create entities
    _LOGGER.debug("Setting up switch entities for device type: %s", device_type.__class__.__name__)
    entities = []
    switch_descriptions = device_type.get_switch_descriptions()
    _LOGGER.debug("Found %d switch descriptions: %s", len(switch_descriptions), switch_descriptions)
    for description in switch_descriptions:
        entity = BLESwitchEntity(coordinator, description, ble_device)
        entities.append(entity)
            
    if entities:
        _LOGGER.debug("Adding %d switch entities", len(entities))
        async_add_entities(entities)
    else:
        _LOGGER.debug("No switch entities to add for this device type.")

class BLESwitchEntity(BaseDeviceEntity, SwitchEntity):
    """Representation of a BLE switch."""

    def __init__(self, coordinator: BLESensorCoordinator, description: SwitchEntityDescription, device: DeviceType):
        """Initialize the BLE switch."""
        super().__init__(coordinator, description, device)

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self.as_bool(self.native_value)

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

        