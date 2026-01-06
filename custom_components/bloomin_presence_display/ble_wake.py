"""BLE wake functionality for BLOOMIN device."""
from __future__ import annotations

import logging
from typing import Any

try:
    from bleak import BleakClient, BleakScanner
    from bleak.exc import BleakError
    from bleak_retry_connector import establish_connection, BLEDeviceScanner
    BLEAK_AVAILABLE = True
    BLEAK_RETRY_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False
    BLEAK_RETRY_AVAILABLE = False
    BleakClient = None  # type: ignore[assignment, misc]
    BleakScanner = None  # type: ignore[assignment, misc]
    BleakError = Exception  # type: ignore[assignment, misc]
    establish_connection = None  # type: ignore[assignment, misc]
    BLEDeviceScanner = None  # type: ignore[assignment, misc]

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
    
    Note: This function is optional. If discovery fails, default UUIDs will be used.
    Discovery may fail with wrapper classes like HaBleakClientWrapper, but this is OK
    as wake_device_via_ble can work with default UUIDs.
    
    Args:
        mac_address: BLE MAC address of the device
        timeout: Connection timeout in seconds
        
    Returns:
        Dictionary with 'service_uuid' and 'characteristic_uuid', or None if discovery fails
    """
    if not BLEAK_AVAILABLE:
        _LOGGER.debug("bleak library is not available for BLE discovery")
        return None
    
    if not mac_address:
        _LOGGER.debug("BLE MAC address is required for discovery")
        return None
    
    # Normalize MAC address format
    mac_address = mac_address.upper().replace("-", ":").replace("_", ":")
    
    _LOGGER.debug("Attempting BLE service discovery for device: %s", mac_address)
    
    try:
        # Use bleak-retry-connector for more reliable connections
        if BLEAK_RETRY_AVAILABLE and establish_connection:
            # Use BLEDeviceScanner to ensure device is discovered before connecting
            scanner = None
            if BLEDeviceScanner:
                scanner = BLEDeviceScanner()
            
            client = await establish_connection(
                BleakClient,
                mac_address,
                name="BLOOMIN",
                scanner=scanner,
                timeout=timeout,
            )
            # establish_connection already connects, so check connection status
            if not client.is_connected:
                _LOGGER.error("Failed to connect to BLE device for discovery: %s", mac_address)
                return None
        else:
            # Fallback: try to scan first, then connect
            if BLEAK_AVAILABLE and BleakScanner:
                _LOGGER.debug("Scanning for BLE device: %s", mac_address)
                try:
                    device = await BleakScanner.find_device_by_address(
                        mac_address,
                        timeout=timeout,
                    )
                    if not device:
                        _LOGGER.error("BLE device not found during scan: %s", mac_address)
                        return None
                    _LOGGER.debug("Found BLE device: %s", mac_address)
                except Exception as e:
                    _LOGGER.warning("BLE scan failed: %s. Attempting direct connection.", e)
            
            client = BleakClient(mac_address, timeout=timeout)
            try:
                await client.connect()
                if not client.is_connected:
                    _LOGGER.error("Failed to connect to BLE device for discovery: %s", mac_address)
                    return None
            except Exception as e:
                _LOGGER.error("Failed to connect to BLE device: %s", e)
                return None
        
        try:
            _LOGGER.debug("Connected to BLE device for discovery: %s", mac_address)
            
            # Check if this is a wrapper class that doesn't support service discovery
            client_type_name = type(client).__name__
            if 'Wrapper' in client_type_name or 'HaBleak' in client_type_name:
                # Wrapper classes (like HaBleakClientWrapper) don't support get_services()
                # This is OK - we'll use default UUIDs which are known to work
                _LOGGER.debug(
                    "Skipping service discovery for wrapper class: %s. "
                    "Will use default UUIDs which are known to work for BLOOMIN8.",
                    client_type_name
                )
                return None
            
            # Get all services - handle both BleakClient and wrapper classes
            services = None
            try:
                # Method 1: Try get_services() method (standard BleakClient)
                if hasattr(client, 'get_services'):
                    try:
                        get_services_method = getattr(client, 'get_services')
                        if callable(get_services_method):
                            services = await get_services_method()
                    except AttributeError:
                        pass
                    except Exception as e:
                        _LOGGER.debug("Failed to call get_services: %s", e)
                
                # Method 2: Try services property
                if services is None and hasattr(client, 'services'):
                    try:
                        services = client.services
                        if hasattr(services, '__await__'):
                            services = await services
                    except AttributeError:
                        pass
                    except Exception as e:
                        _LOGGER.debug("Failed to access services property: %s", e)
                
                # Method 3: Try to access internal client if it's a wrapper
                if services is None:
                    internal_client = None
                    for attr_name in ['_client', 'client', '_ble_client']:
                        if hasattr(client, attr_name):
                            try:
                                internal_client = getattr(client, attr_name)
                                if internal_client and hasattr(internal_client, 'get_services'):
                                    services = await internal_client.get_services()
                                    break
                            except (AttributeError, Exception) as e:
                                _LOGGER.debug("Failed to access internal client via %s: %s", attr_name, e)
                                continue
                
            except Exception as e:
                # Any unexpected error - discovery is optional, so just return None
                _LOGGER.debug("Error during service discovery (this is OK): %s", e)
                return None
            
            if services is None:
                # This is OK - discovery is optional. Default UUIDs will be used.
                _LOGGER.debug(
                    "Could not access services from client (type: %s). "
                    "This is expected with some wrapper classes. Will use default UUIDs.",
                    client_type_name
                )
                return None
            
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
        finally:
            if client.is_connected:
                await client.disconnect()
                
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
    
    Implementation matches https://github.com/mistrsoft/bloomin8_bt_wake
    
    Args:
        mac_address: BLE MAC address of the device (format: "AA:BB:CC:DD:EE:FF")
        service_uuid: BLE service UUID (if None, will use default)
        characteristic_uuid: BLE characteristic UUID (if None, will use default: 0000f001-0000-1000-8000-00805f9b34fb)
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
    
    # Use provided UUIDs or defaults (matching bloomin8_bt_wake)
    target_char_uuid = characteristic_uuid or DEFAULT_BLE_CHARACTERISTIC_UUID
    
    _LOGGER.debug(
        "Using BLE Characteristic UUID: %s (from bloomin8_bt_wake)",
        target_char_uuid
    )
    
    try:
        # Use bleak-retry-connector for more reliable connections (matching Home Assistant best practices)
        if BLEAK_RETRY_AVAILABLE and establish_connection:
            # Use BLEDeviceScanner to ensure device is discovered before connecting
            scanner = None
            if BLEDeviceScanner:
                scanner = BLEDeviceScanner()
            
            client = await establish_connection(
                BleakClient,
                mac_address,
                name="BLOOMIN",
                scanner=scanner,
                timeout=timeout,
            )
            # establish_connection already connects, so check connection status
            if not client.is_connected:
                _LOGGER.error("Failed to connect to BLE device: %s", mac_address)
                return False
        else:
            # Fallback: try to scan first, then connect
            if BLEAK_AVAILABLE and BleakScanner:
                _LOGGER.debug("Scanning for BLE device: %s", mac_address)
                try:
                    device = await BleakScanner.find_device_by_address(
                        mac_address,
                        timeout=timeout,
                    )
                    if not device:
                        _LOGGER.error("BLE device not found during scan: %s", mac_address)
                        return False
                    _LOGGER.debug("Found BLE device: %s", mac_address)
                except Exception as e:
                    _LOGGER.warning("BLE scan failed: %s. Attempting direct connection.", e)
            
            client = BleakClient(mac_address, timeout=timeout)
            try:
                await client.connect()
                if not client.is_connected:
                    _LOGGER.error("Failed to connect to BLE device: %s", mac_address)
                    return False
            except Exception as e:
                _LOGGER.error("Failed to connect to BLE device: %s", e)
                return False
        
        try:
            _LOGGER.debug("Connected to BLE device: %s", mac_address)
            
            # Direct write to characteristic UUID (matching bloomin8_bt_wake implementation)
            # This is the simplest and most reliable method
            _LOGGER.debug("Writing wake command to characteristic: %s", target_char_uuid)
            await client.write_gatt_char(
                target_char_uuid,
                WAKE_COMMAND,
                response=True,
            )
            _LOGGER.info("Wake command sent successfully via BLE (matching bloomin8_bt_wake)")
            return True
            
        except BleakError as e:
            _LOGGER.error("BLE error writing to characteristic %s: %s", target_char_uuid, e)
            return False
        except Exception as e:
            _LOGGER.error("Unexpected error writing to characteristic: %s", e)
            return False
        finally:
            if client.is_connected:
                await client.disconnect()
            
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

