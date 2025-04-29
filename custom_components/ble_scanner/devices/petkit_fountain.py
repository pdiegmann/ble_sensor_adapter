"""Active connection handler for Petkit Fountain devices."""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Callable

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from .base import BaseDeviceHandler
from ..const import (
    LOGGER_NAME,
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
    # Add other relevant keys if needed
)

# Constants from PetkitW5BLEMQTT library analysis
PETKIT_WRITE_UUID = "0000aaa2-0000-1000-8000-00805f9b34fb"
PETKIT_READ_UUID = "0000aaa1-0000-1000-8000-00805f9b34fb"

# Command codes (from commands.py)
CMD_GET_BATTERY = 66
CMD_INIT_DEVICE = 73
CMD_SET_DATETIME = 84
CMD_GET_DEVICE_SYNC = 86
CMD_GET_DEVICE_INFO = 200
CMD_GET_DEVICE_TYPE = 201
CMD_GET_DEVICE_STATE = 210
CMD_GET_DEVICE_CONFIG = 211
CMD_GET_DEVICE_DETAILS = 213 # Gets device_id/serial
CMD_SET_DEVICE_MODE = 220
CMD_SET_DEVICE_CONFIG = 221
CMD_RESET_FILTER = 222

# Response codes (from parsers.py)
RESP_DEVICE_DETAILS = 213
RESP_DEVICE_STATE = 210
RESP_DEVICE_CONFIG = 211
RESP_BATTERY = 66
RESP_DEVICE_INFO = 200
RESP_DEVICE_TYPE = 201
RESP_DEVICE_SYNC = 86 # Used for secret/init
RESP_INIT_DEVICE = 73 # Used for secret/init

# Timeout for waiting for specific responses
RESPONSE_TIMEOUT = 10 # seconds

