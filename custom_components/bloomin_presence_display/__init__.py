"""BLOOMIN Presence Display integration for Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import BloominPresenceCoordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = []


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BLOOMIN Presence Display from a config entry."""
    coordinator = BloominPresenceCoordinator(hass, entry)
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Set up services
    if DOMAIN not in hass.data.get("_services_setup", set()):
        await async_setup_services(hass)
        hass.data.setdefault("_services_setup", set()).add(DOMAIN)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # Unload services if no more entries
        if not hass.data[DOMAIN]:
            await async_unload_services(hass)
            hass.data.get("_services_setup", set()).discard(DOMAIN)
    
    return unload_ok

