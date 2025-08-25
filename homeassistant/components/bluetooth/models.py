class BluetoothServiceInfoBleak:
    def __init__(self, address, name, rssi, manufacturer_data, service_data, service_uuids, source, device, time):
        self.address = address
        self.name = name
        self.rssi = rssi
        self.manufacturer_data = manufacturer_data
        self.service_data = service_data
        self.service_uuids = service_uuids
        self.source = source
        self.device = device
        self.time = time


