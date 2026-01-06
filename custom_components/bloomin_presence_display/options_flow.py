"""Options flow for BLOOMIN Presence Display integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_BLE_MAC_ADDRESS,
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


class BloominPresenceOptionsFlowHandler(OptionsFlow):
    """Handle options flow for BLOOMIN Presence Display."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # Validate image source configuration
            image_source = user_input.get(CONF_IMAGE_SOURCE, DEFAULT_IMAGE_SOURCE)
            if image_source == IMAGE_SOURCE_FOLDER:
                media_folder = user_input.get(CONF_MEDIA_FOLDER, "")
                if not media_folder:
                    errors["base"] = "media_folder_required"
            elif image_source == IMAGE_SOURCE_FILE:
                image_path = user_input.get(CONF_IMAGE_PATH, "")
                if not image_path:
                    errors["base"] = "image_path_required"
                else:
                    # Check if file exists
                    from pathlib import Path
                    if Path(image_path).is_absolute():
                        check_path = Path(image_path)
                    else:
                        media_dir = Path(self.hass.config.media_dirs.get("local", self.hass.config.path("media")))
                        check_path = media_dir / image_path
                    
                    if not check_path.exists():
                        errors["base"] = "image_path_not_found"
                    elif not check_path.is_file():
                        errors["base"] = "image_path_not_file"
            
            # Validate BLE MAC address if BLE wake is enabled
            if user_input.get(CONF_USE_BLE_WAKE):
                mac_address = user_input.get(CONF_BLE_MAC_ADDRESS, "")
                if not mac_address:
                    errors["base"] = "ble_mac_address_required"
                else:
                    # Validate MAC address format
                    mac_normalized = mac_address.upper().replace("-", ":").replace("_", ":")
                    parts = mac_normalized.split(":")
                    if len(parts) != 6 or not all(len(part) == 2 and all(c in "0123456789ABCDEF" for c in part) for part in parts):
                        errors["base"] = "invalid_ble_mac_address"
            
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        data = self.config_entry.data
        
        # Get current image source
        image_source = data.get(CONF_IMAGE_SOURCE, DEFAULT_IMAGE_SOURCE)
        if user_input:
            image_source = user_input.get(CONF_IMAGE_SOURCE, image_source)

        # Build schema
        schema_dict = {
            vol.Optional(
                CONF_IMAGE_SOURCE,
                default=data.get(CONF_IMAGE_SOURCE, DEFAULT_IMAGE_SOURCE),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        IMAGE_SOURCE_FOLDER,
                        IMAGE_SOURCE_FILE,
                    ],
                    translation_key="image_source",
                )
            ),
            vol.Optional(
                CONF_OVERLAY_POSITION,
                default=options.get(CONF_OVERLAY_POSITION, DEFAULT_OVERLAY_POSITION),
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
                CONF_OVERLAY_STYLE,
                default=options.get(CONF_OVERLAY_STYLE, DEFAULT_OVERLAY_STYLE),
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
                CONF_IMAGE_QUALITY,
                default=options.get(CONF_IMAGE_QUALITY, data.get(CONF_IMAGE_QUALITY, DEFAULT_IMAGE_QUALITY)),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
            vol.Optional(
                CONF_OVERLAY_BADGE_SIZE,
                default=options.get(CONF_OVERLAY_BADGE_SIZE, data.get(CONF_OVERLAY_BADGE_SIZE, DEFAULT_OVERLAY_BADGE_SIZE)),
            ): vol.All(vol.Coerce(int), vol.Range(min=10, max=200)),
            vol.Optional(
                CONF_OVERLAY_ICON_SIZE,
                default=options.get(CONF_OVERLAY_ICON_SIZE, data.get(CONF_OVERLAY_ICON_SIZE, DEFAULT_OVERLAY_ICON_SIZE)),
            ): vol.All(vol.Coerce(int), vol.Range(min=10, max=200)),
            vol.Optional(
                CONF_OVERLAY_FONT_SIZE,
                default=options.get(CONF_OVERLAY_FONT_SIZE, data.get(CONF_OVERLAY_FONT_SIZE, DEFAULT_OVERLAY_FONT_SIZE)),
            ): vol.All(vol.Coerce(int), vol.Range(min=8, max=72)),
            vol.Optional(
                CONF_OVERLAY_MARGIN,
                default=options.get(CONF_OVERLAY_MARGIN, data.get(CONF_OVERLAY_MARGIN, DEFAULT_OVERLAY_MARGIN)),
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Optional(
                CONF_USE_BLE_WAKE,
                default=options.get(CONF_USE_BLE_WAKE, data.get(CONF_USE_BLE_WAKE, False)),
            ): bool,
        }
        
        # Conditionally add image source specific fields
        if image_source == IMAGE_SOURCE_FOLDER:
            schema_dict[vol.Required(
                CONF_MEDIA_FOLDER,
                default=data.get(CONF_MEDIA_FOLDER, DEFAULT_MEDIA_FOLDER),
            )] = str
        elif image_source == IMAGE_SOURCE_FILE:
            schema_dict[vol.Required(
                CONF_IMAGE_PATH,
                default=data.get(CONF_IMAGE_PATH, ""),
            )] = str
        
        # Conditionally add BLE MAC address field
        if user_input and user_input.get(CONF_USE_BLE_WAKE) or data.get(CONF_USE_BLE_WAKE, False):
            schema_dict[vol.Required(
                CONF_BLE_MAC_ADDRESS,
                default=data.get(CONF_BLE_MAC_ADDRESS, ""),
            )] = str
        else:
            schema_dict[vol.Optional(
                CONF_BLE_MAC_ADDRESS,
                default=data.get(CONF_BLE_MAC_ADDRESS, ""),
            )] = str

        data_schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )

