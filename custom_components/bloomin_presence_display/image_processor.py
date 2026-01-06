"""Image processing utilities for presence overlay."""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

from PIL import Image, ImageDraw, ImageFont

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ImageProcessor:
    """Handle image processing with presence overlay."""

    def __init__(self, hass: HomeAssistant | None = None) -> None:
        """Initialize the image processor."""
        self._font_cache = {}
        self.hass = hass

    def add_presence_overlay(
        self,
        image_path: str,
        is_home: bool,
        overlay_config: dict[str, Any],
        image_quality: int = 95,
    ) -> bytes:
        """Add presence overlay to image and return as bytes."""
        try:
            # Load image
            image = Image.open(image_path)
            image = image.convert("RGB")  # Ensure RGB mode
            
            # Create overlay
            overlay = self._create_overlay(
                image.size,
                is_home,
                overlay_config
            )
            
            # Composite overlay onto image
            if overlay.mode == "RGBA":
                # Convert image to RGBA for alpha compositing
                image_rgba = image.convert("RGBA")
                # Composite overlay onto image
                image = Image.alpha_composite(image_rgba, overlay).convert("RGB")
            else:
                # Paste overlay if it's not RGBA
                image.paste(overlay, (0, 0), overlay if overlay.mode == "RGBA" else None)
            
            # Convert to bytes
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=image_quality)
            output.seek(0)
            
            return output.getvalue()
            
        except (IOError, OSError) as e:
            _LOGGER.error("File I/O error processing image: %s", e)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error processing image: %s", e, exc_info=True)
            raise

    def _create_overlay(
        self,
        image_size: tuple[int, int],
        is_home: bool,
        config: dict[str, Any],
    ) -> Image.Image:
        """Create presence overlay image."""
        width, height = image_size
        position = config.get("position", "bottom_right")
        style = config.get("style", "badge")
        badge_size = config.get("badge_size", 40)
        icon_size = config.get("icon_size", 32)
        font_size = config.get("font_size", 16)
        margin = config.get("margin", 15)
        
        # Create transparent overlay
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Calculate position
        x, y = self._calculate_position(width, height, position, badge_size, margin)
        
        # Draw overlay based on style
        home_text = config.get("home_text", "집에 있음")
        away_text = config.get("away_text", "외출 중")
        
        if style == "badge":
            self._draw_badge(draw, x, y, is_home, badge_size)
        elif style == "text":
            self._draw_text(draw, x, y, is_home, width, height, font_size, margin, home_text, away_text)
        elif style == "icon":
            self._draw_icon(draw, x, y, is_home, icon_size)
        
        return overlay

    def _calculate_position(
        self, width: int, height: int, position: str, badge_size: int, margin: int
    ) -> tuple[int, int]:
        """Calculate overlay position."""
        if position == "bottom_right":
            return (width - badge_size - margin, height - badge_size - margin)
        elif position == "bottom_left":
            return (margin, height - badge_size - margin)
        elif position == "top_right":
            return (width - badge_size - margin, margin)
        elif position == "top_left":
            return (margin, margin)
        else:
            # Default to bottom_right
            return (width - badge_size - margin, height - badge_size - margin)

    def _draw_badge(
        self, draw: ImageDraw.Draw, x: int, y: int, is_home: bool, badge_size: int = 40
    ) -> None:
        """Draw a subtle badge-style overlay."""
        radius = 8
        
        # Subtle, semi-transparent background color
        # Green for home (more visible but still subtle)
        # Gray for away (very subtle)
        bg_color = (76, 175, 80, 180) if is_home else (120, 120, 120, 140)
        
        # Draw rounded rectangle with subtle shadow effect
        # Shadow
        draw.rounded_rectangle(
            [(x + 2, y + 2), (x + badge_size + 2, y + badge_size + 2)],
            radius=radius,
            fill=(0, 0, 0, 60),
        )
        # Main badge
        draw.rounded_rectangle(
            [(x, y), (x + badge_size, y + badge_size)],
            radius=radius,
            fill=bg_color,
        )
        
        # Draw subtle status indicator (smaller circle)
        indicator_size = 12
        indicator_x = x + badge_size // 2
        indicator_y = y + badge_size // 2
        
        # White dot for home, lighter gray for away
        indicator_color = (255, 255, 255, 220) if is_home else (200, 200, 200, 180)
        draw.ellipse(
            [
                (indicator_x - indicator_size // 2, indicator_y - indicator_size // 2),
                (indicator_x + indicator_size // 2, indicator_y + indicator_size // 2),
            ],
            fill=indicator_color,
        )

    def _draw_text(
        self, draw: ImageDraw.Draw, x: int, y: int, is_home: bool, width: int, height: int, font_size: int = 16, margin: int = 15, home_text: str = "집에 있음", away_text: str = "외출 중"
    ) -> None:
        """Draw subtle text overlay."""
        text = home_text if is_home else away_text
        try:
            # Try to use a system font
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except:
                font = ImageFont.load_default()
        
        # Get text bounding box
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Subtle background rectangle with rounded corners
        padding = 8
        bg_color = (0, 0, 0, 140)  # More transparent
        draw.rounded_rectangle(
            [
                (x - padding, y - padding),
                (x + text_width + padding, y + text_height + padding),
            ],
            radius=6,
            fill=bg_color,
        )
        
        # Text color - subtle but visible
        text_color = (144, 238, 144, 240) if is_home else (200, 200, 200, 220)  # Light green for home, light gray for away
        draw.text((x, y), text, fill=text_color, font=font)

    def _draw_icon(
        self, draw: ImageDraw.Draw, x: int, y: int, is_home: bool, icon_size: int = 32
    ) -> None:
        """Draw subtle icon overlay."""
        
        if is_home:
            # Draw subtle home icon (simple house shape)
            points = [
                (x + icon_size // 2, y + 2),
                (x + 4, y + icon_size // 3),
                (x + 4, y + icon_size - 4),
                (x + icon_size - 4, y + icon_size - 4),
                (x + icon_size - 4, y + icon_size // 3),
            ]
            # Subtle green with transparency
            draw.polygon(points, fill=(76, 175, 80, 200))
            # Add a subtle outline
            draw.polygon(points, outline=(255, 255, 255, 100), width=1)
        else:
            # Draw subtle away icon (circle with line)
            draw.ellipse(
                [(x + 2, y + 2), (x + icon_size - 2, y + icon_size - 2)],
                outline=(158, 158, 158, 180),
                width=2,
            )
            draw.line(
                [(x + 6, y + 6), (x + icon_size - 6, y + icon_size - 6)],
                fill=(158, 158, 158, 180),
                width=2,
            )

