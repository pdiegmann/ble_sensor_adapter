# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Home Assistant custom component called "BLE Sensor" that actively connects to Bluetooth Low Energy (BLE) devices to retrieve data. The component is specifically designed and optimized for Petkit fountain devices, with a simplified architecture focused on this single device type.

## Development Commands

### Testing
```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=custom_components.ble_sensor --cov-report=term-missing

# Run specific test file
pytest tests/components/ble_sensor/test_coordinator.py

# Run tests in verbose mode
pytest -v

# Debug specific tests (e.g., for BLE sensor functionality)
PYTHONPATH=/Users/philhennel/Downloads/ble_sensor_adapter pytest tests/components/ble_sensor/test_sensor.py -v
```

### Building and Installation
The component can be installed via HACS or manually copied to the `custom_components` directory in Home Assistant.

### Dependencies
All dependencies are defined in `pyproject.toml`. Key dependencies include:
- `bleak>=0.22.3` - BLE communication
- `bleak-retry-connector>=3.10.0` - Reliable BLE connections
- `homeassistant>=2024.12.5` - Home Assistant core
- `pytest-homeassistant-custom-component>=0.13.206` - Testing framework

## Architecture

### Core Components

**Custom Component Structure:**
- `custom_components/ble_sensor/` - Main component directory
- `__init__.py` - Integration setup and platform forwarding
- `coordinator.py` - Data update coordinator managing all devices
- `config_flow.py` - UI-based configuration flow
- `manifest.json` - Component metadata and dependencies

**Entity Platforms:**
- `sensor.py` - Sensor entities (battery, filter life, etc.)
- `binary_sensor.py` - Binary sensor entities (warnings, status)
- `switch.py` - Switch entities (power, DND mode)
- `select.py` - Select entities (mode selection)

**Device Architecture:**
- `devices/base.py` - Abstract base class for device types (simplified)
- `devices/device.py` - BLE device model
- `devices/__init__.py` - Simplified device registry (Petkit-only)
- `devices/petkit_fountain.py` - Petkit fountain device handler (primary implementation)

### Key Design Patterns

**Data Coordination:**
The `BLESensorCoordinator` manages data updates for multiple devices with individual polling intervals. It:
- Tracks device availability based on successful BLE connections
- Manages device-specific update timing
- Handles BLE connection failures gracefully
- Stores device data and status separately

**Device Type System (Simplified):**
The Petkit fountain device implements the `DeviceType` abstract base class:
- `async_custom_fetch_data()` - Main data retrieval method
- `get_entity_descriptions()` - Define available entities
- `parse_raw_data()` - Process raw BLE data
- `requires_polling()` - Indicate if polling is needed (always true for Petkit)

The device type system is simplified since only Petkit fountains are supported, removing complex device type lookups and mappings.

**Configuration Flow (Simplified):**
Supports both manual MAC address entry and Bluetooth discovery:
- Auto-discovery of nearby connectable BLE devices
- Implicit device type (always Petkit Fountain) - no selection needed
- Options flow for polling intervals and retry counts

The configuration flow is streamlined since device type is implicit.

### Constants and Configuration

**Key Constants** (`utils/const.py`):
- Petkit fountain entity keys and configuration
- Configuration field names
- Default values for polling intervals
- Simplified device type constants (Petkit-only)

**Configuration Structure:**
- Config entry data contains device list or legacy single device
- Options contain global settings like polling intervals
- Device configs include MAC address, type, name, and individual polling intervals

### Testing Architecture

**Test Structure:**
- `tests/components/ble_sensor/` - Component-specific tests
- `tests/mock_homeassistant/` - Mock Home Assistant framework
- `conftest.py` - Shared test fixtures and mocks

**Mock Framework:**
The project includes a complete mock Home Assistant framework to enable isolated testing without full HA installation.

## Development Guidelines

### Architecture Overview (Simplified for Petkit-Only)

The architecture has been simplified to focus exclusively on Petkit fountain devices:

1. **Device Registry** (`devices/__init__.py`) - Simplified to return Petkit fountain handler by default
2. **Configuration Flow** - Device type selection removed (implicit Petkit Fountain)
3. **Entity Creation** - Streamlined without device type lookups
4. **Constants** - Focused on Petkit fountain specific keys only

### Future Device Type Extensions

To add new device types in the future:
1. Create new device handler in `devices/` directory extending `DeviceType`
2. Update `get_device_type()` function in `devices/__init__.py`
3. Add device type to configuration flow
4. Update constants and entity creation patterns

### BLE Connection Management

Use `bleak-retry-connector` for reliable connections:
```python
client = await establish_connection(
    client_class=BleakClient,
    device=ble_device,
    name=ble_device.address,
    timeout=10.0
)
```

Always implement proper connection cleanup in finally blocks.

### Entity Implementation (Simplified)

Entities are streamlined for Petkit fountain support:
- Inherit from appropriate base classes (`BLESensorEntity`, etc.)
- Use coordinator data via `self.coordinator.get_device_data(device_id)`
- Check availability via `self.coordinator.is_device_available(device_id)`
- Entity descriptions are retrieved once per device type (not per device)
- Simplified entity creation without device type validation loops

### Error Handling

The component emphasizes graceful error handling:
- BLE connection timeouts should not crash the component
- Device unavailability should be reflected in entity availability
- Parsing errors should be logged but not prevent other devices from updating
- Use appropriate log levels (`info` for status updates, `warning` for issues, `error` for failures)
- Device initialization state is reset for each BLE connection session to prevent stale state issues

