"""Generate 256×1 RGBA PNGs for every shipped LUT.

Run from repo root: `uv run --with matplotlib --with pillow python scripts/gen_luts.py`
(or install matplotlib+pillow in the dev env and `uv run python scripts/gen_luts.py`).
"""
from pathlib import Path

import numpy as np
from matplotlib import cm
from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "anybioimage/frontend/viewer/src/render/luts/lut-textures"
OUT.mkdir(parents=True, exist_ok=True)

named = [
    "gray", "viridis", "plasma", "magma", "inferno", "cividis", "turbo",
    "hot", "cool",
]

def ramp(rgb):
    xs = np.linspace(0, 1, 256)
    arr = np.zeros((256, 4), dtype=np.uint8)
    arr[:, 0] = xs * rgb[0] * 255
    arr[:, 1] = xs * rgb[1] * 255
    arr[:, 2] = xs * rgb[2] * 255
    arr[:, 3] = 255
    return arr

plain = {
    "red": (1, 0, 0), "green": (0, 1, 0), "blue": (0, 0, 1),
    "cyan": (0, 1, 1), "magenta": (1, 0, 1), "yellow": (1, 1, 0),
}

for name in named:
    cmap = cm.get_cmap(name, 256)
    rgba = (cmap(np.linspace(0, 1, 256)) * 255).astype(np.uint8)
    Image.fromarray(rgba[None, :, :], mode="RGBA").save(OUT / f"{name}.png")

for name, rgb in plain.items():
    arr = ramp(rgb)
    Image.fromarray(arr[None, :, :], mode="RGBA").save(OUT / f"{name}.png")

print(f"wrote {len(named) + len(plain)} LUT PNGs to {OUT}")
