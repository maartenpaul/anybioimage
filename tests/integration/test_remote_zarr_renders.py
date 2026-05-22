"""Remote OME-Zarr render pixels — DIAGNOSTIC VARIANT [spec §5.3].

This test verifies that loading a remote OME-Zarr URL produces a canvas with
actual image content (not blank black). The assertion scans the *entire*
canvas for the brightest pixel rather than sampling a few points: biological
images have dim backgrounds and bright features in sparse locations, so
pointwise sampling is unreliable.

Historical context (do not silence this test):
  * Before spec §5.3 fix: the IDR zarr rendered fully black because (a) the
    layer builder passed ``{t: 0}`` to sources whose axes list has no ``t``
    key, which threw inside Viv's ``ZarrPixelSource._indexer``, and (b)
    ``_set_zarr_url`` left ``_channel_settings`` empty so ``buildImageLayerProps``
    produced zero selections.
  * After the fix: axes-aware selections + Python-side OMERO pre-fetch →
    the image renders at OMERO's stored display window. Biological data
    often sits in the dim end of that window; we verify visible content
    exists (max brightness > threshold), not uniform brightness.
"""
from __future__ import annotations

import io
import time

import pytest


def _dump_console(widget):
    pg = widget._page
    print(f"\n=== CONSOLE LOG ({len(pg._console_log)} entries) ===")
    for t, msg in pg._console_log:
        print(f"[{t}] {msg}")
    print("=== END CONSOLE LOG ===")


def _canvas_brightness_max(page, index: int = 0) -> tuple[int, tuple[int, int]]:
    """Screenshot the canvas and return (max_brightness, (x, y)) over all pixels.

    ``max_brightness`` is ``max(r + g + b)`` over every pixel. A truly blank
    canvas returns 0; a canvas with any rendered content returns > 0 at the
    brightest pixel.
    """
    from PIL import Image

    rect = page.evaluate("""
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
    """, index)
    if rect is None:
        return 0, (0, 0)

    shot = page.screenshot(clip={"x": rect["x"], "y": rect["y"],
                                 "width": max(1, rect["w"]), "height": max(1, rect["h"])})
    img = Image.open(io.BytesIO(shot)).convert("RGBA")
    # Downsample to speed up scan: 1 sample per 8x8 pixel block.
    small = img.resize((img.width // 8 or 1, img.height // 8 or 1))
    pixels = small.load()
    best = 0
    at = (0, 0)
    for y in range(small.height):
        for x in range(small.width):
            r, g, b, _ = pixels[x, y]
            s = r + g + b
            if s > best:
                best = s
                at = (x * 8, y * 8)
    return best, at


@pytest.mark.integration
def test_remote_zarr_renders_non_black(widget_remote, page):
    """Remote OME-Zarr must produce visible image content within 15 s.

    Threshold is deliberately low (r+g+b > 15, i.e. ~RGB 5-per-channel).
    Biological images at OMERO's default display window can be dim; we verify
    ANY visible content, not bright content.
    """
    try:
        deadline = time.time() + 15
        best = 0
        at = (0, 0)
        while time.time() < deadline:
            best, at = _canvas_brightness_max(page)
            if best > 15:
                return  # success — visible content found
            page.wait_for_timeout(500)
        raise AssertionError(
            f"canvas appears fully black after 15 s: max brightness {best} at {at}. "
            "Image is not rendering. Check console for errors and that "
            "`_channel_settings` + `_image_shape` populate correctly in "
            "`_set_zarr_url`."
        )
    except Exception:
        _dump_console(widget_remote)
        raise
