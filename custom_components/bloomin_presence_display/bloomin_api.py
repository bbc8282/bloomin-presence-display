"""BLOOMIN API client for uploading images."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class BloominAPI:
    """Client for BLOOMIN device API."""

    def __init__(self, ip_address: str, upload_endpoint: str | None = None, wake_endpoint: str | None = None) -> None:
        """Initialize the BLOOMIN API client.
        
        Args:
            ip_address: IP address of the BLOOMIN device
            upload_endpoint: Custom upload endpoint path (e.g., "/api/upload")
            wake_endpoint: Custom wake endpoint path (e.g., "/api/wake")
        """
        self.ip_address = ip_address
        self.base_url = f"http://{ip_address}"
        self.upload_endpoint = upload_endpoint or "/api/upload"
        self.wake_endpoint = wake_endpoint or "/api/wake"

    async def upload_image(self, image_data: bytes) -> bool:
        """Upload image to BLOOMIN device.
        
        Note: This is a fallback method. The preferred method is using
        media_player.play_media service from bloomin8_eink_canvas integration.
        
        API endpoint may vary based on actual BLOOMIN device firmware.
        Common endpoints: /api/upload, /upload, /api/image
        """
        try:
            # BLOOMIN API endpoint for image upload
            # Based on the reference repository, this uses media_player.play_media service
            # We'll use HTTP POST to upload the image
            # Note: Endpoint may be discovered during setup or use default
            url = f"{self.base_url}{self.upload_endpoint}"
            _LOGGER.debug("Uploading image to: %s (size: %d bytes)", url, len(image_data))
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    data=image_data,
                    headers={"Content-Type": "image/jpeg"},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    response_text = await response.text()
                    _LOGGER.debug("Upload response: HTTP %s, body: %s", response.status, response_text[:100])
                    
                    if response.status == 200:
                        _LOGGER.info("Successfully uploaded image to BLOOMIN device via HTTP API")
                        return True
                    else:
                        _LOGGER.error(
                            "Failed to upload image: HTTP %s, response: %s", 
                            response.status, response_text[:200]
                        )
                        return False
                        
        except aiohttp.ClientError as e:
            _LOGGER.error("Network error uploading image to BLOOMIN device: %s", e)
            return False
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout uploading image to BLOOMIN device")
            return False
        except Exception as e:
            _LOGGER.error("Unexpected error uploading image: %s", e, exc_info=True)
            return False

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
                async with session.post(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
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

    async def get_device_info(self) -> dict[str, Any] | None:
        """Get device information."""
        try:
            url = f"{self.base_url}/api/info"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return await response.json()
                    return None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.error("Network error getting device info: %s", e)
            return None
        except Exception as e:
            _LOGGER.error("Unexpected error getting device info: %s", e)
            return None
    
    async def discover_api_endpoints(self) -> dict[str, str] | None:
        """Discover API endpoints by trying common paths.
        
        Returns:
            Dictionary with discovered endpoints (upload, wake, info) or None if discovery fails
        """
        _LOGGER.info("Discovering API endpoints for device: %s", self.ip_address)
        
        # Common API endpoint patterns
        endpoint_candidates = {
            "upload": ["/api/upload", "/upload", "/api/image", "/api/send"],
            "wake": ["/api/wake", "/wake", "/api/ping", "/ping"],
            "info": ["/api/info", "/info", "/api/status", "/status"],
        }
        
        discovered = {}
        
        for endpoint_type, paths in endpoint_candidates.items():
            for path in paths:
                url = f"{self.base_url}{path}"
                try:
                    _LOGGER.debug("Trying endpoint: %s", url)
                    async with aiohttp.ClientSession() as session:
                        if endpoint_type == "upload":
                            # For upload, try POST with empty data
                            async with session.post(
                                url,
                                data=b"",
                                timeout=aiohttp.ClientTimeout(total=3),
                            ) as response:
                                # Accept 200, 400 (bad request but endpoint exists), 405 (method not allowed)
                                if response.status in (200, 400, 405):
                                    discovered[endpoint_type] = path
                                    _LOGGER.info("Discovered %s endpoint: %s", endpoint_type, path)
                                    break
                        elif endpoint_type == "wake":
                            # For wake, try POST
                            async with session.post(
                                url,
                                timeout=aiohttp.ClientTimeout(total=3),
                            ) as response:
                                if response.status in (200, 400, 405):
                                    discovered[endpoint_type] = path
                                    _LOGGER.info("Discovered %s endpoint: %s", endpoint_type, path)
                                    break
                        else:  # info
                            # For info, try GET
                            async with session.get(
                                url,
                                timeout=aiohttp.ClientTimeout(total=3),
                            ) as response:
                                if response.status == 200:
                                    discovered[endpoint_type] = path
                                    _LOGGER.info("Discovered %s endpoint: %s", endpoint_type, path)
                                    break
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    # Endpoint doesn't exist or not reachable, try next
                    continue
                except Exception as e:
                    _LOGGER.debug("Error testing endpoint %s: %s", url, e)
                    continue
        
        if discovered:
            _LOGGER.info("API endpoint discovery successful: %s", discovered)
            return discovered
        else:
            _LOGGER.warning("API endpoint discovery failed, will use default endpoints")
            return None

