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
- Use appropriate log levels (`debug` for detailed info, `error` for failures)

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
