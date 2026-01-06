"""BLE wake functionality for BLOOMIN device."""
from __future__ import annotations

import logging
from typing import Any

try:
    from bleak import BleakClient
    from bleak.exc import BleakError
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False
    BleakClient = None  # type: ignore[assignment, misc]
    BleakError = Exception  # type: ignore[assignment, misc]

_LOGGER = logging.getLogger(__name__)

# Default BLOOMIN BLE Service UUID (fallback if not discovered)
# Note: These UUIDs are placeholders and should be discovered during setup
# Based on https://github.com/mistrsoft/bloomin8_bt_wake:
# - Characteristic UUID: 0000f001-0000-1000-8000-00805f9b34fb
# - Wake command: 0x01 (single byte)
# Common BLE service patterns for wake/control:
# - Generic service: 0000ff00-0000-1000-8000-00805f9b34fb
# - Actual BLOOMIN8: 0000f001-0000-1000-8000-00805f9b34fb (characteristic)
DEFAULT_BLE_SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb"
DEFAULT_BLE_CHARACTERISTIC_UUID = "0000f001-0000-1000-8000-00805f9b34fb"

# Wake command
# Based on https://github.com/mistrsoft/bloomin8_bt_wake:
# - Wake command: 0x01 (single byte) to characteristic 0000f001-0000-1000-8000-00805f9b34fb
WAKE_COMMAND = bytes([0x01])


async def discover_ble_services(mac_address: str, timeout: float = 10.0) -> dict[str, str] | None:
    """Discover BLE services and characteristics for BLOOMIN device.
    
    Args:
        mac_address: BLE MAC address of the device
        timeout: Connection timeout in seconds
        
    Returns:
        Dictionary with 'service_uuid' and 'characteristic_uuid', or None if discovery fails
    """
    if not BLEAK_AVAILABLE:
        _LOGGER.warning("bleak library is not available for BLE discovery")
        return None
    
    if not mac_address:
        _LOGGER.error("BLE MAC address is required for discovery")
        return None
    
    # Normalize MAC address format
    mac_address = mac_address.upper().replace("-", ":").replace("_", ":")
    
    _LOGGER.info("Discovering BLE services for device: %s", mac_address)
    
    try:
        async with BleakClient(mac_address, timeout=timeout) as client:
            if not client.is_connected:
                _LOGGER.error("Failed to connect to BLE device for discovery: %s", mac_address)
                return None
            
            _LOGGER.debug("Connected to BLE device for discovery: %s", mac_address)
            
            # Get all services
            services = await client.get_services()
            
            # Look for writable characteristics (likely to be wake/control)
            discovered_service = None
            discovered_characteristic = None
            
            for service in services:
                _LOGGER.debug("Found service: %s", service.uuid)
                for char in service.characteristics:
                    _LOGGER.debug(
                        "Found characteristic: %s (properties: %s)",
                        char.uuid,
                        char.properties
                    )
                    # Look for writable characteristics (wake commands are typically writable)
                    # Prefer the known BLOOMIN8 wake characteristic UUID if found
                    # Based on https://github.com/mistrsoft/bloomin8_bt_wake: 0000f001-0000-1000-8000-00805f9b34fb
                    if "write" in char.properties:
                        # Prefer known BLOOMIN8 wake characteristic
                        if char.uuid.lower() == "0000f001-0000-1000-8000-00805f9b34fb":
                            discovered_service = service.uuid
                            discovered_characteristic = char.uuid
                            _LOGGER.info(
                                "Found BLOOMIN8 wake characteristic: service=%s, char=%s",
                                service.uuid,
                                char.uuid
                            )
                            break  # Found the specific one, no need to continue
                        elif not discovered_characteristic:
                            # Fallback to first writable characteristic
                            discovered_service = service.uuid
                            discovered_characteristic = char.uuid
                            _LOGGER.debug(
                                "Found writable characteristic: service=%s, char=%s",
                                service.uuid,
                                char.uuid
                            )
            
            if discovered_service and discovered_characteristic:
                result = {
                    "service_uuid": str(discovered_service),
                    "characteristic_uuid": str(discovered_characteristic),
                }
                _LOGGER.info(
                    "BLE discovery successful: service=%s, characteristic=%s",
                    result["service_uuid"],
                    result["characteristic_uuid"]
                )
                return result
            else:
                _LOGGER.warning("No writable characteristic found during BLE discovery")
                return None
                
    except BleakError as e:
        _LOGGER.error("BLE error during discovery: %s", e)
        return None
    except TimeoutError:
        _LOGGER.error("BLE connection timeout during discovery: %s", mac_address)
        return None
    except Exception as e:
        _LOGGER.error("Unexpected error during BLE discovery: %s", e, exc_info=True)
        return None


