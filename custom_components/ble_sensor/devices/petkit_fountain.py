from __future__ import annotations

import asyncio
import binascii
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, Union

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

from custom_components.ble_sensor.devices.base import DeviceType
from custom_components.ble_sensor.devices.device import BLEDevice
from custom_components.ble_sensor.utils.const import (KEY_PF_ALIAS,
                                                      KEY_PF_BATTERY,
                                                      KEY_PF_DND_STATE,
                                                      KEY_PF_FILTER_PERCENT,
                                                      KEY_PF_MODE,
                                                      KEY_PF_MODEL_CODE,
                                                      KEY_PF_MODEL_NAME,
                                                      KEY_PF_POWER_STATUS,
                                                      KEY_PF_PUMP_RUNTIME,
                                                      KEY_PF_RUNNING_STATUS,
                                                      KEY_PF_WARN_BREAKDOWN,
                                                      KEY_PF_WARN_FILTER,
                                                      KEY_PF_WARN_WATER)
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass, BinarySensorEntityDescription)
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.sensor import (SensorDeviceClass,
                                             SensorEntityDescription,
                                             SensorStateClass)
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime

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
        self._device_id_bytes: bytes | None = None
        self._secret: bytes | None = None
        self._notification_queue: asyncio.Queue | None = None
        self._expected_responses: dict[int, asyncio.Future] = {}
        self._is_initialized = False

    def get_sensor_descriptions(self) -> list[SensorEntityDescription]:
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

    def get_binary_sensor_descriptions(self) -> list[BinarySensorEntityDescription]:
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

    def get_switch_descriptions(self) -> list[SwitchEntityDescription]:
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

    def get_select_descriptions(self) -> list[SelectEntityDescription]:
        """Return select entity descriptions for this device type."""
        return [
            SelectEntityDescription(
                key=KEY_PF_MODE,
                name="Mode",
                options=["Smart", "Normal"],
                icon="mdi:fountain",
            ),
        ]

    def get_characteristics(self) -> list[str]:
        """Return characteristic UUIDs this device uses."""
        return [
            PETKIT_READ_UUID,
            PETKIT_WRITE_UUID,
        ]

    def get_services(self) -> list[str]:
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
        """Builds the byte command to send to the device (PetkitW5BLEMQTT compatible)."""
        # PetkitW5BLEMQTT uses header [250,252,253], end byte [251]
        header = [250, 252, 253]  # 0xFA, 0xFC, 0xFD
        end_byte = [251]          # 0xFB
        length = len(data)
        start_data = 0
        command = header + [cmd, type_val, seq, length, start_data] + data + end_byte
        return bytes(command)

    @staticmethod
    def _time_in_bytes() -> list[int]:
        """Get current time formatted as bytes for CMD_SET_DATETIME."""
        now = datetime.now()
        year_bytes = [int(str(now.year)[i:i+2]) for i in range(0, 4, 2)]
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
        except BleakError as e:
            _LOGGER.error(f"BLE error setting power status: {e}")
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
        except BleakError as e:
            _LOGGER.error(f"BLE error setting mode: {e}")
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
        except BleakError as e:
            _LOGGER.error(f"BLE error setting DND state: {e}")
            return False

    # The following methods would be used during the fetch_data operation in the coordinator
    async def async_custom_initialization(self, client: BleakClient) -> bool:
        _LOGGER.info("Starting robust initialization sequence for Petkit Fountain")

        if not client or not client.is_connected:
            _LOGGER.error("Cannot initialize: client not connected")
            return False

        self._notification_queue = asyncio.Queue()

        # Set up notification handler and verify characteristics
        try:
            await client.start_notify(PETKIT_READ_UUID, self._notification_handler)
            _LOGGER.info("Successfully started notifications on characteristic %s", PETKIT_READ_UUID)
            services = client.services
            read_char_found = False
            write_char_found = False
            for service in services:
                for characteristic in service.characteristics:
                    if characteristic.uuid.lower() == PETKIT_READ_UUID.lower():
                        read_char_found = True
                        _LOGGER.info("Found read characteristic: %s (properties: %s)", characteristic.uuid, characteristic.properties)
                    elif characteristic.uuid.lower() == PETKIT_WRITE_UUID.lower():
                        write_char_found = True
                        _LOGGER.info("Found write characteristic: %s (properties: %s)", characteristic.uuid, characteristic.properties)
            if not read_char_found:
                _LOGGER.error("Read characteristic %s not found", PETKIT_READ_UUID)
                return False
            if not write_char_found:
                _LOGGER.error("Write characteristic %s not found", PETKIT_WRITE_UUID)
                return False
            await asyncio.sleep(0.2)
        except Exception as ex:
            _LOGGER.error("Failed to start notifications: %s", ex, exc_info=True)
            return False

        # Robust initialization sequence with retries and reconnects
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # 1. Retry get_device_details until valid
                details_payload = None
                for _ in range(5):
                    details_payload = await self._send_command_with_retry(
                        client,
                        CMD_GET_DEVICE_DETAILS,
                        1,
                        [0, 0],
                        RESP_DEVICE_DETAILS,
                        timeout=INIT_COMMAND_TIMEOUT
                    )
                    if details_payload and len(details_payload) >= 6:
                        break
                    _LOGGER.warning("Device details not valid, retrying...")
                    await asyncio.sleep(1.5)
                if not details_payload or len(details_payload) < 6:
                    raise Exception("Invalid device details response after retries")

                self._device_id_bytes = details_payload[0:6]
                _LOGGER.debug("Device ID/Serial: %s", binascii.hexlify(self._device_id_bytes).decode())

                # 2. Init Device (Send secret derived from device_id)
                reversed_id = bytes(reversed(self._device_id_bytes))
                padded_secret = reversed_id + bytes(max(0, 8 - len(reversed_id)))
                self._secret = padded_secret
                padded_device_id = self._device_id_bytes + bytes(max(0, 8 - len(self._device_id_bytes)))
                init_data = [0, 0] + list(padded_device_id) + list(self._secret)
                await self._send_command_with_retry(
                    client,
                    CMD_INIT_DEVICE,
                    1,
                    init_data,
                    RESP_INIT_DEVICE,
                    timeout=INIT_COMMAND_TIMEOUT
                )
                await asyncio.sleep(1.0)

                # 3. Get Device Sync
                sync_data = [0, 0] + list(self._secret)
                await self._send_command_with_retry(
                    client,
                    CMD_GET_DEVICE_SYNC,
                    1,
                    sync_data,
                    RESP_DEVICE_SYNC,
                    timeout=INIT_COMMAND_TIMEOUT
                )
                await asyncio.sleep(0.75)

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
                await asyncio.sleep(0.75)

                self._is_initialized = True
                _LOGGER.info("Petkit initialization complete (attempt %d)", attempt + 1)
                return True
            except Exception as e:
                _LOGGER.error("Initialization attempt %d failed: %s", attempt + 1, str(e))
                await asyncio.sleep(2.0)
                try:
                    await client.disconnect()
                except Exception:
                    pass
                await asyncio.sleep(1.0)
                try:
                    await client.connect()
                except Exception as e2:
                    _LOGGER.error("Reconnect failed: %s", str(e2))
                    return False
        _LOGGER.error("Petkit initialization failed after %d attempts", max_attempts)
        return False

    async def async_custom_fetch_data(self, ble_device) -> dict[str, Any] | None:
        """Fetch data from the device."""
        _LOGGER.info("Starting data fetch for device %s", ble_device.address)
        
        # Reset initialization state for each new connection
        self._is_initialized = False
        self._device_id_bytes = None
        self._secret = None
        self._expected_responses.clear()
        
        client = None
        try:
            async with asyncio.timeout(30):
                client = await establish_connection(
                    client_class=BleakClient,
                    device=ble_device,
                    name=ble_device.address,
                    timeout=10.0
                )

                _LOGGER.info("BLE connection established to %s", ble_device.address)

                # Always initialize for each session
                if not await self.async_custom_initialization(client):
                    _LOGGER.error("Failed to initialize device %s", ble_device.address)
                    return None

                # Fetch battery level
                battery_payload = await self._send_command_with_retry(
                    client, CMD_GET_BATTERY, 1, [0, 0], RESP_BATTERY
                )

                # Fetch device state
                state_payload = await self._send_command_with_retry(
                    client, CMD_GET_DEVICE_STATE, 1, [0, 0], RESP_DEVICE_STATE
                )

                # Fetch device config
                config_payload = await self._send_command_with_retry(
                    client, CMD_GET_DEVICE_CONFIG, 1, [0, 0], RESP_DEVICE_CONFIG
                )

                # Process payloads and return a dictionary of sensor values
                data = self.parse_raw_data(battery_payload, state_payload, config_payload)
                _LOGGER.info("Successfully fetched and parsed data for %s: %s", ble_device.address, data)
                return data

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout connecting to device %s", ble_device.address)
            return None
        except Exception as e:
            _LOGGER.error("Error fetching data from %s: %s", ble_device.address, str(e))
            return None
        finally:
            if client is not None and client.is_connected:
                try:
                    await client.stop_notify(PETKIT_READ_UUID)
                except Exception:
                    pass  # Ignore errors during cleanup
                try:
                    await client.disconnect()
                except Exception:
                    pass  # Ignore errors during cleanup

    def parse_raw_data(
        self,
        battery_payload: bytes | None,
        state_payload: bytes | None,
        config_payload: bytes | None,
    ) -> dict[str, Any]:
        """Parse the data from the device payloads."""
        data = {}

        if battery_payload and len(battery_payload) >= 1:
            data[KEY_PF_BATTERY] = int(battery_payload[0])

        if state_payload and len(state_payload) >= 12:
            data[KEY_PF_POWER_STATUS] = bool(state_payload[0])
            data[KEY_PF_MODE] = "Smart" if state_payload[1] == 2 else "Normal"
            data[KEY_PF_WARN_BREAKDOWN] = bool(state_payload[2] & 0x01)
            data[KEY_PF_WARN_WATER] = bool(state_payload[2] & 0x02)
            data[KEY_PF_WARN_FILTER] = bool(state_payload[2] & 0x04)

            # Extract pump runtime (4 bytes, little endian)
            if len(state_payload) >= 8:
                pump_runtime = int.from_bytes(state_payload[4:8], byteorder='little')
                data[KEY_PF_PUMP_RUNTIME] = pump_runtime

            # Extract running status
            if len(state_payload) >= 12:
                data[KEY_PF_RUNNING_STATUS] = "Running" if state_payload[11] else "Stopped"

        if config_payload and len(config_payload) >= 9:
            data[KEY_PF_DND_STATE] = bool(config_payload[8])

            # Extract filter percentage if available
            if len(config_payload) >= 4:
                filter_percent = int.from_bytes(config_payload[0:4], byteorder='little')
                # Convert to percentage (assuming max value represents 100%)
                data[KEY_PF_FILTER_PERCENT] = min(100, max(0, filter_percent))

        return data

    async def _send_command_and_wait(
        self,
        client: BleakClient,
        cmd: int,
        type_val: int,
        data: list[int],
        response_cmd: int,
        timeout: float = NORMAL_COMMAND_TIMEOUT,
    ) -> bytes | None:
        """Send a command and wait for the expected response."""
        if not client or not client.is_connected:
            raise BleakError("Client not connected")

        self._increment_sequence()
        command = self._build_command(self._sequence, cmd, type_val, data)

        # Create a future for the expected response
        response_future = asyncio.Future()
        self._expected_responses[self._sequence] = response_future

        try:
            # Send the command
            await client.write_gatt_char(PETKIT_WRITE_UUID, command)
            _LOGGER.info("Sent command %d (seq %d): %s", cmd, self._sequence,
                        binascii.hexlify(command).decode())
            _LOGGER.info("Expecting response for seq %d, expecting cmd %d", self._sequence, response_cmd)

            # Wait for response
            async with asyncio.timeout(timeout):
                response_data = await response_future

            # Parse response
            if len(response_data) < 6:
                _LOGGER.warning("Received short response: %s",
                               binascii.hexlify(response_data).decode())
                return None

            # Extract payload (skip header and checksum)
            payload_length = response_data[2] - 4
            if payload_length > 0 and len(response_data) >= 6 + payload_length:
                payload = response_data[6:6+payload_length]
                _LOGGER.debug("Received response for cmd %d: %s",
                             response_cmd, binascii.hexlify(payload).decode())
                return payload
            else:
                return b''  # Empty payload

        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout waiting for response to command %d", cmd)
            raise
        finally:
            # Clean up the future, even if it timed out or an error occurred
            if self._sequence in self._expected_responses:
                del self._expected_responses[self._sequence]

    async def _send_command_with_retry(
        self,
        client: BleakClient,
        cmd: int,
        type_val: int,
        data: list[int],
        response_cmd: int,
        retries: int = MAX_COMMAND_RETRIES,
        timeout: float = NORMAL_COMMAND_TIMEOUT,
    ) -> bytes | None:
        """Send a command with retries and wait for the expected response."""
        for attempt in range(retries):
            try:
                return await self._send_command_and_wait(
                    client, cmd, type_val, data, response_cmd, timeout
                )
            except (asyncio.TimeoutError, BleakError) as e:
                _LOGGER.warning(
                    "Attempt %d/%d for command %d failed: %s",
                    attempt + 1,
                    retries,
                    cmd,
                    e
                )
                if attempt + 1 == retries:
                    _LOGGER.error("Command %d failed after %d retries", cmd, retries)
                    raise
                await asyncio.sleep(RETRY_DELAY)
        return None

    async def _notification_handler(self, characteristic, data):
        """Handle BLE notifications."""
        data_hex = binascii.hexlify(bytes(data)).decode()
        _LOGGER.info("Received BLE notification: %s (len=%d)", data_hex, len(data))

        if len(data) < 6:
            _LOGGER.warning("Received malformed notification: %s", data_hex)
            return

        seq = data[3]
        response_cmd = data[4]
        _LOGGER.info("Parsed notification: seq=%d, cmd=%d", seq, response_cmd)
        
        if seq in self._expected_responses:
            future = self._expected_responses[seq]
            if not future.done():
                _LOGGER.info("Setting result for expected response seq %d", seq)
                future.set_result(bytes(data))
            else:
                _LOGGER.warning("Future already done for seq %d", seq)
        else:
            if response_cmd == 1:
                _LOGGER.debug("Received benign unsolicited notification for sequence %d (cmd %d), expected sequences: %s",
                              seq, response_cmd, list(self._expected_responses.keys()))
            else:
                _LOGGER.warning("Received unsolicited notification for sequence %d (cmd %d), expected sequences: %s",
                                seq, response_cmd, list(self._expected_responses.keys()))
