from typing import Generic, TypeVar

T = TypeVar("T")

class DataUpdateCoordinator(Generic[T]):
    def __init__(self, hass, logger, name, update_interval=None, update_method=None):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.update_method = update_method or self._async_update_data
        self.data = None
    
    async def _async_update_data(self):
        """Default update method - to be overridden by subclasses."""
        return {}

    async def async_refresh(self):
        self.data = await self.update_method()
        return self.data

class UpdateFailed(Exception):
    pass


