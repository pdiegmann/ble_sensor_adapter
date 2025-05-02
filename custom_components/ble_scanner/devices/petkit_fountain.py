"""Active connection handler for Petkit Fountain devices."""
import asyncio
import logging
from datetime import datetime # Keep for _time_in_bytes
from typing import Any, Dict, Optional # Keep Callable for notification callback type hint if needed

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
# from bleak.backends.device import BLEDevice # No longer needed here
from bleak.exc import BleakError

from custom_components.ble_scanner.devices.base import BaseDeviceHandler
from custom_components.ble_scanner.const import (
    # LOGGER_NAME, # Logger passed in __init__
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

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """Initialize the Petkit Fountain handler."""
        super().__init__(config, logger) # Pass config and logger to base
        self._sequence = 0
        self._device_id_bytes: Optional[bytes] = None
        self._secret: Optional[bytes] = None
        self._notification_queue = asyncio.Queue() # Queue for notifications within a fetch cycle
        self._expected_responses: Dict[int, asyncio.Future] = {} # Futures for expected responses
        self._is_initialized = False # Track if initial command sequence is done
        self._latest_data: Dict[str, Any] = {} # Store latest parsed data

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
        # (This might be less relevant in a polling model unless device sends spontaneously)
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
            try:
                # Based on PetkitW5BLEMQTT/parsers.py device_state
                self._latest_data[KEY_PF_POWER_STATUS] = "On" if payload[0] == 1 else "Off"
                self._latest_data[KEY_PF_MODE] = "Smart" if payload[1] == 2 else "Normal"
                self._latest_data[KEY_PF_WARN_BREAKDOWN] = bool(payload[2])
                self._latest_data[KEY_PF_WARN_WATER] = bool(payload[3])
                self._latest_data[KEY_PF_WARN_FILTER] = bool(payload[4])
                # Filter life seems complex, involves calculation based on runtime/days
                # Let's parse the raw values first
                filter_days_remaining = payload[5]
                # Ensure slice has enough bytes before converting
                if len(payload) >= 10:
                    pump_runtime_minutes = int.from_bytes(payload[6:10], byteorder='little') # Assuming little-endian based on some parsers
                    self._latest_data["filter_days_remaining_raw"] = filter_days_remaining
                    self._latest_data[KEY_PF_PUMP_RUNTIME] = pump_runtime_minutes * 60 # Convert to seconds
                else:
                     self.logger.warning("Device state payload too short for pump runtime.")
                     # Avoid setting potentially incorrect values if data is missing
                     self._latest_data.pop(KEY_PF_PUMP_RUNTIME, None)
                     self._latest_data.pop("filter_days_remaining_raw", None)

                # Calculate filter percentage (approximate, based on common 30-day cycle)
                # This might need adjustment based on specific model/filter type
                if filter_days_remaining <= 0:
                    self._latest_data[KEY_PF_FILTER_PERCENT] = 0
                else:
                    # Assuming a max of 30 days for simplicity, might be wrong
                    self._latest_data[KEY_PF_FILTER_PERCENT] = round(max(0, min(100, (filter_days_remaining / 30) * 100)))

                if len(payload) >= 11:
                    self._latest_data[KEY_PF_RUNNING_STATUS] = "Running" if payload[10] == 1 else "Idle" # Pump status?
                else:
                    self.logger.warning("Device state payload too short for running status.")
                    self._latest_data.pop(KEY_PF_RUNNING_STATUS, None)

                # payload[11] seems unused or unknown in example
                self.logger.debug(f"Parsed device state: {self._latest_data}")
            except IndexError:
                self.logger.error(f"IndexError parsing device state payload: {payload.hex()}", exc_info=True)
            except Exception as e:
                 self.logger.error(f"Unexpected error parsing device state payload: {e}", exc_info=True)
        else:
             self.logger.warning(f"Device state payload too short: {len(payload)} bytes")

    def _parse_device_config(self, payload: bytes):
        """Parse response from CMD_GET_DEVICE_CONFIG (211)."""
        if len(payload) >= 9: # Need at least 9 bytes to read dnd_switch at index 8
             try:
                 # Based on PetkitW5BLEMQTT/parsers.py device_config
                 # ... (other unused values)
                 dnd_switch = payload[8]
                 self._latest_data[KEY_PF_DND_STATE] = "On" if dnd_switch == 1 else "Off"
                 self.logger.debug(f"Parsed device config (DND State): {self._latest_data.get(KEY_PF_DND_STATE)}")
             except IndexError:
                 self.logger.error(f"IndexError parsing device config payload: {payload.hex()}", exc_info=True)
             except Exception as e:
                 self.logger.error(f"Unexpected error parsing device config payload: {e}", exc_info=True)
        else:
             self.logger.warning(f"Device config payload too short: {len(payload)} bytes")

    def _parse_battery(self, payload: bytes):
        """Parse response from CMD_GET_BATTERY (66)."""
        if len(payload) >= 1:
            try:
                battery_level = payload[0]
                self._latest_data[KEY_PF_BATTERY] = battery_level
                self.logger.debug(f"Parsed battery level: {battery_level}%")
            except IndexError: # Should not happen with len check, but for safety
                 self.logger.error(f"IndexError parsing battery payload: {payload.hex()}", exc_info=True)
            except Exception as e:
                 self.logger.error(f"Unexpected error parsing battery payload: {e}", exc_info=True)
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
        # This callback puts data into the queue for processing within async_fetch_data
        self.logger.debug(f"Received notification from {sender.uuid}: {bytes(data).hex()}")
        self._notification_queue.put_nowait(bytes(data))

    async def _process_notifications_inline(self):
        """Process notifications received during the fetch cycle."""
        # This is called within async_fetch_data to handle responses
        # triggered by commands sent during that fetch.
        while not self._notification_queue.empty():
            try:
                data = self._notification_queue.get_nowait()
                self._parse_response(data)
                self._notification_queue.task_done()
            except asyncio.QueueEmpty:
                break # No more notifications for now
            except Exception as e:
                self.logger.error(f"Error processing notification inline: {e}", exc_info=True)


    # --- Command Sending Logic --- #
    async def _send_command_and_wait(self, client: BleakClient, cmd: int, type_val: int, data: list[int], response_cmd: int) -> Optional[bytes]:
        """Sends a command using the provided client and waits for a specific response command."""
        # Removed connection check, assumes client is connected by coordinator
        seq = self._sequence
        command_bytes = self._build_command(seq, cmd, type_val, data)
        future = asyncio.Future()
        self._expected_responses[response_cmd] = future

        try:
            self.logger.debug(f"Sending command: Seq={seq}, Cmd={cmd}, Type={type_val}, Data={data}")
            await client.write_gatt_char(PETKIT_WRITE_UUID, command_bytes, response=False)
            self._increment_sequence()

            # Wait for the response (processed by _notification_callback -> _parse_response)
            payload = await asyncio.wait_for(future, timeout=RESPONSE_TIMEOUT)
            self.logger.debug(f"Received expected response for Cmd={response_cmd}: {payload.hex()}")
            return payload
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout waiting for response to command {cmd} (Expected: {response_cmd})")
            # Let the exception propagate to async_fetch_data
            raise
        except BleakError as e:
            self.logger.error(f"BleakError sending command {cmd}: {e}")
            # Let the exception propagate to async_fetch_data
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error sending command {cmd}: {e}", exc_info=True)
            # Let the exception propagate to async_fetch_data
            raise
        finally:
            # Clean up future
            if response_cmd in self._expected_responses:
                del self._expected_responses[response_cmd]

    # --- Initialization Sequence --- #
    async def _initialize_device(self, client: BleakClient):
        """Perform the initial command sequence required by Petkit devices."""
        self.logger.info(f"Starting initialization sequence for {self.device_id}")

        # 1. Get Device Details (to get device_id/serial)
        details_payload = await self._send_command_and_wait(client, CMD_GET_DEVICE_DETAILS, 1, [0, 0], RESP_DEVICE_DETAILS)
        if not details_payload:
            self.logger.error("Failed to get device details during initialization.")
            return False
        self._parse_device_details(details_payload)
        if not self._device_id_bytes:
             self.logger.error("Could not extract device ID from details response.")
             return False

        # 2. Init Device (Send secret derived from device_id)
        reversed_id = bytes(reversed(self._device_id_bytes))
        padded_secret = reversed_id + bytes(max(0, 8 - len(reversed_id)))
        self._secret = padded_secret # Store the secret
        self.logger.debug(f"Generated Secret: {self._secret.hex()}")

        padded_device_id = self._device_id_bytes + bytes(max(0, 8 - len(self._device_id_bytes)))
        init_data = [0, 0] + list(padded_device_id) + list(self._secret)
        init_payload = await self._send_command_and_wait(client, CMD_INIT_DEVICE, 1, init_data, RESP_INIT_DEVICE)
        if init_payload is None: # Check for None explicitly, empty payload might be valid
            self.logger.warning("Failed to send init command or receive response. Continuing cautiously...")
            # Some devices might not respond to init, proceed cautiously
            # return False # Decide if this is fatal

        # 3. Get Device Sync (Send secret)
        sync_data = [0, 0] + list(self._secret)
        sync_payload = await self._send_command_and_wait(client, CMD_GET_DEVICE_SYNC, 1, sync_data, RESP_DEVICE_SYNC)
        if sync_payload is None:
            self.logger.warning("Failed to send sync command or receive response. Continuing...")
            # return False # Might not be critical?

        # 4. Set Datetime
        time_data = self._time_in_bytes()
        # No specific response expected for set_datetime, just send and hope
        # Use a dummy response code that won't match anything real
        try:
            await self._send_command_and_wait(client, CMD_SET_DATETIME, 1, time_data, 999)
        except asyncio.TimeoutError:
            self.logger.debug("Timeout expected for SET_DATETIME command, continuing.")
        except BleakError as e:
            self.logger.warning(f"BleakError sending SET_DATETIME: {e}. Continuing...")
        # Check if successful? Assume ok for now.

        self.logger.info(f"Initialization sequence completed for {self.device_id}")
        self._is_initialized = True
        return True

    # --- Main Fetch Logic (Replaces update) --- #
    async def async_fetch_data(self, client: BleakClient) -> Dict[str, Any]:
        """
        Fetch data from the connected Petkit Fountain.

        Handles initialization, command sending, and notification processing
        within a single fetch cycle using the provided connected client.
        """
        self.logger.debug(f"[{self.device_id}] Starting async_fetch_data")
        # Clear previous data? Or keep stale data until updated? Let's clear specific keys on failure.
        # self._latest_data = {} # Start fresh each time? Maybe not ideal if some fetches fail.

        # Ensure notifications are stopped from previous runs (safety)
        try:
            await client.stop_notify(PETKIT_READ_UUID)
        except (BleakError, KeyError): # Ignore errors if not subscribed or char missing
             pass
        # Clear the queue from potential leftovers
        while not self._notification_queue.empty():
            self._notification_queue.get_nowait()
            self._notification_queue.task_done()
        self._expected_responses.clear() # Clear any stale futures

        try:
            # Start notifications for this fetch cycle
            await client.start_notify(PETKIT_READ_UUID, self._notification_callback)
            self.logger.debug(f"[{self.device_id}] Started notification listener.")

            # Perform initialization sequence if not done yet
            if not self._is_initialized:
                if not await self._initialize_device(client):
                    # Initialization failed, raise error to coordinator
                    raise BleakError("Device initialization failed.")

            # Fetch current state after initialization/connection
            self.logger.debug(f"[{self.device_id}] Requesting device state, config, and battery...")

            # Use asyncio.gather to run fetches concurrently? Petkit might not like that.
            # Send commands sequentially with delays.

            state_payload = await self._send_command_and_wait(client, CMD_GET_DEVICE_STATE, 1, [0, 0], RESP_DEVICE_STATE)
            if state_payload:
                self._parse_device_state(state_payload)
            else:
                self.logger.warning(f"[{self.device_id}] Failed to get device state.")
                # Clear relevant keys if fetch failed?
                self._latest_data.pop(KEY_PF_POWER_STATUS, None)
                self._latest_data.pop(KEY_PF_MODE, None)
                # ... clear other state keys

            await asyncio.sleep(0.5) # Small delay between commands

            config_payload = await self._send_command_and_wait(client, CMD_GET_DEVICE_CONFIG, 1, [0, 0], RESP_DEVICE_CONFIG)
            if config_payload:
                self._parse_device_config(config_payload)
            else:
                self.logger.warning(f"[{self.device_id}] Failed to get device config.")
                self._latest_data.pop(KEY_PF_DND_STATE, None)


            await asyncio.sleep(0.5)

            battery_payload = await self._send_command_and_wait(client, CMD_GET_BATTERY, 1, [0, 0], RESP_BATTERY)
            if battery_payload:
                self._parse_battery(battery_payload)
            else:
                self.logger.warning(f"[{self.device_id}] Failed to get battery level.")
                self._latest_data.pop(KEY_PF_BATTERY, None)


            # Add other fetches if needed (CMD_GET_DEVICE_INFO, CMD_GET_DEVICE_TYPE)

            # Process any remaining notifications that might have arrived
            await self._process_notifications_inline()

            self.logger.info(f"[{self.device_id}] Data fetch successful. Latest data: {self._latest_data}")
            return self._latest_data.copy() # Return a copy

        except (BleakError, asyncio.TimeoutError) as e:
            self.logger.error(f"[{self.device_id}] Communication error during data fetch: {e}")
            # Mark device unavailable implicitly by raising UpdateFailed in coordinator
            # Clear data? Maybe not, keep last known state?
            # Let the coordinator handle the UpdateFailed exception.
            raise # Re-raise the exception
        except Exception as e:
            self.logger.error(f"[{self.device_id}] Unexpected error during data fetch: {e}", exc_info=True)
            raise # Re-raise the exception
        finally:
            # Stop notifications after fetch cycle
            try:
                if client.is_connected: # Check connection before trying to stop
                    await client.stop_notify(PETKIT_READ_UUID)
                    self.logger.debug(f"[{self.device_id}] Stopped notification listener.")
            except BleakError as e:
                # Ignore errors stopping notifications if already disconnected etc.
                self.logger.warning(f"[{self.device_id}] BleakError stopping notifications: {e}")
            except Exception as e:
                 self.logger.warning(f"[{self.device_id}] Error stopping notifications: {e}")
            # Clear queue and futures again just in case
            while not self._notification_queue.empty():
                self._notification_queue.get_nowait()
                self._notification_queue.task_done()
            self._expected_responses.clear()
