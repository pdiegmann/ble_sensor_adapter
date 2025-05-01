from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from typing import Optional, Dict, Any

# --- Base Parser Class ---
class BaseParser:
    """Base class for BLE data parsers."""
    def parse(self, service_info: BluetoothServiceInfoBleak) -> Optional[Dict[str, Any]]:
        """Parse advertisement data. Must be implemented by subclasses."""
        raise NotImplementedError
