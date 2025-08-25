class EntityDescription:
    def __init__(self, key, name, device_class=None, state_class=None, native_unit_of_measurement=None, entity_category=None, icon=None, options=None):
        self.key = key
        self.name = name
        self.device_class = device_class
        self.state_class = state_class
        self.native_unit_of_measurement = native_unit_of_measurement
        self.entity_category = entity_category
        self.icon = icon
        self.options = options

class SensorEntityDescription(EntityDescription):
    pass

class BinarySensorEntityDescription(EntityDescription):
    pass

class SwitchEntityDescription(EntityDescription):
    pass

class SelectEntityDescription(EntityDescription):
    pass
