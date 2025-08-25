from homeassistant.config_entries import HomeAssistantConfigEntries


class HomeAssistant:
    def __init__(self):
        self.config_entries = HomeAssistantConfigEntries()
        self.data = {}

class Config:
    pass

def callback(func):
    return func
