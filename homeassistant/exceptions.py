class HomeAssistantError(Exception):
    """Base exception for Home Assistant."""
    pass

class ConfigEntryNotReady(HomeAssistantError):
    """Raised when a config entry is not ready."""
    pass
