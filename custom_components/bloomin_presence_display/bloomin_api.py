"""BLOOMIN API client for wake functionality."""
from __future__ import annotations

import asyncio
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)


class BloominAPI:
    """Client for BLOOMIN device API."""

    def __init__(self, ip_address: str, wake_endpoint: str | None = None) -> None:
        """Initialize the BLOOMIN API client.
        
        Note: Image upload is handled by the official bloomin8_eink_canvas integration
        via media_player.play_media service. This API client is only used for wake functionality.
        
        Args:
            ip_address: IP address of the BLOOMIN device
            wake_endpoint: Custom wake endpoint path (e.g., "/api/wake")
        """
        self.ip_address = ip_address
        self.base_url = f"http://{ip_address}"
        self.wake_endpoint = wake_endpoint or "/api/wake"

    async def wake_device(self) -> bool:
        """Wake up the BLOOMIN device.
        
        Note: This is a fallback method. The preferred methods are:
        1. BLE wake (if enabled)
        2. eink_display.whistle service from bloomin8_eink_canvas integration
        
        API endpoint may vary based on actual BLOOMIN device firmware.
        Common endpoints: /api/wake, /wake, /api/ping
        """
        try:
            # Note: Endpoint may be discovered during setup or use default
            url = f"{self.base_url}{self.wake_endpoint}"
            _LOGGER.debug("Attempting to wake device via HTTP API: %s", url)
            
            async with aiohttp.ClientSession() as session:
                # Try without Content-Type header first (some devices don't accept JSON)
                async with session.post(
                    url,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    response_text = await response.text()
                    _LOGGER.debug("Wake response: HTTP %s, body: %s", response.status, response_text[:100])
                    
                    success = response.status == 200
                    if success:
                        _LOGGER.info("Successfully woke device via HTTP API")
                    else:
                        _LOGGER.warning("Wake request returned HTTP %s: %s", response.status, response_text[:100])
                    return success
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error("Network error waking device: %s", e)
            return False
        except Exception as e:
            _LOGGER.error("Unexpected error waking device: %s", e)
            return False


