"""Data coordinator for BLOOMIN Presence Display."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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
    CONF_PERSON_ENTITY,
    CONF_USE_BLE_WAKE,
    DEFAULT_IMAGE_QUALITY,
    DEFAULT_OVERLAY_BADGE_SIZE,
    DEFAULT_OVERLAY_FONT_SIZE,
    DEFAULT_OVERLAY_ICON_SIZE,
    DEFAULT_OVERLAY_MARGIN,
    DOMAIN,
    IMAGE_SOURCE_FILE,
    IMAGE_SOURCE_FOLDER,
    PERSON_STATE_HOME,
)
from .image_processor import ImageProcessor
from .bloomin_api import BloominAPI
from .ble_wake import wake_device_via_ble

_LOGGER = logging.getLogger(__name__)


class BloominPresenceCoordinator:
    """Class to manage BLOOMIN Presence Display operations."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.hass = hass
        self.bloomin_ip = entry.data[CONF_BLOOMIN_IP]
        self.person_entity = entry.data[CONF_PERSON_ENTITY]
        self.image_source = entry.data.get(CONF_IMAGE_SOURCE, IMAGE_SOURCE_FOLDER)
        self.media_folder = entry.data.get(CONF_MEDIA_FOLDER, "bloomin_display")
        self.image_path = entry.data.get(CONF_IMAGE_PATH, "")
        self.use_ble_wake = entry.data.get(CONF_USE_BLE_WAKE, False)
        self.ble_mac_address = entry.data.get(CONF_BLE_MAC_ADDRESS, "")
        self.ble_service_uuid = entry.data.get(CONF_BLE_SERVICE_UUID)
        self.ble_characteristic_uuid = entry.data.get(CONF_BLE_CHARACTERISTIC_UUID)
        
        # Initialize API client with discovered endpoints (if any)
        upload_endpoint = entry.data.get("api_upload_endpoint")
        wake_endpoint = entry.data.get("api_wake_endpoint")
        self.bloomin_api = BloominAPI(self.bloomin_ip, upload_endpoint, wake_endpoint)
        self.image_processor = ImageProcessor(self.hass)

    def get_media_folder_path(self) -> Path:
        """Get the full path to the media folder."""
        media_dir = Path(self.hass.config.media_dirs.get("local", self.hass.config.path("media")))
        return media_dir / self.media_folder

    def get_image_path(self) -> Path | None:
        """Get image path based on image source setting."""
        _LOGGER.debug("Getting image path (source: %s)", self.image_source)
        
        if self.image_source == IMAGE_SOURCE_FILE:
            # Use specific image file
            if not self.image_path:
                _LOGGER.warning("Image path not configured for file source mode")
                return None
            
            _LOGGER.debug("Using file source mode, image_path: %s", self.image_path)
            
            # Handle both absolute and relative paths
            if Path(self.image_path).is_absolute():
                image_path = Path(self.image_path)
                _LOGGER.debug("Using absolute path: %s", image_path)
            else:
                # Relative to media directory
                media_dir = Path(self.hass.config.media_dirs.get("local", self.hass.config.path("media")))
                image_path = media_dir / self.image_path
                _LOGGER.debug("Using relative path (media_dir: %s, final: %s)", media_dir, image_path)
            
            if not image_path.exists():
                _LOGGER.error("Image file does not exist: %s", image_path)
                return None
            
            if not image_path.is_file():
                _LOGGER.error("Image path is not a file: %s", image_path)
                return None
            
            _LOGGER.info("Found image file: %s", image_path)
            return image_path
        else:
            # Use random image from folder
            _LOGGER.debug("Using folder source mode, folder: %s", self.media_folder)
            return self.get_latest_image()
    
    def get_latest_image(self) -> Path | None:
        """Get a random image from the media folder."""
        import random
        
        folder_path = self.get_media_folder_path()
        _LOGGER.debug("Looking for images in folder: %s", folder_path)
        
        if not folder_path.exists():
            _LOGGER.warning("Media folder does not exist: %s", folder_path)
            return None
        
        if not folder_path.is_dir():
            _LOGGER.error("Media folder path is not a directory: %s", folder_path)
            return None
        
        # Find all image files
        image_extensions = {".jpg", ".jpeg", ".png", ".bmp"}
        try:
            image_files = [
                f for f in folder_path.iterdir()
                if f.is_file() and f.suffix.lower() in image_extensions
            ]
        except PermissionError as e:
            _LOGGER.error("Permission denied accessing media folder: %s - %s", folder_path, e)
            return None
        except Exception as e:
            _LOGGER.error("Error reading media folder: %s - %s", folder_path, e)
            return None
        
        if not image_files:
            _LOGGER.warning("No images found in media folder: %s (supported formats: %s)", 
                          folder_path, ", ".join(image_extensions))
            return None
        
        # Return a random image from the folder
        selected_image = random.choice(image_files)
        _LOGGER.info("Selected random image: %s from %d total images in folder: %s", 
                    selected_image.name, len(image_files), folder_path)
        return selected_image

    def _find_bloomin_entity(self) -> str | None:
        """Find the BLOOMIN media_player entity matching our IP."""
        entity_registry = er.async_get(self.hass)
        _LOGGER.debug("Searching for BLOOMIN entity with IP: %s", self.bloomin_ip)
        
        # Look for media_player entities that match our BLOOMIN IP
        matching_entities = []
        for entity_id, entity in entity_registry.entities.items():
            if entity.platform == "bloomin8_eink_canvas" or "bloomin" in entity_id.lower():
                # Check if this entity matches our IP
                if hasattr(entity, "config_entry_id") and entity.config_entry_id:
                    config_entry = self.hass.config_entries.async_get_entry(entity.config_entry_id)
                    if config_entry:
                        entity_ip = config_entry.data.get("host") or config_entry.data.get("ip_address")
                        _LOGGER.debug("Found potential entity: %s (IP: %s)", entity_id, entity_ip)
                        if entity_ip == self.bloomin_ip:
                            matching_entities.append(entity_id)
                            _LOGGER.debug("Entity IP matches: %s", entity_id)
        
        if matching_entities:
            _LOGGER.info("Found %d matching BLOOMIN entity(ies): %s", len(matching_entities), matching_entities)
            return matching_entities[0]  # Return first match
        
        _LOGGER.warning("No BLOOMIN entity found matching IP: %s", self.bloomin_ip)
        return None

    async def wake_device(self) -> None:
        """Wake up BLOOMIN device using BLE, eink_display.whistle service, or API."""
        # Priority order:
        # 1. BLE wake (if enabled and MAC address provided)
        # 2. eink_display.whistle service (recommended for WiFi-based wake)
        # 3. HTTP API wake endpoint (fallback)
        
        # Try BLE wake first if enabled
        if self.use_ble_wake and self.ble_mac_address:
            _LOGGER.info(
                "Attempting to wake device via BLE: %s (service: %s, char: %s)",
                self.ble_mac_address,
                self.ble_service_uuid or "default",
                self.ble_characteristic_uuid or "default"
            )
            success = await wake_device_via_ble(
                self.ble_mac_address,
                self.ble_service_uuid,
                self.ble_characteristic_uuid
            )
            if success:
                _LOGGER.info("Successfully woke up BLOOMIN device via BLE")
                return
            else:
                _LOGGER.warning("BLE wake failed, trying fallback methods")
        
        # Try eink_display.whistle service (recommended method)
        bloomin_entity = self._find_bloomin_entity()
        
        if bloomin_entity:
            try:
                await self.hass.services.async_call(
                    "eink_display",
                    "whistle",
                    {"entity_id": bloomin_entity},
                )
                _LOGGER.info("Woke up BLOOMIN device using eink_display.whistle service")
                return
            except (ValueError, AttributeError, KeyError) as e:
                _LOGGER.debug("Could not use eink_display.whistle service: %s", e)
            except Exception as e:
                _LOGGER.warning("Unexpected error using eink_display.whistle service: %s", e)
        
        # Fallback: try HTTP API wake endpoint
        try:
            success = await self.bloomin_api.wake_device()
            if success:
                _LOGGER.info("Woke up BLOOMIN device via HTTP API")
            else:
                _LOGGER.warning("Failed to wake BLOOMIN device via HTTP API")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.warning("Network error while waking BLOOMIN device (continuing anyway): %s", e)
        except Exception as e:
            _LOGGER.warning("Unexpected error waking BLOOMIN device (continuing anyway): %s", e)

    async def process_and_upload_image(self, image_path: Path | None = None) -> bool:
        """Process image with presence overlay and upload to BLOOMIN device."""
        _LOGGER.info("Starting image processing and upload (entry_id: %s)", self.entry.entry_id)
        
        try:
            # Wake up BLOOMIN device first (BLE-based device needs to be woken up)
            _LOGGER.debug("Waking up BLOOMIN device...")
            await self.wake_device()
            
            # Get current person state
            _LOGGER.debug("Getting person entity state: %s", self.person_entity)
            person_state = self.hass.states.get(self.person_entity)
            
            if person_state is None:
                _LOGGER.error("Person entity %s not found", self.person_entity)
                return False
            
            current_state = person_state.state
            is_home = current_state == PERSON_STATE_HOME
            _LOGGER.info("Person state: %s (is_home: %s)", current_state, is_home)
            
            # Get image path if not provided
            if image_path is None:
                _LOGGER.debug("Image path not provided, getting from configured source")
                image_path = self.get_image_path()
            else:
                _LOGGER.debug("Using provided image path: %s", image_path)
            
            if image_path is None:
                _LOGGER.error("Failed to get image path")
                return False
            
            if not image_path.exists():
                _LOGGER.error("Image file does not exist: %s", image_path)
                return False
            
            _LOGGER.info("Processing image: %s", image_path)
            
            # Process image with presence overlay
            # Check both options and data for overlay settings (options takes precedence)
            overlay_position = self.entry.options.get(
                "overlay_position",
                self.entry.data.get("overlay_position", "bottom_right")
            )
            overlay_style = self.entry.options.get(
                "overlay_style",
                self.entry.data.get("overlay_style", "badge")
            )
            image_quality = self.entry.options.get(
                CONF_IMAGE_QUALITY,
                self.entry.data.get(CONF_IMAGE_QUALITY, DEFAULT_IMAGE_QUALITY)
            )
            badge_size = self.entry.options.get(
                CONF_OVERLAY_BADGE_SIZE,
                self.entry.data.get(CONF_OVERLAY_BADGE_SIZE, DEFAULT_OVERLAY_BADGE_SIZE)
            )
            icon_size = self.entry.options.get(
                CONF_OVERLAY_ICON_SIZE,
                self.entry.data.get(CONF_OVERLAY_ICON_SIZE, DEFAULT_OVERLAY_ICON_SIZE)
            )
            font_size = self.entry.options.get(
                CONF_OVERLAY_FONT_SIZE,
                self.entry.data.get(CONF_OVERLAY_FONT_SIZE, DEFAULT_OVERLAY_FONT_SIZE)
            )
            margin = self.entry.options.get(
                CONF_OVERLAY_MARGIN,
                self.entry.data.get(CONF_OVERLAY_MARGIN, DEFAULT_OVERLAY_MARGIN)
            )
            
            # Get text translations
            try:
                from homeassistant.helpers import translation
                translations = await translation.async_get_translations(
                    self.hass,
                    self.hass.config.language,
                    "config",
                    [DOMAIN]
                )
                home_text = translations.get(f"component.{DOMAIN}.overlay.home", "집에 있음")
                away_text = translations.get(f"component.{DOMAIN}.overlay.away", "외출 중")
            except Exception:
                # Fallback to default Korean text
                home_text = "집에 있음"
                away_text = "외출 중"
            
            overlay_config = {
                "position": overlay_position,
                "style": overlay_style,
                "badge_size": badge_size,
                "icon_size": icon_size,
                "font_size": font_size,
                "margin": margin,
                "home_text": home_text,
                "away_text": away_text,
            }
            _LOGGER.debug(
                "Overlay config: position=%s, style=%s, quality=%d, badge=%d, icon=%d, font=%d, margin=%d",
                overlay_position, overlay_style, image_quality, badge_size, icon_size, font_size, margin
            )
            
            _LOGGER.debug("Processing image with overlay (this may take a moment)...")
            processed_image = await self.hass.async_add_executor_job(
                self.image_processor.add_presence_overlay,
                str(image_path),
                is_home,
                overlay_config,
                image_quality
            )
            _LOGGER.debug("Image processed successfully, size: %d bytes", len(processed_image))
            
            # Upload to BLOOMIN device
            # Find the BLOOMIN media_player entity
            _LOGGER.debug("Looking for BLOOMIN media_player entity (IP: %s)", self.bloomin_ip)
            bloomin_entity = self._find_bloomin_entity()
            
            if bloomin_entity:
                _LOGGER.info("Found BLOOMIN entity: %s, using media_player service", bloomin_entity)
                # Save processed image to media directory for media_player service
                output_dir = Path(self.hass.config.media_dirs.get("local", self.hass.config.path("media"))) / "bloomin_presence"
                output_dir.mkdir(parents=True, exist_ok=True)
                
                image_filename = f"presence_{self.entry.entry_id}.jpg"
                output_path = output_dir / image_filename
                
                with open(output_path, "wb") as f:
                    f.write(processed_image)
                
                # Use Home Assistant's media_player.play_media service
                # This is the recommended way as it uses the BLOOMIN8 integration's built-in functionality
                media_content_id = f"/media/local/bloomin_presence/{image_filename}"
                try:
                    await self.hass.services.async_call(
                        "media_player",
                        "play_media",
                        {
                            "entity_id": bloomin_entity,
                            "media_content_id": media_content_id,
                            "media_content_type": "image/jpeg",
                        },
                    )
                    _LOGGER.info(
                        "Uploaded image to BLOOMIN display via media_player service (presence: %s)",
                        "Home" if is_home else "Away"
                    )
                    return True
                except (ValueError, AttributeError, KeyError) as e:
                    _LOGGER.debug(
                        "Could not use media_player service (invalid parameters): %s. Trying direct API.",
                        e
                    )
                except Exception as e:
                    _LOGGER.warning(
                        "Failed to upload via media_player service: %s. Trying direct API.",
                        e
                    )
                    # Fall through to direct API upload
            else:
                _LOGGER.info("BLOOMIN media_player entity not found, using direct HTTP API")
            
            # Fallback: try direct API upload
            _LOGGER.debug("Uploading image via direct HTTP API to: %s", self.bloomin_ip)
            success = await self.bloomin_api.upload_image(processed_image)
            if success:
                _LOGGER.info(
                    "Successfully uploaded image to BLOOMIN display via direct API (presence: %s)",
                    "Home" if is_home else "Away"
                )
            else:
                _LOGGER.error("Failed to upload image to BLOOMIN display via direct API")
            return success
                
        except (IOError, OSError) as err:
            _LOGGER.error("File I/O error processing and uploading image: %s", err, exc_info=True)
            return False
        except Exception as err:
            _LOGGER.error("Unexpected error processing and uploading image: %s", err, exc_info=True)
            return False

