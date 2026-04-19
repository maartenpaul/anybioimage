"""Pixel sampling for integration tests.

Reads canvas pixels via deck.gl's `readPixels` [spec §4] so we don't trip the
tainted-canvas rule that affects `getImageData` on WebGL-sourced images from
cross-origin contexts.
"""
from __future__ import annotations


_READ_PIXELS_JS = """
([index, x, y, w, h]) => {
  const widgets = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) widgets.push(el);
  }
  const w2 = widgets[index];
  if (!w2) return null;
  const canvas = w2.shadowRoot.querySelector('canvas');
  if (!canvas) return null;
  // Use the WebGL context's readPixels directly — avoids the 2D-context
  // getImageData path entirely.
  const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
  if (!gl) return null;
  const pixels = new Uint8Array(w * h * 4);
  gl.readPixels(x, y, w, h, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
  return Array.from(pixels);
}
"""


def read_pixels_at(page, index: int, x: int, y: int, w: int = 1, h: int = 1) -> list[int]:
    """Return RGBA values at canvas coord (x, y). Flat list of length w*h*4."""
    return page.evaluate(_READ_PIXELS_JS, [index, x, y, w, h]) or []


def sample_canvas(page, index: int, points: list[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    """Sample canvas pixels at each (x, y) in `points`; return [(r,g,b,a), ...]."""
    out = []
    for (x, y) in points:
        px = read_pixels_at(page, index, x, y, 1, 1)
        if len(px) < 4:
            out.append((0, 0, 0, 0))
        else:
            out.append((px[0], px[1], px[2], px[3]))
    return out


def assert_non_black(samples: list[tuple[int, int, int, int]], threshold: int = 10) -> None:
    """Fail loudly if every sampled pixel is near-black."""
    for (r, g, b, _a) in samples:
        if r > threshold or g > threshold or b > threshold:
            return
    raise AssertionError(f"all {len(samples)} sampled pixels are near-black (<={threshold}): {samples}")
