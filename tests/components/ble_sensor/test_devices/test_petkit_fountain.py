import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bleak import BleakClient

from custom_components.ble_sensor.devices.petkit_fountain import (
    CMD_GET_BATTERY, CMD_GET_DEVICE_STATE, PETKIT_READ_UUID, RESP_BATTERY,
    RESP_DEVICE_CONFIG, RESP_DEVICE_STATE, PetkitFountain)


@pytest.fixture
def petkit_fountain():
    return PetkitFountain()

@pytest.fixture
def mock_bleak_client():
    client = AsyncMock(spec=BleakClient)
    client.is_connected = True
    return client

@pytest.mark.asyncio
async def test_async_custom_initialization_success(petkit_fountain, mock_bleak_client):
    # Mock _send_command_with_retry to return dummy data for successful initialization
    with patch.object(petkit_fountain,
                      '_send_command_with_retry',
                      new_callable=AsyncMock) as mock_send_command:
        mock_send_command.side_effect = [
            b'\x01\x02\x03\x04\x05\x06',  # details_payload (device_id)
            b'\x00',  # init_payload
            b'\x00',  # sync_payload
            asyncio.TimeoutError # Expected timeout for set_datetime
        ]

        result = await petkit_fountain.async_custom_initialization(mock_bleak_client)
        assert result is True
        assert petkit_fountain._is_initialized is True
        assert mock_bleak_client.start_notify.called
        assert petkit_fountain._device_id_bytes == b'\x01\x02\x03\x04\x05\x06'

@pytest.mark.asyncio
async def test_async_custom_initialization_client_not_connected(petkit_fountain, mock_bleak_client):
    mock_bleak_client.is_connected = False
    result = await petkit_fountain.async_custom_initialization(mock_bleak_client)
    assert result is False
    assert petkit_fountain._is_initialized is False

@pytest.mark.asyncio
async def test_async_custom_initialization_notify_failure(petkit_fountain, mock_bleak_client):
    mock_bleak_client.start_notify.side_effect = Exception("Notify failed")
    result = await petkit_fountain.async_custom_initialization(mock_bleak_client)
    assert result is False
    assert petkit_fountain._is_initialized is False

@pytest.mark.asyncio
async def test_async_custom_fetch_data_success(petkit_fountain, mock_bleak_client):
    petkit_fountain._is_initialized = True
    with patch.object(petkit_fountain,
                      '_send_command_with_retry',
                      new_callable=AsyncMock) as mock_send_command:
        mock_send_command.side_effect = [
            b'\x01',  # battery_payload
            b'\x01\x02\x03\x04\x05\x06\x05\x06\x07\x08\x0B\x0C',  # state_payload (mode 2 for Smart, pump_runtime 0x08070605)
            b'\x01\x02\x03\x04\x05\x06\x07\x08\x09'   # config_payload
        ]

        data = await petkit_fountain.async_custom_fetch_data(mock_bleak_client)
        assert data is not None
        assert data['battery'] == 1
        assert data["power_status"] is True
        assert data["mode"] == "Smart"
        assert data['warn_water'] is True
        assert data['warn_filter'] is True
        assert data['warn_breakdown'] is True
        assert data['filter_percent'] == 6
        assert data["pump_runtime"] == 134678021
        assert data['running_status'] == 'Running'
        assert data['dnd_state'] is True

@pytest.mark.asyncio
async def test_async_custom_fetch_data_not_initialized(petkit_fountain, mock_bleak_client):
    petkit_fountain._is_initialized = False
    data = await petkit_fountain.async_custom_fetch_data(mock_bleak_client)
    assert data is None

@pytest.mark.asyncio
async def test_async_set_power_status(petkit_fountain, mock_bleak_client):
    with patch.object(petkit_fountain,
                      '_send_command_and_wait',
                      new_callable=AsyncMock) as mock_send_command:
        mock_send_command.side_effect = [
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', # Initial state payload
            b'\x00' # Response for set command
        ]
        result = await petkit_fountain.async_set_power_status(mock_bleak_client, True)
        assert result is True
        # Verify that _send_command_and_wait was called with the correct new_state
    args, _ = mock_send_command.call_args_list[1]
    assert args[3][0] == 1 # Check the power status byte

@pytest.mark.asyncio
async def test_async_set_mode(petkit_fountain, mock_bleak_client):
    with patch.object(petkit_fountain,
                      '_send_command_and_wait',
                      new_callable=AsyncMock) as mock_send_command:
        mock_send_command.side_effect = [
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', # Initial state payload
            b'\x00' # Response for set command
        ]
        result = await petkit_fountain.async_set_mode(mock_bleak_client, "Smart")
        assert result is True
        # Verify that _send_command_and_wait was called with the correct new_state
    args, _ = mock_send_command.call_args_list[1]
    assert args[3][1] == 2 # Check the mode byte (2 for Smart)

