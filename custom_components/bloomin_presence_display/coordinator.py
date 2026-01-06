"""Data coordinator for BLOOMIN Presence Display."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

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
    CONF_PERSON_ENTITIES,
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
        # Support both single person entity (legacy) and multiple person entities
        self.person_entities = entry.data.get(CONF_PERSON_ENTITIES, [])
        if not self.person_entities:
            # Fallback to single person entity for backward compatibility
            person_entity = entry.data.get(CONF_PERSON_ENTITY)
            if person_entity:
                self.person_entities = [person_entity]
        self.image_source = entry.data.get(CONF_IMAGE_SOURCE, IMAGE_SOURCE_FOLDER)
        self.media_folder = entry.data.get(CONF_MEDIA_FOLDER, "bloomin_display")
        self.image_path = entry.data.get(CONF_IMAGE_PATH, "")
        self.use_ble_wake = entry.data.get(CONF_USE_BLE_WAKE, False)
        self.ble_mac_address = entry.data.get(CONF_BLE_MAC_ADDRESS, "")
        self.ble_service_uuid = entry.data.get(CONF_BLE_SERVICE_UUID)
        self.ble_characteristic_uuid = entry.data.get(CONF_BLE_CHARACTERISTIC_UUID)
        
        # Initialize API client (only used for wake functionality)
        wake_endpoint = entry.data.get("api_wake_endpoint")
        self.bloomin_api = BloominAPI(self.bloomin_ip, wake_endpoint=wake_endpoint)
        self.image_processor = ImageProcessor(self.hass)

    def get_media_folder_path(self) -> Path:
        """Get the full path to the media folder. Creates folder if it doesn't exist."""
        media_dir = Path(self.hass.config.media_dirs.get("local", self.hass.config.path("media")))
        folder_path = media_dir / self.media_folder
        
        # Create folder if it doesn't exist
        if not folder_path.exists():
            try:
                folder_path.mkdir(parents=True, exist_ok=True)
                _LOGGER.info("Created media folder: %s", folder_path)
            except (OSError, PermissionError) as e:
                _LOGGER.error("Failed to create media folder %s: %s", folder_path, e)
                raise
        
        return folder_path

    async def get_image_path(self) -> Path | None:
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
            
            # Check existence in thread pool to avoid blocking
            exists = await asyncio.to_thread(image_path.exists)
            if not exists:
                _LOGGER.error("Image file does not exist: %s", image_path)
                return None
            
            is_file = await asyncio.to_thread(image_path.is_file)
            if not is_file:
                _LOGGER.error("Image path is not a file: %s", image_path)
                return None
            
            _LOGGER.info("Found image file: %s", image_path)
            return image_path
        else:
            # Use random image from folder
            _LOGGER.debug("Using folder source mode, folder: %s", self.media_folder)
            return await self.get_latest_image()
    
    async def get_latest_image(self) -> Path | None:
        """Get a random image from the media folder."""
        import random
        
        folder_path = self.get_media_folder_path()
        _LOGGER.debug("Looking for images in folder: %s", folder_path)
        
        # Check existence in thread pool to avoid blocking
        exists = await asyncio.to_thread(folder_path.exists)
        if not exists:
            _LOGGER.warning("Media folder does not exist: %s", folder_path)
            return None
        
        is_dir = await asyncio.to_thread(folder_path.is_dir)
        if not is_dir:
            _LOGGER.error("Media folder path is not a directory: %s", folder_path)
            return None
        
        # Find all image files in thread pool to avoid blocking
        image_extensions = {".jpg", ".jpeg", ".png", ".bmp"}
        try:
            def _list_images():
                return [
                    f for f in folder_path.iterdir()
                    if f.is_file() and f.suffix.lower() in image_extensions
                ]
            
            image_files = await asyncio.to_thread(_list_images)
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
        """Find the BLOOMIN media_player entity matching our IP.
        
        Strategy:
        1. First, try to find config_entry with matching IP from bloomin8_eink_canvas domain
        2. Then find media_player entities linked to that config_entry
        3. Fallback to searching all media_player entities by platform/IP
        """
        entity_registry = er.async_get(self.hass)
        _LOGGER.debug("Searching for BLOOMIN entity with IP: %s", self.bloomin_ip)
        
        # Method 1: Find config_entry by domain and IP, then find its entities
        try:
            for entry_id, config_entry in self.hass.config_entries.async_entries("bloomin8_eink_canvas"):
                entry_ip = config_entry.data.get("host") or config_entry.data.get("ip_address")
                _LOGGER.debug("Found bloomin8_eink_canvas config_entry: %s (IP: %s)", entry_id, entry_ip)
                
                if entry_ip == self.bloomin_ip:
                    # Find media_player entities linked to this config_entry
                    matching_entities = [
                        entity_id
                        for entity_id, entity in entity_registry.entities.items()
                        if (entity_id.startswith("media_player.") and
                            hasattr(entity, "config_entry_id") and
                            entity.config_entry_id == entry_id)
                    ]
                    
                    if matching_entities:
                        _LOGGER.info(
                            "Found %d matching BLOOMIN entity(ies) via config_entry: %s",
                            len(matching_entities), matching_entities
                        )
                        return matching_entities[0]
        except Exception as e:
            _LOGGER.debug("Error finding via config_entry: %s", e)
        
        # Method 2: Fallback - search all media_player entities
        matching_entities = []
        all_bloomin_entities = []
        
        for entity_id, entity in entity_registry.entities.items():
            # Check if it's a media_player entity
            if not entity_id.startswith("media_player."):
                continue
                
            # Check if it's from bloomin8_eink_canvas platform
            if entity.platform == "bloomin8_eink_canvas" or "bloomin" in entity_id.lower() or "eink" in entity_id.lower():
                all_bloomin_entities.append(entity_id)
                
                # Check if this entity matches our IP
                if hasattr(entity, "config_entry_id") and entity.config_entry_id:
                    config_entry = self.hass.config_entries.async_get_entry(entity.config_entry_id)
                    if config_entry:
                        entity_ip = config_entry.data.get("host") or config_entry.data.get("ip_address")
                        _LOGGER.debug("Found potential entity: %s (IP: %s, platform: %s)", entity_id, entity_ip, entity.platform)
                        if entity_ip == self.bloomin_ip:
                            matching_entities.append(entity_id)
                            _LOGGER.debug("Entity IP matches: %s", entity_id)
        
        if matching_entities:
            _LOGGER.info("Found %d matching BLOOMIN entity(ies): %s", len(matching_entities), matching_entities)
            return matching_entities[0]  # Return first match
        
        # If no exact IP match, log all found entities for debugging
        if all_bloomin_entities:
            _LOGGER.warning(
                "No BLOOMIN entity found matching IP: %s. Found %d BLOOMIN entities: %s. "
                "Will try to use the first one.",
                self.bloomin_ip, len(all_bloomin_entities), all_bloomin_entities
            )
            # Fallback: use first found entity if IP doesn't match (might be useful for single device setups)
            return all_bloomin_entities[0]
        
        _LOGGER.error("No BLOOMIN entity found at all. Make sure bloomin8_eink_canvas integration is configured.")
        return None

    async def wake_device(self) -> None:
        """Wake up BLOOMIN device using BLE first, then WiFi-based methods as fallback.
        
        Priority order (matching bloomin8_bt_wake repository):
        1. BLE wake (MUST be tried first if enabled)
        2. eink_display.whistle service (WiFi-based fallback)
        3. HTTP API wake endpoint (WiFi-based fallback)
        """
        # Priority 1: BLE wake MUST be tried first if enabled
        # This matches the bloomin8_bt_wake repository implementation
        if self.use_ble_wake and self.ble_mac_address:
            _LOGGER.info(
                "Attempting to wake device via BLE (priority 1): %s (service: %s, char: %s)",
                self.ble_mac_address,
                self.ble_service_uuid or "default",
                self.ble_characteristic_uuid or "default"
            )
            try:
                success = await wake_device_via_ble(
                    self.ble_mac_address,
                    self.ble_service_uuid,
                    self.ble_characteristic_uuid
                )
                if success:
                    _LOGGER.info("Successfully woke up BLOOMIN device via BLE")
                    return
                else:
                    _LOGGER.warning("BLE wake failed, trying WiFi-based fallback methods")
            except Exception as e:
                _LOGGER.warning("BLE wake error: %s. Trying WiFi-based fallback methods.", e)
        else:
            _LOGGER.debug("BLE wake not enabled or MAC address not configured, skipping BLE wake")
        
        # Priority 2: Try eink_display.whistle service (WiFi-based fallback)
        bloomin_entity = self._find_bloomin_entity()
        
        if bloomin_entity:
            # Check if the service exists
            if "eink_display" in self.hass.services.async_services():
                if "whistle" in self.hass.services.async_services().get("eink_display", {}):
                    try:
                        _LOGGER.debug("Attempting to wake device via eink_display.whistle service (fallback)")
                        await self.hass.services.async_call(
                            "eink_display",
                            "whistle",
                            {"entity_id": bloomin_entity},
                        )
                        _LOGGER.info("Successfully woke up BLOOMIN device using eink_display.whistle service")
                        return
                    except (ValueError, AttributeError, KeyError) as e:
                        _LOGGER.debug("Could not use eink_display.whistle service: %s", e)
                    except Exception as e:
                        _LOGGER.debug("Unexpected error using eink_display.whistle service: %s", e)
                else:
                    _LOGGER.debug("eink_display.whistle service not available")
            else:
                _LOGGER.debug("eink_display domain not available")
        
        # Priority 3: Try HTTP API wake endpoint (WiFi-based fallback)
        try:
            _LOGGER.debug("Attempting to wake device via HTTP API (fallback)")
            success = await self.bloomin_api.wake_device()
            if success:
                _LOGGER.info("Successfully woke up BLOOMIN device via HTTP API")
            else:
                _LOGGER.warning("All wake methods failed. Device may need to be woken manually.")
        except (asyncio.TimeoutError, Exception) as e:
            _LOGGER.warning("HTTP API wake error: %s", e)

    async def process_and_upload_image(self, image_path: Path | None = None) -> bool:
        """Process image with presence overlay and upload to BLOOMIN device."""
        _LOGGER.info("Starting image processing and upload (entry_id: %s)", self.entry.entry_id)
        
        try:
            # Wake up BLOOMIN device first (BLE-based device needs to be woken up)
            _LOGGER.debug("Waking up BLOOMIN device...")
            await self.wake_device()
            
            # Get current person states (support multiple persons)
            _LOGGER.debug("Getting person entity states: %s", self.person_entities)
            
            if not self.person_entities:
                _LOGGER.error("No person entities configured")
                return False
            
            # Check if any person is home
            is_home = False
            person_states = []
            
            for person_entity_id in self.person_entities:
                person_state = self.hass.states.get(person_entity_id)
                if person_state is None:
                    _LOGGER.warning("Person entity %s not found", person_entity_id)
                    continue
                
                current_state = person_state.state
                person_is_home = current_state == PERSON_STATE_HOME
                person_states.append((person_entity_id, current_state, person_is_home))
                
                if person_is_home:
                    is_home = True
            
            if not person_states:
                _LOGGER.error("No valid person entities found")
                return False
            
            _LOGGER.info(
                "Person states: %s (any_home: %s)",
                ", ".join([f"{pid}={state}" for pid, state, _ in person_states]),
                is_home
            )
            
            # Get image path if not provided
            if image_path is None:
                _LOGGER.debug("Image path not provided, getting from configured source")
                image_path = await self.get_image_path()
            else:
                _LOGGER.debug("Using provided image path: %s", image_path)
            
            if image_path is None:
                _LOGGER.error("Failed to get image path")
                return False
            
            # Check existence in thread pool to avoid blocking
            exists = await asyncio.to_thread(image_path.exists)
            if not exists:
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
            
            # Upload to BLOOMIN device using media_player.play_media service
            # This uses the official bloomin8_eink_canvas integration's built-in functionality
            # Reference: https://github.com/ARPOBOT-BLOOMIN8/eink_canvas_home_assistant_component
            _LOGGER.debug("Uploading image using media_player.play_media service (IP: %s)", self.bloomin_ip)
            
            # Find the BLOOMIN media_player entity
            bloomin_entity = self._find_bloomin_entity()
            if not bloomin_entity:
                _LOGGER.error("BLOOMIN media_player entity not found. Make sure bloomin8_eink_canvas integration is configured.")
                _LOGGER.debug("Available media_player entities: %s", [
                    entity_id for entity_id in er.async_get(self.hass).entities.keys()
                    if "bloomin" in entity_id.lower() or "eink" in entity_id.lower()
                ])
                return False
            
            # Save processed image to media directory
            import time
            # Get the actual media directory path
            media_dirs = self.hass.config.media_dirs
            local_media_dir = media_dirs.get("local")
            if not local_media_dir:
                # Fallback to default media directory
                local_media_dir = self.hass.config.path("media")
            
            output_dir = Path(local_media_dir) / "bloomin_presence"
            # Create directory in thread pool to avoid blocking
            await asyncio.to_thread(output_dir.mkdir, parents=True, exist_ok=True)
            
            timestamp = int(time.time() * 1000)
            image_filename = f"presence_{self.entry.entry_id}_{timestamp}.jpg"
            output_path = output_dir / image_filename
            
            try:
                # Write file in thread pool to avoid blocking
                def _write_file():
                    with open(output_path, "wb") as f:
                        f.write(processed_image)
                
                await asyncio.to_thread(_write_file)
                _LOGGER.debug("Saved processed image to: %s", output_path)
                
                # Verify file was written
                file_exists = await asyncio.to_thread(output_path.exists)
                if not file_exists:
                    _LOGGER.error("File was not created: %s", output_path)
                    return False
                
                # Get relative path from media directory for media_content_id
                # The path should be relative to the media directory root
                try:
                    relative_path = output_path.relative_to(Path(local_media_dir))
                    _LOGGER.debug("Relative path from media dir: %s", relative_path)
                except ValueError:
                    # If relative path calculation fails, use filename only
                    relative_path = Path("bloomin_presence") / image_filename
                    _LOGGER.debug("Using fallback relative path: %s", relative_path)
                
                # Try multiple media_content_id formats that bloomin8_eink_canvas might accept
                # Format 1: /media/local/path (standard Home Assistant format)
                media_content_id_variants = [
                    f"/media/local/{relative_path.as_posix()}",
                    f"media://local/{relative_path.as_posix()}",
                    f"/local/{relative_path.as_posix()}",
                    f"/media/local/bloomin_presence/{image_filename}",
                    f"media://local/bloomin_presence/{image_filename}",
                ]
                
                # Also try the media browser format: directory,device_galleries/directory,gallery:default/filename
                # But first try standard formats
                for media_content_id in media_content_id_variants:
                    try:
                        _LOGGER.info(
                            "Calling media_player.play_media service for entity: %s with media_content_id: %s",
                            bloomin_entity, media_content_id
                        )
                        
                        result = await self.hass.services.async_call(
                            "media_player",
                            "play_media",
                            {
                                "entity_id": bloomin_entity,
                                "media_content_id": media_content_id,
                                "media_content_type": "image/jpeg",
                            },
                            blocking=True,  # Wait for result
                        )
                        
                        _LOGGER.info(
                            "Successfully uploaded and displayed image on BLOOMIN display via media_player service (presence: %s, path: %s)",
                            "Home" if is_home else "Away",
                            media_content_id
                        )
                        return True
                    except (ValueError, AttributeError, KeyError) as e:
                        _LOGGER.debug("Failed with media_content_id '%s': %s, trying next format", media_content_id, e)
                        continue
                    except Exception as e:
                        _LOGGER.debug("Error with media_content_id '%s': %s, trying next format", media_content_id, e)
                        continue
                
                # If all standard formats failed, log error
                _LOGGER.error(
                    "Failed to use media_player.play_media service with all path formats. "
                    "Entity: %s, Tried paths: %s",
                    bloomin_entity, media_content_id_variants
                )
                return False
                
            except (IOError, OSError) as e:
                _LOGGER.error("Failed to save processed image: %s", e, exc_info=True)
                return False
            except Exception as e:
                _LOGGER.error("Unexpected error: %s", e, exc_info=True)
                return False
                
        except (IOError, OSError) as err:
            _LOGGER.error("File I/O error processing and uploading image: %s", err, exc_info=True)
            return False
        except Exception as err:
            _LOGGER.error("Unexpected error processing and uploading image: %s", err, exc_info=True)
            return False

