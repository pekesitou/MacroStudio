"""Generate the application icon (no third-party assets involved)."""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Rounded dark background
draw.rounded_rectangle((8, 8, SIZE - 8, SIZE - 8), radius=52, fill="#121826")

# Accent ring (the "record target" used as the app logo)
draw.ellipse((52, 52, SIZE - 52, SIZE - 52), fill="#6c8cff")
draw.ellipse((74, 74, SIZE - 74, SIZE - 74), fill="#121826")
draw.ellipse((84, 84, SIZE - 84, SIZE - 84), outline="#8fa9ff", width=5)

# Red recording dot
draw.ellipse((104, 104, SIZE - 104, SIZE - 104), fill="#ff4d4d")

# Small highlight for depth
draw.ellipse((112, 112, 132, 132), fill="#ff8a8a")

out = Path(__file__).with_name("macro_studio.ico")
img.save(out, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("ICONO:", out)