@pytest.mark.asyncio
async def test_async_set_dnd_state(petkit_fountain, mock_bleak_client):
    with patch.object(petkit_fountain,
                      '_send_command_and_wait',
                      new_callable=AsyncMock) as mock_send_command:
        mock_send_command.side_effect = [
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00', # Initial config payload
            b'\x00' # Response for set command
        ]
        result = await petkit_fountain.async_set_dnd_state(mock_bleak_client, True)
        assert result is True
        # Verify that _send_command_and_wait was called with the correct new_config
    args, _ = mock_send_command.call_args_list[1]
    assert args[3][8] == 1 # Check the DND byte (1 for True)

@pytest.mark.asyncio
async def test_send_command_and_wait_success(petkit_fountain, mock_bleak_client):
    # Mock write_gatt_char to simulate sending command and receiving notification
    mock_bleak_client.write_gatt_char.return_value = None

    # Simulate notification coming in after command is sent
    async def mock_notify_callback(characteristic, data):
        await asyncio.sleep(0.1) # Simulate a small delay
        # This data should match the expected response format
        petkit_fountain._notification_handler(None, b'\x55\xAA\x06\x01\xD2\x01\x00\x00\x00\x00\x00\x00\x00') # Example response for CMD 210, seq 1

    mock_bleak_client.start_notify.side_effect = mock_notify_callback
    await mock_bleak_client.start_notify(PETKIT_READ_UUID, petkit_fountain._notification_handler)

    # Call the method under test
    response_task = asyncio.create_task(petkit_fountain._send_command_and_wait(
        mock_bleak_client, CMD_GET_DEVICE_STATE, 1, [0, 0], RESP_DEVICE_STATE
    ))
    await asyncio.sleep(0.2) # Allow some time for the command to be sent and future to be set
    await petkit_fountain._notification_handler(None, b'\x55\xAA\x06\x01\xD2\x01\x01\x00\x00\x00\x00\x00\x00') # Example response for CMD 210, seq 1 with 0x01 as first data byte
    response = await response_task
    assert response == b'\x01\x00\x00\x00\x00\x00'

@pytest.mark.asyncio
async def test_send_command_and_wait_timeout(petkit_fountain, mock_bleak_client):
    mock_bleak_client.write_gatt_char.return_value = None
    # Do not simulate notification, so it will time out
    with pytest.raises(asyncio.TimeoutError):
        await petkit_fountain._send_command_and_wait(
            mock_bleak_client, CMD_GET_DEVICE_STATE, 1, [0, 0], RESP_DEVICE_STATE, timeout=0.5
        )

@pytest.mark.asyncio
async def test_send_command_with_retry_success(petkit_fountain, mock_bleak_client):
    with patch.object(petkit_fountain,
                      '_send_command_and_wait',
                      new_callable=AsyncMock) as mock_send_command_and_wait:
        mock_send_command_and_wait.return_value = b'success'
        response = await petkit_fountain._send_command_with_retry(
            mock_bleak_client, CMD_GET_BATTERY, 1, [0, 0], RESP_BATTERY
        )
        assert response == b'success'
        assert mock_send_command_and_wait.call_count == 1

@pytest.mark.asyncio
async def test_send_command_with_retry_failure(petkit_fountain, mock_bleak_client):
    with patch.object(petkit_fountain,
                      '_send_command_and_wait',
                      new_callable=AsyncMock) as mock_send_command_and_wait:
        mock_send_command_and_wait.side_effect = asyncio.TimeoutError("Test Timeout")
        with pytest.raises(asyncio.TimeoutError):
            await petkit_fountain._send_command_with_retry(
                mock_bleak_client, CMD_GET_BATTERY, 1, [0, 0], RESP_BATTERY, retries=2, timeout=0.1
            )
        assert mock_send_command_and_wait.call_count == 2

@pytest.mark.asyncio
async def test_notification_handler_valid_data(petkit_fountain):
    petkit_fountain._expected_responses[1] = asyncio.Future()
    # Simulate a valid notification for sequence 1, command 210
    await petkit_fountain._notification_handler(None, b'\x55\xAA\x06\x01\xD2\x01\x00\x00\x00\x00\x00\x00\x00')
    assert petkit_fountain._expected_responses[1].done()
    assert petkit_fountain._expected_responses[1].result() == b'\x55\xAA\x06\x01\xD2\x01\x00\x00\x00\x00\x00\x00\x00'

@pytest.mark.asyncio
async def test_notification_handler_malformed_data(petkit_fountain):
    # Malformed data (too short)
    with patch('custom_components.ble_sensor.devices.petkit_fountain._LOGGER.warning') as mock_warning:
        await petkit_fountain._notification_handler(None, b'\x01\x02\x03')
        mock_warning.assert_called_with("Received malformed notification: %s", '010203')

@pytest.mark.asyncio
async def test_notification_handler_unsolicited_notification(petkit_fountain):
    # Unsolicited notification (sequence not in expected_responses)
    with patch('custom_components.ble_sensor.devices.petkit_fountain._LOGGER.debug') as mock_debug:
        await petkit_fountain._notification_handler(None, b'\x55\xAA\x06\x02\xD2\x01\x00\x00\x00\x00\x00\x00\x00') # seq 2
        mock_debug.assert_called_with("Received unsolicited notification for sequence %d (cmd %d)", 2, 210)
