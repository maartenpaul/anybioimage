"""Pixel sampling for integration tests.

Deck.gl renders with ``preserveDrawingBuffer=false`` (the WebGL default), which
means the WebGL framebuffer is cleared after each frame composition.
``gl.readPixels`` and ``canvas.toDataURL()`` therefore return all-zero data.

The correct approach is to use Playwright's screenshot API clipped to the
canvas bounding rect.  The browser composites the GL output into the
screenshot even after the GL drawing buffer is cleared.
"""
from __future__ import annotations

import io


_CANVAS_RECT_JS = """
(index) => {
  const widgets = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) widgets.push(el);
  }
  const w = widgets[index];
  if (!w) return null;
  const c = w.shadowRoot.querySelector('canvas');
  if (!c) return null;
  const r = c.getBoundingClientRect();
  return { x: r.left, y: r.top, w: r.width, h: r.height };
}
"""


def _canvas_rect(page, index: int) -> dict | None:
    """Return the canvas bounding rect {x, y, w, h} in page coordinates."""
    return page.evaluate(_CANVAS_RECT_JS, index)


def sample_canvas(page, index: int, points: list[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    """Sample canvas pixels at each (x, y) offset from canvas top-left.

    Takes a Playwright screenshot clipped to the canvas element (capturing
    deck.gl's composited output) then reads individual pixel values from the
    resulting PNG using Pillow.  Returns [(r, g, b, a), …].

    ``points`` are (x, y) offsets relative to the canvas top-left corner,
    matching the coordinate system used in ``widget.canvas_box()``.
    """
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Pillow is required for pixel sampling — install it with "
            "'pip install Pillow' or add it to the dev extras."
        ) from exc

    rect = _canvas_rect(page, index)
    if rect is None:
        return [(0, 0, 0, 0)] * len(points)

    # Clip screenshot to the canvas element.
    screenshot_bytes = page.screenshot(
        clip={
            "x": rect["x"],
            "y": rect["y"],
            "width": max(1, rect["w"]),
            "height": max(1, rect["h"]),
        }
    )
    img = Image.open(io.BytesIO(screenshot_bytes)).convert("RGBA")
    img_w, img_h = img.size

    out = []
    for (x, y) in points:
        # Clamp to canvas bounds.
        px = max(0, min(img_w - 1, int(x)))
        py = max(0, min(img_h - 1, int(y)))
        r, g, b, a = img.getpixel((px, py))
        out.append((r, g, b, a))
    return out


def read_pixels_at(page, index: int, x: int, y: int, w: int = 1, h: int = 1) -> list[int]:
    """Return RGBA values at canvas coord (x, y). Flat list of length w*h*4.

    Single-pixel convenience wrapper around ``sample_canvas``.
    w and h arguments are ignored (kept for API compatibility).
    """
    samples = sample_canvas(page, index, [(x, y)])
    if not samples:
        return [0, 0, 0, 0]
    r, g, b, a = samples[0]
    return [r, g, b, a]


def assert_non_black(samples: list[tuple[int, int, int, int]], threshold: int = 10) -> None:
    """Fail loudly if every sampled pixel is near-black."""
    for (r, g, b, _a) in samples:
        if r > threshold or g > threshold or b > threshold:
            return
    raise AssertionError(f"all {len(samples)} sampled pixels are near-black (<={threshold}): {samples}")
