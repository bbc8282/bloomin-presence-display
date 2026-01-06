"""Config flow for BLOOMIN Presence Display integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ENTITY_ID, CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import (
    CONF_BLE_CHARACTERISTIC_UUID,
    CONF_BLE_MAC_ADDRESS,
    CONF_BLE_SERVICE_UUID,
    CONF_BLOOMIN_IP,
    CONF_IMAGE_PATH,
    CONF_IMAGE_QUALITY,
    CONF_IMAGE_SOURCE,
    CONF_MEDIA_FOLDER,
    CONF_OVERLAY_BADGE_SIZE,
    CONF_OVERLAY_FONT_SIZE,
    CONF_OVERLAY_ICON_SIZE,
    CONF_OVERLAY_MARGIN,
    CONF_OVERLAY_POSITION,
    CONF_OVERLAY_STYLE,
    CONF_PERSON_ENTITY,
    CONF_USE_BLE_WAKE,
    DEFAULT_IMAGE_QUALITY,
    DEFAULT_IMAGE_SOURCE,
    DEFAULT_MEDIA_FOLDER,
    DEFAULT_OVERLAY_BADGE_SIZE,
    DEFAULT_OVERLAY_FONT_SIZE,
    DEFAULT_OVERLAY_ICON_SIZE,
    DEFAULT_OVERLAY_MARGIN,
    DEFAULT_OVERLAY_POSITION,
    DEFAULT_OVERLAY_STYLE,
    DOMAIN,
    IMAGE_SOURCE_FILE,
    IMAGE_SOURCE_FOLDER,
    OVERLAY_POSITION_BOTTOM_RIGHT,
    OVERLAY_POSITION_BOTTOM_LEFT,
    OVERLAY_POSITION_TOP_RIGHT,
    OVERLAY_POSITION_TOP_LEFT,
    OVERLAY_STYLE_BADGE,
    OVERLAY_STYLE_TEXT,
    OVERLAY_STYLE_ICON,
)

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input and test connection."""
    # Validate person entity exists
    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(data[CONF_PERSON_ENTITY])
    if entity is None:
        raise ValueError("person_entity_not_found")
    
    # Validate image source configuration
    image_source = data.get(CONF_IMAGE_SOURCE, DEFAULT_IMAGE_SOURCE)
    if image_source == IMAGE_SOURCE_FOLDER:
        # Validate media folder exists
        media_folder = data.get(CONF_MEDIA_FOLDER, DEFAULT_MEDIA_FOLDER)
        if not media_folder:
            raise ValueError("media_folder_required")
    elif image_source == IMAGE_SOURCE_FILE:
        # Validate image path exists
        image_path = data.get(CONF_IMAGE_PATH, "")
        if not image_path:
            raise ValueError("image_path_required")
        
        # Check if file exists
        from pathlib import Path
        if Path(image_path).is_absolute():
            check_path = Path(image_path)
        else:
            media_dir = Path(hass.config.media_dirs.get("local", hass.config.path("media")))
            check_path = media_dir / image_path
        
        if not check_path.exists():
            raise ValueError("image_path_not_found")
        if not check_path.is_file():
            raise ValueError("image_path_not_file")
    
    # Validate BLE MAC address format if BLE wake is enabled
    if data.get(CONF_USE_BLE_WAKE):
        mac_address = data.get(CONF_BLE_MAC_ADDRESS, "")
        if not mac_address:
            raise ValueError("ble_mac_address_required")
        # Basic MAC address format validation (XX:XX:XX:XX:XX:XX)
        mac_normalized = mac_address.upper().replace("-", ":").replace("_", ":")
        parts = mac_normalized.split(":")
        if len(parts) != 6 or not all(len(part) == 2 and all(c in "0123456789ABCDEF" for c in part) for part in parts):
            raise ValueError("invalid_ble_mac_address")
    
    # Test wake functionality to verify device connection
    # This helps ensure the device is reachable before completing setup
    bloomin_ip = data.get(CONF_BLOOMIN_IP)
    use_ble_wake = data.get(CONF_USE_BLE_WAKE, False)
    ble_mac_address = data.get(CONF_BLE_MAC_ADDRESS, "")
    
    wake_success = False
    wake_method_used = None
    
    # Try BLE wake first if enabled
    if use_ble_wake and ble_mac_address:
        try:
            from .ble_wake import discover_ble_services, wake_device_via_ble
            
            # Discover BLE services and characteristics
            _LOGGER.info("Discovering BLE services during setup: %s", ble_mac_address)
            discovered = await discover_ble_services(ble_mac_address, timeout=5.0)
            
            if discovered:
                # Store discovered UUIDs in data
                data[CONF_BLE_SERVICE_UUID] = discovered["service_uuid"]
                data[CONF_BLE_CHARACTERISTIC_UUID] = discovered["characteristic_uuid"]
                _LOGGER.info(
                    "BLE discovery successful: service=%s, characteristic=%s",
                    discovered["service_uuid"],
                    discovered["characteristic_uuid"]
                )
            else:
                _LOGGER.warning(
                    "BLE discovery failed, will use default UUIDs. "
                    "Wake test may fail if defaults don't match your device."
                )
            
            # Test BLE wake with discovered or default UUIDs
            _LOGGER.info("Testing BLE wake during setup: %s", ble_mac_address)
            wake_success = await wake_device_via_ble(
                ble_mac_address,
                data.get(CONF_BLE_SERVICE_UUID),
                data.get(CONF_BLE_CHARACTERISTIC_UUID),
                timeout=5.0
            )
            if wake_success:
                _LOGGER.info("BLE wake test successful during setup")
                wake_method_used = "BLE"
            else:
                _LOGGER.debug("BLE wake test failed, will try other methods")
        except Exception as e:
            _LOGGER.debug("BLE wake test error: %s", e)
    
    # Try eink_display.whistle service
    if not wake_success:
        try:
            # Find BLOOMIN entity by IP
            for entity_id, entity in entity_registry.entities.items():
                if entity.platform == "bloomin8_eink_canvas" or "bloomin" in entity_id.lower():
                    if hasattr(entity, "config_entry_id") and entity.config_entry_id:
                        config_entry = hass.config_entries.async_get_entry(entity.config_entry_id)
                        if config_entry and config_entry.data.get("host") == bloomin_ip:
                            try:
                                await hass.services.async_call(
                                    "eink_display",
                                    "whistle",
                                    {"entity_id": entity_id},
                                )
                                wake_success = True
                                wake_method_used = "eink_display.whistle"
                                _LOGGER.info("eink_display.whistle test successful during setup")
                                break
                            except (ValueError, AttributeError, KeyError) as e:
                                _LOGGER.debug("eink_display.whistle test error (invalid parameters): %s", e)
                            except Exception as e:
                                _LOGGER.debug("eink_display.whistle test error: %s", e)
        except Exception as e:
            _LOGGER.debug("eink_display.whistle service lookup error: %s", e)
    
    # Try HTTP API wake as fallback
    if not wake_success:
        try:
            from .bloomin_api import BloominAPI
            
            # Discover API endpoints
            _LOGGER.info("Discovering API endpoints for device: %s", bloomin_ip)
            api = BloominAPI(bloomin_ip)
            discovered_endpoints = await api.discover_api_endpoints()
            
            if discovered_endpoints:
                # Store discovered endpoints in data
                if "upload" in discovered_endpoints:
                    data["api_upload_endpoint"] = discovered_endpoints["upload"]
                if "wake" in discovered_endpoints:
                    data["api_wake_endpoint"] = discovered_endpoints["wake"]
                _LOGGER.info(
                    "API endpoint discovery successful: %s",
                    discovered_endpoints
                )
                
                # Recreate API client with discovered endpoints
                api = BloominAPI(
                    bloomin_ip,
                    discovered_endpoints.get("upload"),
                    discovered_endpoints.get("wake")
                )
            else:
                _LOGGER.warning(
                    "API endpoint discovery failed, will use default endpoints. "
                    "Wake test may fail if defaults don't match your device."
                )
            
            # Test wake with discovered or default endpoints
            wake_success = await api.wake_device()
            if wake_success:
                wake_method_used = "HTTP API"
                _LOGGER.info("HTTP API wake test successful during setup")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.debug("HTTP API wake test network error: %s", e)
        except Exception as e:
            _LOGGER.debug("HTTP API wake test error: %s", e)
    
    # Log result
    if wake_success:
        _LOGGER.info(
            "Device wake test successful using %s. Setup can proceed.",
            wake_method_used or "unknown method"
        )
    else:
        _LOGGER.warning(
            "Could not wake device during setup using any method. "
            "Please verify: "
            "1. IP address is correct and device is on the same network, "
            "2. BLE MAC address is correct (if using BLE wake), "
            "3. BLOOMIN8 E-Ink Canvas integration is installed (for whistle service). "
            "Setup will continue, but device connectivity should be checked."
        )
        # Don't raise error - allow setup to continue so user can fix settings later
        # This is more user-friendly than blocking setup entirely
    
    return {"title": data.get(CONF_NAME, "BLOOMIN Presence Display")}


class BloominPresenceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BLOOMIN Presence Display."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        from .options_flow import BloominPresenceOptionsFlowHandler
        return BloominPresenceOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Show progress indicator during validation (which includes wake test)
                info = await validate_input(self.hass, user_input)
            except ValueError as err:
                errors["base"] = str(err)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Validation successful (including wake test)
                return self.async_create_entry(title=info["title"], data=user_input)

        # Build schema dynamically based on image source and BLE wake selection
        image_source = DEFAULT_IMAGE_SOURCE
        if user_input:
            image_source = user_input.get(CONF_IMAGE_SOURCE, DEFAULT_IMAGE_SOURCE)
        
        schema_dict = {
            vol.Required(CONF_NAME, default="BLOOMIN Presence Display"): str,
            vol.Required(CONF_BLOOMIN_IP): str,
            vol.Required(CONF_PERSON_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="person")
            ),
            vol.Required(
                CONF_IMAGE_SOURCE, default=DEFAULT_IMAGE_SOURCE
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        IMAGE_SOURCE_FOLDER,
                        IMAGE_SOURCE_FILE,
                    ],
                    translation_key="image_source",
                )
            ),
            vol.Optional(CONF_USE_BLE_WAKE, default=False): bool,
            vol.Optional(
                CONF_OVERLAY_POSITION, default=DEFAULT_OVERLAY_POSITION
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        OVERLAY_POSITION_BOTTOM_RIGHT,
                        OVERLAY_POSITION_BOTTOM_LEFT,
                        OVERLAY_POSITION_TOP_RIGHT,
                        OVERLAY_POSITION_TOP_LEFT,
                    ],
                    translation_key="overlay_position",
                )
            ),
                vol.Optional(
                    CONF_OVERLAY_STYLE, default=DEFAULT_OVERLAY_STYLE
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            OVERLAY_STYLE_BADGE,
                            OVERLAY_STYLE_TEXT,
                            OVERLAY_STYLE_ICON,
                        ],
                        translation_key="overlay_style",
                    )
                ),
                vol.Optional(
                    CONF_IMAGE_QUALITY, default=DEFAULT_IMAGE_QUALITY
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
                vol.Optional(
                    CONF_OVERLAY_BADGE_SIZE, default=DEFAULT_OVERLAY_BADGE_SIZE
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=200)),
                vol.Optional(
                    CONF_OVERLAY_ICON_SIZE, default=DEFAULT_OVERLAY_ICON_SIZE
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=200)),
                vol.Optional(
                    CONF_OVERLAY_FONT_SIZE, default=DEFAULT_OVERLAY_FONT_SIZE
                ): vol.All(vol.Coerce(int), vol.Range(min=8, max=72)),
                vol.Optional(
                    CONF_OVERLAY_MARGIN, default=DEFAULT_OVERLAY_MARGIN
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            }
        
        # Conditionally add image source specific fields
        if image_source == IMAGE_SOURCE_FOLDER:
            schema_dict[vol.Required(
                CONF_MEDIA_FOLDER,
                default=user_input.get(CONF_MEDIA_FOLDER, DEFAULT_MEDIA_FOLDER) if user_input else DEFAULT_MEDIA_FOLDER
            )] = str
        elif image_source == IMAGE_SOURCE_FILE:
            schema_dict[vol.Required(
                CONF_IMAGE_PATH,
                default=user_input.get(CONF_IMAGE_PATH, "") if user_input else ""
            )] = str
        
        # Conditionally add BLE MAC address field
        # If user has already selected BLE wake, make it required
        if user_input and user_input.get(CONF_USE_BLE_WAKE):
            schema_dict[vol.Required(CONF_BLE_MAC_ADDRESS)] = str
        else:
            schema_dict[vol.Optional(CONF_BLE_MAC_ADDRESS)] = str

        data_schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

