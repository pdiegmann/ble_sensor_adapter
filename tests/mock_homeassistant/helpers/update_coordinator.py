from typing import Generic, TypeVar

T = TypeVar("T")

class DataUpdateCoordinator(Generic[T]):
    def __init__(self, hass, logger, name, update_interval, update_method):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.update_method = update_method
        self.data = None

    async def async_refresh(self):
        self.data = await self.update_method()
        return self.data

class UpdateFailed(Exception):
    pass
