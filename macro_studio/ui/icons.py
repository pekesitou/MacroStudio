"""Programmatically drawn, crisp icons (no external assets needed)."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Tuple

from PIL import Image, ImageDraw
import customtkinter as ctk

CANVAS = 64
DARK_COLOR = (223, 229, 240, 255)
LIGHT_COLOR = (43, 50, 68, 255)


def _shape(kind: str, draw: ImageDraw.ImageDraw, color) -> None:
    c = CANVAS
    m = 10  # margin
    if kind == "record":
        draw.ellipse((m + 2, m + 2, c - m - 2, c - m - 2), fill=color)
    elif kind == "play":
        draw.polygon([(m + 6, m), (c - m - 4, c / 2), (m + 6, c - m)], fill=color)
    elif kind == "pause":
        draw.rounded_rectangle((m + 4, m, m + 20, c - m), radius=4, fill=color)
        draw.rounded_rectangle((c - m - 20, m, c - m - 4, c - m), radius=4, fill=color)
    elif kind == "stop":
        draw.rounded_rectangle((m + 3, m + 3, c - m - 3, c - m - 3), radius=6, fill=color)
    elif kind == "step":
        draw.polygon([(m, m), (c - m - 14, c / 2), (m, c - m)], fill=color)
        draw.rounded_rectangle((c - m - 8, m, c - m, c - m), radius=3, fill=color)
    elif kind == "plus":
        draw.rounded_rectangle((c / 2 - 4, m + 4, c / 2 + 4, c - m - 4), radius=3, fill=color)
        draw.rounded_rectangle((m + 4, c / 2 - 4, c - m - 4, c / 2 + 4), radius=3, fill=color)
    elif kind == "minus":
        draw.rounded_rectangle((m + 4, c / 2 - 4, c - m - 4, c / 2 + 4), radius=3, fill=color)
    elif kind == "trash":
        draw.rounded_rectangle((m + 6, m + 16, c - m - 6, c - m), radius=5, outline=color, width=4)
        draw.rounded_rectangle((m + 2, m + 10, c - m - 2, m + 18), radius=3, fill=color)
        draw.rounded_rectangle((c / 2 - 3, m + 2, c / 2 + 3, m + 11), radius=2, fill=color)
        for x in (c / 2 - 9, c / 2, c / 2 + 9):
            draw.line((x, m + 26, x, c - m - 6), fill=color, width=3)
    elif kind == "copy":
        draw.rounded_rectangle((m + 10, m + 10, c - m, c - m), radius=5, outline=color, width=4)
        draw.rounded_rectangle((m, m, c - m - 10, c - m - 10), radius=5, fill=(0, 0, 0, 0), outline=color, width=4)
    elif kind == "save":
        draw.rounded_rectangle((m + 2, m + 2, c - m - 2, c - m - 2), radius=5, outline=color, width=4)
        draw.rectangle((m + 12, m + 2, c - m - 12, m + 20), outline=color, width=4)
        draw.rounded_rectangle((m + 12, c - m - 18, c - m - 12, c - m - 2), radius=3, fill=color)
    elif kind == "folder":
        draw.polygon(
            [(m, m + 8), (m + 22, m + 8), (m + 28, m + 16), (c - m, m + 16),
             (c - m, c - m), (m, c - m)],
            fill=color,
        )
    elif kind == "import":
        draw.rounded_rectangle((m + 4, c - m - 12, c - m - 4, c - m), radius=4, outline=color, width=4)
        draw.line((c / 2, m + 4, c / 2, c - m - 18), fill=color, width=5)
        draw.polygon([(c / 2 - 10, m + 16), (c / 2 + 10, m + 16), (c / 2, m + 26)], fill=color)
    elif kind == "export":
        draw.rounded_rectangle((m + 4, c - m - 12, c - m - 4, c - m), radius=4, outline=color, width=4)
        draw.line((c / 2, c - m - 18, c / 2, m + 4), fill=color, width=5)
        draw.polygon([(c / 2 - 10, m + 24), (c / 2 + 10, m + 24), (c / 2, m + 14)], fill=color)
    elif kind == "settings":
        draw.ellipse((m + 8, m + 8, c - m - 8, c - m - 8), outline=color, width=5)
        for angle in range(0, 360, 45):
            import math
            rad = math.radians(angle)
            x1 = c / 2 + math.cos(rad) * 20
            y1 = c / 2 + math.sin(rad) * 20
            x2 = c / 2 + math.cos(rad) * 28
            y2 = c / 2 + math.sin(rad) * 28
            draw.line((x1, y1, x2, y2), fill=color, width=5)
    elif kind == "sun":
        draw.ellipse((m + 12, m + 12, c - m - 12, c - m - 12), outline=color, width=5)
        import math
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            draw.line(
                (c / 2 + math.cos(rad) * 18, c / 2 + math.sin(rad) * 18,
                 c / 2 + math.cos(rad) * 26, c / 2 + math.sin(rad) * 26),
                fill=color, width=4,
            )
    elif kind == "moon":
        draw.ellipse((m + 4, m + 4, c - m - 4, c - m - 4), fill=color)
        draw.ellipse((m + 18, m + 2, c - m + 6, c - m + 2), fill=(0, 0, 0, 0))
    elif kind == "search":
        draw.ellipse((m + 2, m + 2, c - m - 12, c - m - 12), outline=color, width=5)
        draw.line((c - m - 14, c - m - 14, c - m, c - m), fill=color, width=6)
    elif kind == "loop":
        draw.arc((m + 4, m + 4, c - m - 4, c - m - 4), start=40, end=320, fill=color, width=5)
        draw.polygon([(c - m - 14, m + 2), (c - m, m + 12), (c - m - 18, m + 16)], fill=color)
    elif kind == "edit":
        draw.polygon(
            [(m + 4, c - m - 8), (m + 4, c - m - 18), (c - m - 16, m + 8),
             (c - m - 6, m + 18), (m + 14, c - m - 8)],
            fill=color,
        )
        draw.line((m + 4, c - m - 2, c - m - 2, c - m - 2), fill=color, width=4)
    elif kind == "close":
        draw.line((m + 4, m + 4, c - m - 4, c - m - 4), fill=color, width=6)
        draw.line((c - m - 4, m + 4, m + 4, c - m - 4), fill=color, width=6)
    elif kind == "chevron_down":
        draw.polygon([(m + 8, m + 18), (c - m - 8, m + 18), (c / 2, c - m - 12)], fill=color)
    elif kind == "info":
        draw.ellipse((m + 2, m + 2, c - m - 2, c - m - 2), outline=color, width=4)
        draw.ellipse((c / 2 - 3, m + 12, c / 2 + 3, m + 18), fill=color)
        draw.rounded_rectangle((c / 2 - 3, m + 24, c / 2 + 3, c - m - 6), radius=2, fill=color)
    else:
        draw.ellipse((m, m, c - m, c - m), outline=color, width=4)


@lru_cache(maxsize=128)
def _image(kind: str, dark: bool, size: int) -> Image.Image:
    color = DARK_COLOR if dark else LIGHT_COLOR
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    _shape(kind, draw, color)
    return img.resize((size, size), Image.LANCZOS)


def icon(kind: str, size: int = 18) -> ctk.CTkImage:
    """Return a CTkImage with variants for dark and light themes."""
    return ctk.CTkImage(
        light_image=_image(kind, False, size),
        dark_image=_image(kind, True, size),
        size=(size, size),
    )


AVAILABLE = (
    "record", "play", "pause", "stop", "step", "plus", "minus", "trash", "copy",
    "save", "folder", "import", "export", "settings", "sun", "moon", "search",
    "loop", "edit", "close", "chevron_down", "info",
)
