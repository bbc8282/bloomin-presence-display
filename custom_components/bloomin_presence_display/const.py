"""Constants for BLOOMIN Presence Display integration."""
from typing import Final

DOMAIN: Final = "bloomin_presence_display"

# Configuration keys
CONF_BLOOMIN_IP: Final = "bloomin_ip"
CONF_BLE_MAC_ADDRESS: Final = "ble_mac_address"
CONF_BLE_SERVICE_UUID: Final = "ble_service_uuid"
CONF_BLE_CHARACTERISTIC_UUID: Final = "ble_characteristic_uuid"
CONF_USE_BLE_WAKE: Final = "use_ble_wake"
CONF_PERSON_ENTITY: Final = "person_entity"
CONF_PERSON_ENTITIES: Final = "person_entities"  # For multiple person support
CONF_IMAGE_SOURCE: Final = "image_source"
CONF_MEDIA_FOLDER: Final = "media_folder"
CONF_IMAGE_PATH: Final = "image_path"
CONF_OVERLAY_POSITION: Final = "overlay_position"
CONF_OVERLAY_STYLE: Final = "overlay_style"
CONF_IMAGE_QUALITY: Final = "image_quality"
CONF_OVERLAY_BADGE_SIZE: Final = "overlay_badge_size"
CONF_OVERLAY_ICON_SIZE: Final = "overlay_icon_size"
CONF_OVERLAY_FONT_SIZE: Final = "overlay_font_size"
CONF_OVERLAY_MARGIN: Final = "overlay_margin"

# Default values
DEFAULT_MEDIA_FOLDER: Final = "bloomin_display"
DEFAULT_IMAGE_SOURCE: Final = "folder"
DEFAULT_OVERLAY_POSITION: Final = "bottom_right"
DEFAULT_OVERLAY_STYLE: Final = "badge"
DEFAULT_IMAGE_QUALITY: Final = 95
DEFAULT_OVERLAY_BADGE_SIZE: Final = 40
DEFAULT_OVERLAY_ICON_SIZE: Final = 32
DEFAULT_OVERLAY_FONT_SIZE: Final = 16
DEFAULT_OVERLAY_MARGIN: Final = 15

# Image source options
IMAGE_SOURCE_FOLDER: Final = "folder"
IMAGE_SOURCE_FILE: Final = "file"

# Overlay positions
OVERLAY_POSITION_BOTTOM_RIGHT: Final = "bottom_right"
OVERLAY_POSITION_BOTTOM_LEFT: Final = "bottom_left"
OVERLAY_POSITION_TOP_RIGHT: Final = "top_right"
OVERLAY_POSITION_TOP_LEFT: Final = "top_left"

# Overlay styles
OVERLAY_STYLE_BADGE: Final = "badge"
OVERLAY_STYLE_TEXT: Final = "text"
OVERLAY_STYLE_ICON: Final = "icon"

# Person states
PERSON_STATE_HOME: Final = "home"
PERSON_STATE_AWAY: Final = "away"
PERSON_STATE_NOT_HOME: Final = "not_home"

# Service names
SERVICE_UPDATE_DISPLAY: Final = "update_display"
SERVICE_FORCE_REFRESH: Final = "force_refresh"

