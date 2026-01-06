"""Services for BLOOMIN Presence Display."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_UPDATE_DISPLAY = "update_display"
SERVICE_UPLOAD_IMAGE = "upload_image"

SERVICE_SCHEMA_UPDATE_DISPLAY = vol.Schema(
    {
        vol.Optional("entity_id"): cv.string,
    }
)

SERVICE_SCHEMA_UPLOAD_IMAGE = vol.Schema(
    {
        vol.Optional("entity_id"): cv.string,
        vol.Optional("image_path"): cv.string,
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for BLOOMIN Presence Display."""

    async def update_display_service(call: ServiceCall) -> None:
        """Handle update_display service call - processes latest image from media folder."""
        # Get all coordinators and process for each
        coordinators = list(hass.data[DOMAIN].values())
        
        if not coordinators:
            _LOGGER.warning("No BLOOMIN Presence Display integrations found")
            return
        
        # If entity_id is provided, find specific coordinator
        entity_id = call.data.get("entity_id")
        if entity_id:
            coordinator = None
            # First, try to find by entry_id (most reliable)
            if entity_id in hass.data[DOMAIN]:
                coordinator = hass.data[DOMAIN][entity_id]
                _LOGGER.debug("Found coordinator by entry_id: %s", entity_id)
            else:
                # Try to find by entry title
                for entry_id, coord in hass.data[DOMAIN].items():
                    config_entry = hass.config_entries.async_get_entry(entry_id)
                    if config_entry and config_entry.title == entity_id:
                        coordinator = coord
                        _LOGGER.debug("Found coordinator by title: %s (entry_id: %s)", entity_id, entry_id)
                        break
                
                if not coordinator:
                    _LOGGER.warning("No coordinator found for entity_id: %s", entity_id)
            
            coordinators = [coordinator] if coordinator else []
        
        # Process each coordinator
        for coord in coordinators:
            if coord:
                success = await coord.process_and_upload_image()
                if success:
                    _LOGGER.info("Updated display")
                else:
                    _LOGGER.error("Failed to update display")

    async def upload_image_service(call: ServiceCall) -> None:
        """Handle upload_image service call with optional image path."""
        image_path_str = call.data.get("image_path")
        entity_id = call.data.get("entity_id")
        
        # Get coordinators
        coordinators = list(hass.data[DOMAIN].values())
        
        if not coordinators:
            _LOGGER.warning("No BLOOMIN Presence Display integrations found")
            return
        
        # If entity_id is provided, find specific coordinator
        if entity_id:
            coordinator = None
            # First, try to find by entry_id (most reliable)
            if entity_id in hass.data[DOMAIN]:
                coordinator = hass.data[DOMAIN][entity_id]
                _LOGGER.debug("Found coordinator by entry_id: %s", entity_id)
            else:
                # Try to find by entry title
                for entry_id, coord in hass.data[DOMAIN].items():
                    config_entry = hass.config_entries.async_get_entry(entry_id)
                    if config_entry and config_entry.title == entity_id:
                        coordinator = coord
                        _LOGGER.debug("Found coordinator by title: %s (entry_id: %s)", entity_id, entry_id)
                        break
                
                if not coordinator:
                    _LOGGER.warning("No coordinator found for entity_id: %s", entity_id)
            
            coordinators = [coordinator] if coordinator else []
        
        image_path = None
        if image_path_str:
            image_path = Path(image_path_str)
            if not image_path.exists():
                _LOGGER.error("Image path does not exist: %s", image_path)
                return
        
        # Process each coordinator
        for coord in coordinators:
            if coord:
                success = await coord.process_and_upload_image(image_path)
                if success:
                    _LOGGER.info("Uploaded image")
                else:
                    _LOGGER.error("Failed to upload image")

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_DISPLAY,
        update_display_service,
        schema=SERVICE_SCHEMA_UPDATE_DISPLAY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPLOAD_IMAGE,
        upload_image_service,
        schema=SERVICE_SCHEMA_UPLOAD_IMAGE,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services for BLOOMIN Presence Display."""
    hass.services.async_remove(DOMAIN, SERVICE_UPDATE_DISPLAY)
    hass.services.async_remove(DOMAIN, SERVICE_UPLOAD_IMAGE)

