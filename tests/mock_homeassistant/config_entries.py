class ConfigEntry:
    def __init__(self, entry_id, data, options=None):
        self.entry_id = entry_id
        self.data = data
        self.options = options if options is not None else {}
        self.update_listeners = []

    def add_update_listener(self, listener):
        self.update_listeners.append(listener)

    async def async_on_unload(self, func):
        pass

class ConfigEntriesFlowManager:
    async def async_forward_entry_setups(self, entry, platforms):
        pass

    async def async_reload(self, entry_id):
        pass

    async def async_forward_entry_unload(self, entry, platform):
        pass

class HomeAssistantConfigEntries:
    def __init__(self):
        self.flow = ConfigEntriesFlowManager()

    async def async_forward_entry_setups(self, entry, platforms):
        await self.flow.async_forward_entry_setups(entry, platforms)

    async def async_reload(self, entry_id):
        await self.flow.async_reload(entry_id)

    async def async_forward_entry_unload(self, entry, platform):
        await self.flow.async_forward_entry_unload(entry, platform)
