# Config entry sources
SOURCE_USER = "user"
SOURCE_BLUETOOTH = "bluetooth"
SOURCE_DISCOVERY = "discovery"
SOURCE_HOMEKIT = "homekit"
SOURCE_IMPORT = "import"

class ConfigFlow:
    """Base class for config flows."""
    VERSION = 1
    
    def __init_subclass__(cls, *, domain, **kwargs):
        """Initialize subclass with domain."""
        super().__init_subclass__(**kwargs)
        cls._domain = domain
    
    def async_show_form(self, *, step_id, data_schema=None, errors=None, description_placeholders=None):
        """Show form."""
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
            "description_placeholders": description_placeholders or {}
        }
    
    def async_create_entry(self, *, title, data, options=None):
        """Create config entry."""
        return {
            "type": "create_entry",
            "title": title,
            "data": data,
            "options": options or {}
        }
    
    def _abort_if_unique_id_configured(self):
        """Check if unique ID is already configured."""
        pass
        
    async def async_set_unique_id(self, unique_id):
        """Set unique ID."""
        self._unique_id = unique_id

class OptionsFlow:
    """Base class for options flows."""
    
    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry
    
    def async_show_form(self, *, step_id, data_schema=None, errors=None):
        """Show form."""
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {}
        }
    
    def async_create_entry(self, *, title="", data):
        """Create options entry."""
        return {
            "type": "create_entry",
            "title": title,
            "data": data
        }

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


