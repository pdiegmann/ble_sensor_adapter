"""Implementation for Petkit Fountain device type."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, Union, override
import binascii
from bleak_retry_connector import establish_connection

from homeassistant.components.sensor import (
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass
)
from homeassistant.components.binary_sensor import (
    BinarySensorEntityDescription,
    BinarySensorDeviceClass
)
from homeassistant.components.switch import (
    SwitchEntityDescription,
)
from homeassistant.components.select import (
    SelectEntityDescription,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTime,
    EntityCategory
)

from bleak import BleakClient
from bleak.exc import BleakError

from custom_components.ble_sensor.devices.device import BLEDevice
from custom_components.ble_sensor.utils.const import (
    KEY_PF_MODEL_CODE,
    KEY_PF_MODEL_NAME,
    KEY_PF_ALIAS,
    KEY_PF_BATTERY,
    KEY_PF_POWER_STATUS,
    KEY_PF_MODE,
    KEY_PF_DND_STATE,
    KEY_PF_WARN_BREAKDOWN,
    KEY_PF_WARN_WATER,
    KEY_PF_WARN_FILTER,
    KEY_PF_PUMP_RUNTIME,
    KEY_PF_FILTER_PERCENT,
    KEY_PF_RUNNING_STATUS,
)
from custom_components.ble_sensor.devices.base import DeviceType

_LOGGER = logging.getLogger(__name__)

# Petkit Fountain BLE characteristics and commands
PETKIT_WRITE_UUID = "0000aaa2-0000-1000-8000-00805f9b34fb"
PETKIT_READ_UUID = "0000aaa1-0000-1000-8000-00805f9b34fb"

# Command codes
CMD_GET_BATTERY = 66
CMD_INIT_DEVICE = 73
CMD_SET_DATETIME = 84
CMD_GET_DEVICE_SYNC = 86
CMD_GET_DEVICE_INFO = 200
CMD_GET_DEVICE_TYPE = 201
CMD_GET_DEVICE_STATE = 210
CMD_GET_DEVICE_CONFIG = 211
CMD_GET_DEVICE_DETAILS = 213
CMD_SET_DEVICE_MODE = 220
CMD_SET_DEVICE_CONFIG = 221
CMD_RESET_FILTER = 222

# Response codes
RESP_DEVICE_DETAILS = 213
RESP_DEVICE_STATE = 210
RESP_DEVICE_CONFIG = 211
RESP_BATTERY = 66
RESP_DEVICE_INFO = 200
RESP_DEVICE_TYPE = 201
RESP_DEVICE_SYNC = 86
RESP_INIT_DEVICE = 73

# Command retries and timeouts
MAX_COMMAND_RETRIES = 3
INIT_COMMAND_TIMEOUT = 30  # seconds for initialization commands
NORMAL_COMMAND_TIMEOUT = 10  # seconds for normal operation commands
RETRY_DELAY = 2  # seconds between retries

class PetkitFountain(DeviceType):
    """Petkit Fountain device type implementation."""

    def __init__(self) -> None:
        """Initialize the device type."""
        super().__init__()
        self._name = "petkit_fountain"
        self._description = "Petkit Fountain"
        self._sequence = 0
        self._device_id_bytes: Optional[bytes] = None
        self._secret: Optional[bytes] = None
        self._notification_queue: Optional[asyncio.Queue] = None
        self._expected_responses: Dict[int, asyncio.Future] = {}
        self._is_initialized = False

    def get_sensor_descriptions(self) -> List[SensorEntityDescription]:
        """Return sensor entity descriptions for this device type."""
        return [
            SensorEntityDescription(
                key=KEY_PF_BATTERY,
                name="Battery",
                device_class=SensorDeviceClass.BATTERY,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=PERCENTAGE,
                entity_category=EntityCategory.DIAGNOSTIC,
                icon=None,
            ),
            SensorEntityDescription(
                key=KEY_PF_FILTER_PERCENT,
                name="Filter Life",
                device_class=None,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement=PERCENTAGE,
                entity_category=EntityCategory.DIAGNOSTIC,
                icon=None,
            ),
            SensorEntityDescription(
                key=KEY_PF_PUMP_RUNTIME,
                name="Pump Runtime",
                device_class=SensorDeviceClass.DURATION,
                state_class=SensorStateClass.TOTAL_INCREASING,
                native_unit_of_measurement=UnitOfTime.SECONDS,
                entity_category=EntityCategory.DIAGNOSTIC,
                icon=None,
            ),
            SensorEntityDescription(
                key=KEY_PF_RUNNING_STATUS,
                name="Status",
                device_class=None,
                state_class=None,
                native_unit_of_measurement=None,
                entity_category=None,
                icon="mdi:water-pump",
            ),
        ]

    def get_binary_sensor_descriptions(self) -> List[BinarySensorEntityDescription]:
        """Return binary sensor entity descriptions for this device type."""
        return [
            BinarySensorEntityDescription(
                key=KEY_PF_WARN_WATER,
                name="Water Warning",
                device_class=BinarySensorDeviceClass.PROBLEM,
                entity_category=EntityCategory.DIAGNOSTIC,
                icon=None,
            ),
            BinarySensorEntityDescription(
                key=KEY_PF_WARN_FILTER,
                name="Filter Warning",
                device_class=BinarySensorDeviceClass.PROBLEM,
                entity_category=EntityCategory.DIAGNOSTIC,
                icon=None,
            ),
            BinarySensorEntityDescription(
                key=KEY_PF_WARN_BREAKDOWN,
                name="Breakdown Warning",
                device_class=BinarySensorDeviceClass.PROBLEM,
                entity_category=EntityCategory.DIAGNOSTIC,
                icon=None,
            ),
        ]
        
    def get_switch_descriptions(self) -> List[SwitchEntityDescription]:
        """Return switch entity descriptions for this device type."""
        return [
            SwitchEntityDescription(
                key=KEY_PF_POWER_STATUS,
                name="Power",
                icon="mdi:power",
            ),
            SwitchEntityDescription(
                key=KEY_PF_DND_STATE,
                name="Do Not Disturb",
                icon="mdi:do-not-disturb",
            ),
        ]
        
    def get_select_descriptions(self) -> List[SelectEntityDescription]:
        """Return select entity descriptions for this device type."""
        return [
            SelectEntityDescription(
                key=KEY_PF_MODE,
                name="Mode",
                options=["Smart", "Normal"],
                icon="mdi:fountain",
            ),
        ]

    def get_characteristics(self) -> List[str]:
        """Return characteristic UUIDs this device uses."""
        return [
            PETKIT_READ_UUID,
            PETKIT_WRITE_UUID,
        ]

    def get_services(self) -> List[str]:
        """Return service UUIDs this device uses."""
        # Return empty list if no specific services needed
        return []

    def requires_polling(self) -> bool:
        """Return True if this device requires polling."""
        return True

    def create_device(self, mac_address: str) -> BLEDevice:
        """Create a device instance for this device type."""
        device = super().create_device(mac_address)
        device.manufacturer = "Petkit"
        device.model = "Smart Fountain"
        return device

    # Command building methods
    @staticmethod
    def _build_command(seq: int, cmd: int, type_val: int, data: list[int]) -> bytes:
        """Builds the byte command to send to the device."""
        checksum = 0
        command_bytes = [85, 170, len(data) + 4, seq, cmd, type_val] + data
        for byte_val in command_bytes[2:]:
            checksum ^= byte_val
        command_bytes.append(checksum)
        return bytes(command_bytes)

    @staticmethod
    def _time_in_bytes() -> list[int]:
        """Get current time formatted as bytes for CMD_SET_DATETIME."""
        now = datetime.now()
        year_bytes = list(int(str(now.year)[i:i+2]) for i in range(0, 4, 2))
        time_data = year_bytes + [now.month, now.day, now.hour, now.minute, now.second]
        return time_data

    def _increment_sequence(self):
        """Increment and wrap the command sequence number."""
        self._sequence = (self._sequence + 1) % 256

    # Methods to handle setting values
    async def async_set_power_status(self, client: BleakClient, state: bool) -> bool:
        """Set the power status of the device."""
        try:
            # Get current state first
            state_payload = await self._send_command_and_wait(
                client, CMD_GET_DEVICE_STATE, 1, [0, 0], RESP_DEVICE_STATE
            )
            
            if not state_payload or len(state_payload) < 12:
                _LOGGER.error("Failed to get device state before setting power")
                return False
                
            # Copy current state and modify the power status byte
            new_state = list(state_payload)
            new_state[0] = 1 if state else 0
            
            # Send command to set state
            await self._send_command_and_wait(
                client, CMD_SET_DEVICE_MODE, 1, new_state, 999
            )
            
            return True
        except Exception as e:
            _LOGGER.error(f"Error setting power status: {e}")
            return False
    
    async def async_set_mode(self, client: BleakClient, mode: str) -> bool:
        """Set the mode of the device."""
        try:
            # Get current state first
            state_payload = await self._send_command_and_wait(
                client, CMD_GET_DEVICE_STATE, 1, [0, 0], RESP_DEVICE_STATE
            )
            
            if not state_payload or len(state_payload) < 12:
                _LOGGER.error("Failed to get device state before setting mode")
                return False
                
            # Copy current state and modify the mode byte
            new_state = list(state_payload)
            new_state[1] = 2 if mode.lower() == "smart" else 1
            
            # Send command to set state
            await self._send_command_and_wait(
                client, CMD_SET_DEVICE_MODE, 1, new_state, 999
            )
            
            return True
        except Exception as e:
            _LOGGER.error(f"Error setting mode: {e}")
            return False
    
    async def async_set_dnd_state(self, client: BleakClient, state: bool) -> bool:
        """Set the Do Not Disturb state of the device."""
        try:
            # Get current config first
            config_payload = await self._send_command_and_wait(
                client, CMD_GET_DEVICE_CONFIG, 1, [0, 0], RESP_DEVICE_CONFIG
            )
            
            if not config_payload or len(config_payload) < 9:
                _LOGGER.error("Failed to get device config before setting DND")
                return False
                
            # Copy current config and modify the DND byte
            new_config = list(config_payload)
            new_config[8] = 1 if state else 0
            
            # Send command to set config
            await self._send_command_and_wait(
                client, CMD_SET_DEVICE_CONFIG, 1, new_config, 999
            )
            
            return True
        except Exception as e:
            _LOGGER.error(f"Error setting DND state: {e}")
            return False

    # The following methods would be used during the fetch_data operation in the coordinator

    async def async_custom_initialization(self, client: BleakClient, data_callback) -> bool:
        """Initialize the Petkit Fountain device with improved error handling."""
        _LOGGER.info("Starting initialization sequence for Petkit Fountain")
        
        if not client or not client.is_connected:
            _LOGGER.error("Cannot initialize: client not connected")
            return False
            
        # Initialize notification queue
        self._notification_queue = asyncio.Queue()
        
        # Set up notification handler
        async def notification_handler(characteristic, data):
            _LOGGER.debug("Received notification: %s", binascii.hexlify(bytes(data)).decode())
            await self._notification_queue.put(bytes(data))
        
        # Start notifications with retry
        for attempt in range(MAX_COMMAND_RETRIES):
            try:
                await client.start_notify(PETKIT_READ_UUID, notification_handler)
                break
            except Exception as ex:
                if attempt == MAX_COMMAND_RETRIES - 1:
                    _LOGGER.error("Failed to start notifications: %s", ex)
                    return False
                _LOGGER.warning(
                    "Failed to start notifications (attempt %d/%d): %s",
                    attempt + 1,
                    MAX_COMMAND_RETRIES,
                    ex
                )
                await asyncio.sleep(RETRY_DELAY)
        
        try:
            # 1. Get Device Details (to get device_id/serial)
            details_payload = await self._send_command_with_retry(
                client,
                CMD_GET_DEVICE_DETAILS,
                1,
                [0, 0],
                RESP_DEVICE_DETAILS,
                timeout=INIT_COMMAND_TIMEOUT
            )
            
            if not details_payload or len(details_payload) < 6:
                _LOGGER.error("Invalid device details response")
                return False
                
            # Extract device ID
            self._device_id_bytes = details_payload[0:6]
            _LOGGER.debug("Device ID/Serial: %s", binascii.hexlify(self._device_id_bytes).decode())
            
            # 2. Init Device (Send secret derived from device_id)
            reversed_id = bytes(reversed(self._device_id_bytes))
            padded_secret = reversed_id + bytes(max(0, 8 - len(reversed_id)))
            self._secret = padded_secret
            
            padded_device_id = self._device_id_bytes + bytes(max(0, 8 - len(self._device_id_bytes)))
            init_data = [0, 0] + list(padded_device_id) + list(self._secret)
            
            init_payload = await self._send_command_with_retry(
                client,
                CMD_INIT_DEVICE,
                1,
                init_data,
                RESP_INIT_DEVICE,
                timeout=INIT_COMMAND_TIMEOUT
            )
            
            # 3. Get Device Sync
            sync_data = [0, 0] + list(self._secret)
            sync_payload = await self._send_command_with_retry(
                client,
                CMD_GET_DEVICE_SYNC,
                1,
                sync_data,
                RESP_DEVICE_SYNC,
                timeout=INIT_COMMAND_TIMEOUT
            )
            
            # 4. Set Datetime (expected to timeout)
            time_data = self._time_in_bytes()
            try:
                await self._send_command_with_retry(
                    client,
                    CMD_SET_DATETIME,
                    1,
                    time_data,
                    999,
                    timeout=5,
                    retries=1
                )
            except asyncio.TimeoutError:
                _LOGGER.debug("Expected timeout for SET_DATETIME command")
            
            self._is_initialized = True
            _LOGGER.info("Petkit initialization complete")
            return True
            
        except Exception as e:
            _LOGGER.error("Error during initialization: %s", e, exc_info=True)
            return False

    async def _send_command_with_retry(
        self, 
        client: BleakClient, 
        cmd: int, 
        type_val: int, 
        data: list[int], 
        response_cmd: int,
        timeout: float = NORMAL_COMMAND_TIMEOUT,
        retries: int = MAX_COMMAND_RETRIES
    ) -> Optional[bytes]:
        """Send command with retry logic."""
        last_error = None
        for attempt in range(retries):
            try:
                if attempt > 0:
                    _LOGGER.debug(
                        "Retrying command %d (attempt %d/%d)",
                        cmd,
                        attempt + 1,
                        retries
                    )
                    await asyncio.sleep(RETRY_DELAY)
                    
                return await self._send_command_and_wait(
                    client, cmd, type_val, data, response_cmd, timeout
                )
            except asyncio.TimeoutError as ex:
                last_error = ex
                _LOGGER.warning(
                    "Timeout sending command %d (attempt %d/%d)",
                    cmd,
                    attempt + 1,
                    retries
                )
            except BleakError as ex:
                last_error = ex
                _LOGGER.warning(
                    "BLE error sending command %d (attempt %d/%d): %s",
                    cmd,
                    attempt + 1,
                    retries,
                    ex
                )
            except Exception as ex:
                last_error = ex
                _LOGGER.error(
                    "Unexpected error sending command %d (attempt %d/%d): %s",
                    cmd,
                    attempt + 1,
                    retries,
                    ex
                )
                
        if last_error:
            _LOGGER.error(
                "Failed to send command %d after %d attempts: %s",
                cmd,
                retries,
                last_error
            )
            raise last_error
            
        return None

    async def _send_command_and_wait(
        self, 
        client: BleakClient, 
        cmd: int, 
        type_val: int, 
        data: list[int], 
        response_cmd: int,
        timeout: float = NORMAL_COMMAND_TIMEOUT
    ) -> Optional[bytes]:
        """Send command and wait for a specific response."""
        if not client or not client.is_connected:
            raise BleakError("Client not connected")
            
        seq = self._sequence
        command_bytes = self._build_command(seq, cmd, type_val, data)
        future = asyncio.Future()
        self._expected_responses[response_cmd] = future
        
        try:
            _LOGGER.debug(
                "Sending command: Seq=%d, Cmd=%d, Type=%d, Data=%s",
                seq,
                cmd,
                type_val,
                binascii.hexlify(bytes(data)).decode()
            )
            await client.write_gatt_char(PETKIT_WRITE_UUID, command_bytes, response=False)
            self._increment_sequence()
            
            # Wait for the response
            try:
                payload = await asyncio.wait_for(future, timeout=timeout)
                _LOGGER.debug(
                    "Received response for command %d: %s",
                    cmd,
                    binascii.hexlify(payload).decode() if payload else None
                )
                return payload
            except asyncio.TimeoutError:
                _LOGGER.warning(
                    "Timeout waiting for response to command %d (timeout=%d)",
                    cmd,
                    timeout
                )
                raise
                
        except Exception as e:
            _LOGGER.error("Error sending command %d: %s", cmd, e)
            raise
        finally:
            # Clean up
            if response_cmd in self._expected_responses:
                del self._expected_responses[response_cmd]

    async def _process_notification(self, data: bytes) -> Dict[str, Any]:
        """Process a notification from the device."""
        if not data or len(data) < 6:
            return {}
            
        # Validate start bytes
        if data[0] != 0x55 or data[1] != 0xAA:
            return {}
            
        # Extract command and payload
        cmd = data[4]
        payload = data[6:-1]  # Skip header and checksum
        
        # Check if this is an expected response
        if cmd in self._expected_responses and not self._expected_responses[cmd].done():
            self._expected_responses[cmd].set_result(payload)
            return {}  # Don't process further here
            
        # Parse the data based on command
        result = {}
        
        if cmd == RESP_DEVICE_STATE:
            if len(payload) >= 12:
                result[KEY_PF_POWER_STATUS] = "On" if payload[0] == 1 else "Off"
                result[KEY_PF_MODE] = "Smart" if payload[1] == 2 else "Normal"
                result[KEY_PF_WARN_BREAKDOWN] = bool(payload[2])
                result[KEY_PF_WARN_WATER] = bool(payload[3])
                result[KEY_PF_WARN_FILTER] = bool(payload[4])
                
                filter_days_remaining = payload[5]
                if len(payload) >= 10:
                    pump_runtime_minutes = int.from_bytes(payload[6:10], byteorder='little')
                    result[KEY_PF_PUMP_RUNTIME] = pump_runtime_minutes * 60  # Convert to seconds
                
                # Calculate filter percentage
                if filter_days_remaining <= 0:
                    result[KEY_PF_FILTER_PERCENT] = 0
                else:
                    result[KEY_PF_FILTER_PERCENT] = round(max(0, min(100, (filter_days_remaining / 30) * 100)))
                
                if len(payload) >= 11:
                    result[KEY_PF_RUNNING_STATUS] = "Running" if payload[10] == 1 else "Idle"
        
        elif cmd == RESP_DEVICE_CONFIG:
            if len(payload) >= 9:
                dnd_switch = payload[8]
                result[KEY_PF_DND_STATE] = "On" if dnd_switch == 1 else "Off"
        
        elif cmd == RESP_BATTERY:
            if len(payload) >= 1:
                result[KEY_PF_BATTERY] = payload[0]
                
        return result
        
    @override
    async def _get_data(self, ble_device, uuid: Optional[str] = None) -> Dict[str, Any]|None:
        client = await establish_connection(
            client_class=BleakClient,
            device=ble_device,
            name=ble_device.address,
            timeout=10.0  # Use at least 10 second timeout
        )
        return self.async_custom_fetch_data(client)

    async def async_custom_fetch_data(self, client: BleakClient) -> Dict[str, Any]:
        """Fetch data from the Petkit Fountain device."""
        _LOGGER.debug("Starting Petkit data fetch")
        result = {}
        
        # Make sure we're initialized
        if not self._is_initialized:
            initialized = await self.async_custom_initialization(client, None)
            if not initialized:
                raise BleakError("Device initialization failed")
        
        try:
            # Request device state
            state_payload = await self._send_command_and_wait(
                client, CMD_GET_DEVICE_STATE, 1, [0, 0], RESP_DEVICE_STATE
            )
            if state_payload:
                # Parse device state
                if len(state_payload) >= 12:
                    result[KEY_PF_POWER_STATUS] = "On" if state_payload[0] == 1 else "Off"
                    result[KEY_PF_MODE] = "Smart" if state_payload[1] == 2 else "Normal"
                    result[KEY_PF_WARN_BREAKDOWN] = bool(state_payload[2])
                    result[KEY_PF_WARN_WATER] = bool(state_payload[3])
                    result[KEY_PF_WARN_FILTER] = bool(state_payload[4])
                    
                    filter_days_remaining = state_payload[5]
                    if len(state_payload) >= 10:
                        pump_runtime_minutes = int.from_bytes(state_payload[6:10], byteorder='little')
                        result[KEY_PF_PUMP_RUNTIME] = pump_runtime_minutes * 60  # Convert to seconds
                    
                    # Calculate filter percentage
                    if filter_days_remaining <= 0:
                        result[KEY_PF_FILTER_PERCENT] = 0
                    else:
                        result[KEY_PF_FILTER_PERCENT] = round(max(0, min(100, (filter_days_remaining / 30) * 100)))
                    
                    if len(state_payload) >= 11:
                        result[KEY_PF_RUNNING_STATUS] = "Running" if state_payload[10] == 1 else "Idle"
            
            await asyncio.sleep(0.5)  # Small delay between commands
            
            # Request device config
            config_payload = await self._send_command_and_wait(
                client, CMD_GET_DEVICE_CONFIG, 1, [0, 0], RESP_DEVICE_CONFIG
            )
            if config_payload and len(config_payload) >= 9:
                dnd_switch = config_payload[8]
                result[KEY_PF_DND_STATE] = "On" if dnd_switch == 1 else "Off"
            
            await asyncio.sleep(0.5)
            
            # Request battery level
            battery_payload = await self._send_command_and_wait(
                client, CMD_GET_BATTERY, 1, [0, 0], RESP_BATTERY
            )
            if battery_payload and len(battery_payload) >= 1:
                result[KEY_PF_BATTERY] = battery_payload[0]
            
            # Process any remaining notifications in the queue
            while not self._notification_queue.empty():
                notification_data = await self._notification_queue.get()
                notify_result = await self._process_notification(notification_data)
                result.update(notify_result)
                self._notification_queue.task_done()
                
            return result
            
        except Exception as e:
            _LOGGER.error(f"Error fetching Petkit data: {e}", exc_info=True)
            raise
        