async def wake_device_via_ble(
    mac_address: str,
    service_uuid: str | None = None,
    characteristic_uuid: str | None = None,
    timeout: float = 10.0
) -> bool:
    """Wake up BLOOMIN device via BLE.
    
    Args:
        mac_address: BLE MAC address of the device (format: "AA:BB:CC:DD:EE:FF")
        service_uuid: BLE service UUID (if None, will use default or try to discover)
        characteristic_uuid: BLE characteristic UUID (if None, will use default or try to discover)
        timeout: Connection timeout in seconds
        
    Returns:
        True if wake command was sent successfully, False otherwise
    """
    if not BLEAK_AVAILABLE:
        _LOGGER.error("bleak library is not available. Install it with: pip install bleak")
        return False
    
    if not mac_address:
        _LOGGER.error("BLE MAC address is required")
        return False
    
    # Normalize MAC address format
    mac_address = mac_address.upper().replace("-", ":").replace("_", ":")
    
    _LOGGER.info("Attempting to wake BLOOMIN device via BLE: %s", mac_address)
    
    try:
        async with BleakClient(mac_address, timeout=timeout) as client:
            # Check if device is connected
            if not client.is_connected:
                _LOGGER.error("Failed to connect to BLE device: %s", mac_address)
                return False
            
            _LOGGER.debug("Connected to BLE device: %s", mac_address)
            
            # Use provided UUIDs or discover
            target_service_uuid = service_uuid or DEFAULT_BLE_SERVICE_UUID
            target_char_uuid = characteristic_uuid or DEFAULT_BLE_CHARACTERISTIC_UUID
            
            _LOGGER.debug(
                "Using BLE UUIDs - Service: %s, Characteristic: %s",
                target_service_uuid,
                target_char_uuid
            )
            
            # Try to find the service and characteristic
            services = await client.get_services()
            characteristic = None
            
            _LOGGER.debug("Scanning for BLE services and characteristics...")
            for service in services:
                _LOGGER.debug("Found service: %s", service.uuid)
                for char in service.characteristics:
                    _LOGGER.debug(
                        "Found characteristic: %s (properties: %s)",
                        char.uuid,
                        char.properties
                    )
                    # Try to match by provided UUID first
                    if target_char_uuid and char.uuid.lower() == target_char_uuid.lower():
                        if "write" in char.properties:
                            characteristic = char
                            _LOGGER.info("Found matching characteristic by UUID: %s", char.uuid)
                            break
                    # Also check for known BLOOMIN8 wake characteristic
                    elif char.uuid.lower() == "0000f001-0000-1000-8000-00805f9b34fb" and "write" in char.properties:
                        if not characteristic:
                            characteristic = char
                            _LOGGER.info("Found known BLOOMIN8 wake characteristic: %s", char.uuid)
                    elif not characteristic and "write" in char.properties:
                        # Fallback: use first writable characteristic
                        characteristic = char
                        _LOGGER.debug("Using fallback writable characteristic: %s", char.uuid)
            
            if not characteristic:
                _LOGGER.warning(
                    "Could not find wake characteristic. Trying provided/default UUID: %s",
                    target_char_uuid
                )
                # Try direct write with provided/default UUID
                try:
                    await client.write_gatt_char(
                        target_char_uuid,
                        WAKE_COMMAND,
                        response=True,
                    )
                    _LOGGER.info("Wake command sent via BLE (direct UUID)")
                    return True
                except (BleakError, AttributeError) as e:
                    _LOGGER.error("Failed to write to characteristic: %s", e)
                    return False
                except Exception as e:
                    _LOGGER.error("Unexpected error writing to characteristic: %s", e)
                    return False
            
            # Write wake command to characteristic
            await client.write_gatt_char(
                characteristic.uuid,
                WAKE_COMMAND,
                response=True,
            )
            
            _LOGGER.info("Wake command sent successfully via BLE")
            return True
            
    except BleakError as e:
        _LOGGER.error("BLE error while waking device: %s", e)
        return False
    except TimeoutError:
        _LOGGER.error("BLE connection timeout while waking device: %s", mac_address)
        return False
    except (OSError, PermissionError) as e:
        _LOGGER.error("System error while waking device via BLE (check Bluetooth permissions): %s", e)
        return False
    except Exception as e:
        _LOGGER.error("Unexpected error while waking device via BLE: %s", e, exc_info=True)
        return False