### Configuration and Options

The config flow supports:
- Initial device setup with MAC address and device type
- Options flow for adjusting polling intervals and retry counts
- Bluetooth discovery integration for easier setup
- Multiple device configuration through the devices list

## Project Structure Notes

**Mock Framework:** The `homeassistant/` and `tests/mock_homeassistant/` directories contain a minimal mock implementation of Home Assistant core components, allowing for isolated testing.

**Device Data Flow:**
1. Coordinator polls devices based on individual intervals
2. Device handlers connect via BLE and fetch raw data
3. Raw data is parsed into entity state values
4. Entities retrieve data from coordinator on state requests

**Integration Type:** This is a "device" integration that creates device entries in Home Assistant, with entities linked to those devices.

## Recent Improvements and Debugging

### Deprecation Warning Fix
- **Fixed Config import deprecation**: Resolved "The deprecated alias Config was used from ble_sensor" warning
- **Backward compatibility**: Uses `try/except` import pattern for compatibility with older Home Assistant versions
- **Future-proofing**: Ready for Home Assistant 2025.11 when old import path is removed

### Entity Availability Fix (Latest)
- **Fixed entity availability logic**: Removed dependency on global coordinator success, now focuses only on device-specific availability
- **Resolved initialization state issues**: Device initialization state is properly reset for each BLE connection session
- **Enhanced logging visibility**: Changed critical logs from DEBUG to INFO/WARNING levels for better troubleshooting

### Debugging Features Added
- **Comprehensive lifecycle logging**: Integration setup, coordinator cycles, and platform registration
- **BLE operation visibility**: Detailed connection attempts, initialization sequences, and data fetch results  
- **Entity creation tracking**: Logs show sensor entity creation counts and unique IDs
- **Device processing details**: Update timing, BLE device discovery, and connection status

### Troubleshooting Tips
When entities show as unavailable:
1. Check Home Assistant logs for INFO-level messages from `custom_components.ble_sensor`
2. Verify device is powered on, nearby, and not connected to other apps
3. Look for BLE connection establishment and initialization sequence logs
4. Monitor coordinator update cycles and device processing messages

### Root Cause Analysis (Latest)
**Issue**: `async_ble_device_from_address()` returns `None` causing "Device not currently reachable via Bluetooth"

**Root Causes Identified**:
1. **Home Assistant Bluetooth integration** may not be properly discovering the device
2. **Device power/connectivity** - fountain may be off, connected to another app, or out of range
3. **MAC address formatting** - inconsistent case or format issues
4. **Bluetooth adapter issues** - no working adapters or scanning problems

**Enhanced Diagnostics Added**:
- Bluetooth integration health checks on startup
- Alternative BLE device discovery methods
- Comprehensive discovered devices listing
- MAC address validation and normalization
- Actionable troubleshooting guidance in logs

### Log Analysis
Key log messages to look for:
- `"Setting up BLE Sensor integration"` - Integration startup
- `"Bluetooth integration OK: Found X adapter(s)"` - Bluetooth health check
- `"Coordinator update cycle starting"` - Update cycles beginning
- `"Device X not found in Y discovered devices"` - BLE discovery analysis
- `"TROUBLESHOOTING TIPS for device"` - Actionable guidance
- `"BLE connection established"` - Successful BLE connections
- `"Successfully fetched and parsed data"` - Data retrieval success

## Troubleshooting Guide

### "Device not currently reachable via Bluetooth"

This is the most common issue. Follow these steps in order:

#### Step 1: Check Device Status
1. **Power**: Ensure your Petkit fountain is powered ON and has water
2. **Proximity**: Device should be within 10 meters of Home Assistant
3. **App Connection**: Disconnect from the Petkit mobile app if connected
4. **Power Cycle**: Turn the fountain off and on again

#### Step 2: Verify Home Assistant Bluetooth
1. Go to **Settings > Devices & Services**
2. Check that **Bluetooth** integration is installed and working
3. Look for error messages in the Bluetooth integration
4. If needed, reload or restart the Bluetooth integration

#### Step 3: Check BLE Discovery
Look in Home Assistant logs for these specific messages:
- `"Bluetooth integration OK: Found X adapter(s)"` - Should show at least 1 adapter
- `"Device [MAC] not found in Y discovered devices"` - Shows how many BLE devices are discovered
- `"Available devices: [list]"` - Shows what devices ARE being discovered

#### Step 4: Advanced Diagnostics
If the above doesn't work:
1. **Check MAC Address**: Ensure the configured MAC address exactly matches your device
2. **Bluetooth Adapter**: Verify your system's Bluetooth adapter is working (try pairing another device)
3. **Home Assistant Restart**: Sometimes a full Home Assistant restart helps reset BLE scanning
4. **System Bluetooth**: On the host system, try `bluetoothctl scan on` to see if the device appears

#### Step 5: Alternative Discovery
The integration now checks multiple discovery methods and will show:
- Whether the device appears in Home Assistant's discovered devices list
- Signal strength (RSSI) if detected
- Comparison with other nearby BLE devices

### Device Shows as Unavailable After Connection
This indicates BLE connection succeeded but data parsing failed:
1. Check for initialization errors in logs
2. Look for timeout or protocol errors
3. Verify the device is a supported Petkit fountain model