class PetkitFountainHandler(BaseDeviceHandler):
    """Handles connection and data parsing for Petkit Fountains."""

    def __init__(self, hass, config, logger):
        super().__init__(hass, config, logger)
        self._sequence = 0
        self._device_id_bytes: Optional[bytes] = None
        self._secret: Optional[bytes] = None
        self._notification_queue = asyncio.Queue()
        self._expected_responses: Dict[int, asyncio.Future] = {}
        self._is_initialized = False # Track if initial command sequence is done

    def _increment_sequence(self):
        """Increment and wrap the command sequence number."""
        self._sequence = (self._sequence + 1) % 256

    # --- Command Building (Adapted from PetkitW5BLEMQTT/utils.py) --- #
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

    # --- Response Parsing (Adapted from PetkitW5BLEMQTT/parsers.py) --- #
    def _parse_response(self, data: bytes):
        """Parse incoming data from the device notification."""
        if not data or len(data) < 6:
            self.logger.debug(f"Received short/invalid data: {data.hex()}")
            return

        # Basic validation (Start bytes, checksum)
        if data[0] != 0x55 or data[1] != 0xAA:
            self.logger.debug(f"Invalid start bytes: {data.hex()}")
            return

        declared_len = data[2]
        actual_len = len(data)
        if actual_len < declared_len + 4: # Header (4 bytes) + declared payload len
             self.logger.debug(f"Incomplete packet: Declared {declared_len}, Got {actual_len}. Data: {data.hex()}")
             return

        # Verify checksum
        checksum = 0
        for byte_val in data[2:-1]: # From length byte up to (excluding) checksum byte
            checksum ^= byte_val
        if checksum != data[-1]:
            self.logger.warning(f"Checksum mismatch: Calculated {checksum}, Got {data[-1]}. Data: {data.hex()}")
            return

        seq = data[3]
        cmd = data[4]
        type_val = data[5]
        payload = data[6:-1]

        self.logger.debug(f"Received response: Seq={seq}, Cmd={cmd}, Type={type_val}, Payload={payload.hex()}")

        # Check if this is a response we are waiting for
        if cmd in self._expected_responses and not self._expected_responses[cmd].done():
            self._expected_responses[cmd].set_result(payload)
            # Don't process further here, wait for the command sender
            return

        # Handle unsolicited updates or parse specific responses if needed outside command context
        if cmd == RESP_DEVICE_STATE:
            self._parse_device_state(payload)
        elif cmd == RESP_DEVICE_CONFIG:
            self._parse_device_config(payload)
        elif cmd == RESP_BATTERY:
            self._parse_battery(payload)
        # Add other unsolicited handlers if necessary

    def _parse_device_details(self, payload: bytes):
        """Parse response from CMD_GET_DEVICE_DETAILS (213)."""
        if len(payload) >= 6:
            # Extract device ID (serial number?) - seems to be 6 bytes
            self._device_id_bytes = payload[0:6]
            self.logger.info(f"Received Device ID/Serial bytes: {self._device_id_bytes.hex()}")
            # Store as a readable string if desired (e.g., hex)
            self._latest_data["serial_hex"] = self._device_id_bytes.hex()
        else:
            self.logger.warning("Device details payload too short")

    def _parse_device_state(self, payload: bytes):
        """Parse response from CMD_GET_DEVICE_STATE (210)."""
        if len(payload) >= 12:
            # Based on PetkitW5BLEMQTT/parsers.py device_state
            self._latest_data[KEY_PF_POWER_STATUS] = "On" if payload[0] == 1 else "Off"
            self._latest_data[KEY_PF_MODE] = "Smart" if payload[1] == 2 else "Normal"
            self._latest_data[KEY_PF_WARN_BREAKDOWN] = bool(payload[2])
            self._latest_data[KEY_PF_WARN_WATER] = bool(payload[3])
            self._latest_data[KEY_PF_WARN_FILTER] = bool(payload[4])
            # Filter life seems complex, involves calculation based on runtime/days
            # Let's parse the raw values first
            filter_days_remaining = payload[5]
            pump_runtime_minutes = int.from_bytes(payload[6:10], byteorder='little') # Assuming little-endian based on some parsers
            self._latest_data["filter_days_remaining_raw"] = filter_days_remaining
            self._latest_data[KEY_PF_PUMP_RUNTIME] = pump_runtime_minutes * 60 # Convert to seconds

            # Calculate filter percentage (approximate, based on common 30-day cycle)
            # This might need adjustment based on specific model/filter type
            if filter_days_remaining <= 0:
                self._latest_data[KEY_PF_FILTER_PERCENT] = 0
            else:
                # Assuming a max of 30 days for simplicity, might be wrong
                self._latest_data[KEY_PF_FILTER_PERCENT] = round(max(0, min(100, (filter_days_remaining / 30) * 100)))

            self._latest_data[KEY_PF_RUNNING_STATUS] = "Running" if payload[10] == 1 else "Idle" # Pump status?
            # payload[11] seems unused or unknown in example
            self.logger.debug(f"Parsed device state: {self._latest_data}")
        else:
             self.logger.warning(f"Device state payload too short: {len(payload)} bytes")

    def _parse_device_config(self, payload: bytes):
        """Parse response from CMD_GET_DEVICE_CONFIG (211)."""
        if len(payload) >= 14:
             # Based on PetkitW5BLEMQTT/parsers.py device_config
             # smart_time_on = payload[0]
             # smart_time_off = payload[1]
             # led_switch = payload[2]
             # led_brightness = payload[3]
             # led_light_time_on_1 = payload[4]
             # led_light_time_on_2 = payload[5]
             # led_light_time_off_1 = payload[6]
             # led_light_time_off_2 = payload[7]
             dnd_switch = payload[8]
             # dnd_time_start_1 = payload[9]
             # dnd_time_start_2 = payload[10]
             # dnd_time_end_1 = payload[11]
             # dnd_time_end_2 = payload[12]
             # is_locked = payload[13]
             self._latest_data[KEY_PF_DND_STATE] = "On" if dnd_switch == 1 else "Off"
             self.logger.debug(f"Parsed device config (DND State): {self._latest_data[KEY_PF_DND_STATE]}")
        else:
             self.logger.warning(f"Device config payload too short: {len(payload)} bytes")

    def _parse_battery(self, payload: bytes):
        """Parse response from CMD_GET_BATTERY (66)."""
        if len(payload) >= 1:
            battery_level = payload[0]
            self._latest_data[KEY_PF_BATTERY] = battery_level
            self.logger.debug(f"Parsed battery level: {battery_level}%")
        else:
            self.logger.warning("Battery payload too short")

    def _parse_device_info(self, payload: bytes):
        """Parse response from CMD_GET_DEVICE_INFO (200)."""
        # Example parser doesn't show specific use, maybe just confirmation?
        self.logger.debug(f"Received device info response payload: {payload.hex()}")
        # Could potentially extract firmware version if format is known

    def _parse_device_type(self, payload: bytes):
        """Parse response from CMD_GET_DEVICE_TYPE (201)."""
        # Example parser doesn't show specific use, maybe just confirmation?
        self.logger.debug(f"Received device type response payload: {payload.hex()}")
        # Could potentially extract model info if format is known

    # --- Notification Handling --- #
    def _notification_callback(self, sender: BleakGATTCharacteristic, data: bytearray):
        """Handle incoming data notifications."""
        self.logger.debug(f"Received notification from {sender.uuid}: {bytes(data).hex()}")
        self._notification_queue.put_nowait(bytes(data))

    async def _process_notifications(self):
        """Continuously process notifications from the queue."""
        while self.is_connected:
            try:
                data = await self._notification_queue.get()
                self._parse_response(data)
                self._notification_queue.task_done()
            except asyncio.CancelledError:
                self.logger.debug("Notification processing task cancelled.")
                break
            except Exception as e:
                self.logger.error(f"Error processing notification: {e}", exc_info=True)

    # --- Command Sending Logic --- #
    async def _send_command_and_wait(self, cmd: int, type_val: int, data: list[int], response_cmd: int) -> Optional[bytes]:
        """Sends a command and waits for a specific response command."""
        if not self.is_connected or not self._client:
            self.logger.error("Cannot send command: Not connected")
            return None

        seq = self._sequence
        command_bytes = self._build_command(seq, cmd, type_val, data)
        future = asyncio.Future()
        self._expected_responses[response_cmd] = future

        try:
            self.logger.debug(f"Sending command: Seq={seq}, Cmd={cmd}, Type={type_val}, Data={data}")
            await self._client.write_gatt_char(PETKIT_WRITE_UUID, command_bytes, response=False)
            self._increment_sequence()

            # Wait for the response
            payload = await asyncio.wait_for(future, timeout=RESPONSE_TIMEOUT)
            self.logger.debug(f"Received expected response for Cmd={response_cmd}: {payload.hex()}")
            return payload
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout waiting for response to command {cmd} (Expected: {response_cmd})")
            return None
        except BleakError as e:
            self.logger.error(f"BleakError sending command {cmd}: {e}")
            await self.disconnect() # Disconnect if write fails
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error sending command {cmd}: {e}", exc_info=True)
            return None
        finally:
            # Clean up future
            if response_cmd in self._expected_responses:
                del self._expected_responses[response_cmd]

    # --- Initialization Sequence --- #
    async def _initialize_device(self):
        """Perform the initial command sequence required by Petkit devices."""
        self.logger.info(f"Starting initialization sequence for {self.device_id}")

        # 1. Get Device Details (to get device_id/serial)
        details_payload = await self._send_command_and_wait(CMD_GET_DEVICE_DETAILS, 1, [0, 0], RESP_DEVICE_DETAILS)
        if not details_payload:
            self.logger.error("Failed to get device details during initialization.")
            return False
        self._parse_device_details(details_payload)
        if not self._device_id_bytes:
             self.logger.error("Could not extract device ID from details response.")
             return False

        # 2. Init Device (Send secret derived from device_id)
        # Adapted from PetkitW5BLEMQTT/commands.py init_device
        # Secret generation might need refinement based on Utils.py logic
        # Simple reverse and pad for now, might be incorrect
        reversed_id = bytes(reversed(self._device_id_bytes))
        # Pad to 8 bytes
        padded_secret = reversed_id + bytes(max(0, 8 - len(reversed_id)))
        self._secret = padded_secret # Store the secret
        self.logger.debug(f"Generated Secret: {self._secret.hex()}")

        padded_device_id = self._device_id_bytes + bytes(max(0, 8 - len(self._device_id_bytes)))
        init_data = [0, 0] + list(padded_device_id) + list(self._secret)
        init_payload = await self._send_command_and_wait(CMD_INIT_DEVICE, 1, init_data, RESP_INIT_DEVICE)
        if init_payload is None: # Check for None explicitly, empty payload might be valid
            self.logger.error("Failed to send init command or receive response.")
            # Some devices might not respond to init, proceed cautiously
            # return False

        # 3. Get Device Sync (Send secret)
        sync_data = [0, 0] + list(self._secret)
        sync_payload = await self._send_command_and_wait(CMD_GET_DEVICE_SYNC, 1, sync_data, RESP_DEVICE_SYNC)
        if sync_payload is None:
            self.logger.warning("Failed to send sync command or receive response. Continuing...")
            # return False # Might not be critical?

        # 4. Set Datetime
        time_data = self._time_in_bytes()
        # No specific response expected for set_datetime, just send
        await self._send_command_and_wait(CMD_SET_DATETIME, 1, time_data, 999) # Use dummy response code
        # Check if successful? Assume ok for now.

        self.logger.info(f"Initialization sequence completed for {self.device_id}")
        self._is_initialized = True
        return True

    # --- Main Update Logic --- #
    async def update(self, ble_device: BLEDevice) -> None:
        """Connect, initialize (if needed), subscribe, and fetch data."""
        async with self._update_lock:
            if not await self._ensure_connected(ble_device):
                self.mark_unavailable()
                return

            notification_task = None
            try:
                # Start notification processing task
                await self._client.start_notify(PETKIT_READ_UUID, self._notification_callback)
                notification_task = asyncio.create_task(self._process_notifications())
                self.logger.debug("Started notification listener.")

                # Perform initialization sequence if not done yet
                if not self._is_initialized:
                    if not await self._initialize_device():
                        raise BleakError("Device initialization failed.")

                # Fetch current state after initialization/connection
                self.logger.debug("Requesting device state and config...")
                state_payload = await self._send_command_and_wait(CMD_GET_DEVICE_STATE, 1, [0, 0], RESP_DEVICE_STATE)
                if state_payload:
                    self._parse_device_state(state_payload)

                await asyncio.sleep(0.5) # Small delay between commands

                config_payload = await self._send_command_and_wait(CMD_GET_DEVICE_CONFIG, 1, [0, 0], RESP_DEVICE_CONFIG)
                if config_payload:
                    self._parse_device_config(config_payload)

                await asyncio.sleep(0.5)

                battery_payload = await self._send_command_and_wait(CMD_GET_BATTERY, 1, [0, 0], RESP_BATTERY)
                if battery_payload:
                    self._parse_battery(battery_payload)

                # Add other fetches if needed (CMD_GET_DEVICE_INFO, CMD_GET_DEVICE_TYPE)

                self._last_update_time = datetime.now()
                self._is_available = True
                self.logger.info(f"Update successful for {self.device_id}. Latest data: {self._latest_data}")

                # Keep connection open? Or disconnect after update?
                # For polling coordinator, disconnect is better to allow other devices.
                # If using a push-based approach, keep connected.
                # Current coordinator is polling, so disconnect.
                # Let the coordinator handle disconnect? No, handler should manage its state.
                # Keep connected for a short while to allow notifications? No, polling implies discrete updates.

            except BleakError as e:
                self.logger.error(f"BleakError during update for {self.device_id}: {e}")
                self.mark_unavailable()
                await self.disconnect() # Ensure disconnect on error
                raise
            except Exception as e:
                self.logger.error(f"Unexpected error during update for {self.device_id}: {e}", exc_info=True)
                self.mark_unavailable()
                await self.disconnect() # Ensure disconnect on error
                raise
            finally:
                # Stop notifications and processing task before potential disconnect
                if self.is_connected and self._client:
                    try:
                        await self._client.stop_notify(PETKIT_READ_UUID)
                        self.logger.debug("Stopped notification listener.")
                    except BleakError as e:
                        self.logger.warning(f"BleakError stopping notifications: {e}")
                if notification_task and not notification_task.done():
                    notification_task.cancel()
                    await asyncio.sleep(0) # Allow cancellation to propagate

                # Disconnect after update cycle (for polling coordinator)
                await self.disconnect()

