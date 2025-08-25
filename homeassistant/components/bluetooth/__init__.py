from .models import BluetoothServiceInfoBleak

def async_ble_device_from_address(*args, **kwargs):
    pass

def async_register_callback(*args, **kwargs):
    pass

def async_track_unavailable(*args, **kwargs):
    pass

def async_scanner_count(*args, **kwargs):
    return 1

class BluetoothChange:
    ADDRESS = "address"
    NAME = "name"
    RSSI = "rssi"
    ADVERTISEMENT = "advertisement"

class BluetoothScanningMode:
    ACTIVE = "active"
    PASSIVE = "passive"


