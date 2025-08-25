from homeassistant.components.sensor.const import (SensorDeviceClass,
                                                   SensorStateClass)
from homeassistant.helpers.entity import SensorEntityDescription


class SensorEntity:
    """Base class for sensor entities."""

    def __init__(self):
        """Initialize sensor entity."""
        self._attr_name = None
        self._attr_unique_id = None
        self._attr_device_info = None
        self.entity_description = None

    @property
    def name(self):
        """Return the name of the entity."""
        return self._attr_name

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return self._attr_unique_id

    @property
    def available(self):
        """Return if the entity is available."""
        return True

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        return None
