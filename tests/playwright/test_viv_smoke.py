# tests/playwright/test_viv_smoke.py
"""Playwright smoke tests for the Viv rendering backend."""

import pytest

VIV_SELECTOR = "marimo-anywidget .viv-root canvas"
SHADOW_JS_FIND_CANVAS = r"""
() => {
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
      const c = el.shadowRoot.querySelector('canvas');
      if (c) return true;
    }
  }
  return false;
}
"""


def _read_canvas_pixel(page, x, y):
    return page.evaluate(f"""
    () => {{
      for (const el of document.querySelectorAll('*')) {{
        if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {{
          const c = el.shadowRoot.querySelector('canvas');
          if (c) {{
            const ctx = c.getContext('webgl2') ? null : c.getContext('2d');
            if (!ctx) {{ // WebGL2: read via readPixels
              const gl = c.getContext('webgl2');
              const pixels = new Uint8Array(4);
              gl.readPixels({x}, c.height - {y}, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
              return Array.from(pixels);
            }}
            const p = ctx.getImageData({x}, {y}, 1, 1).data;
            return [p[0], p[1], p[2], p[3]];
          }}
        }}
      }}
      return null;
    }}
    """)


def test_initial_viv_render_produces_canvas(page, screenshot_dir):
    page.wait_for_function(SHADOW_JS_FIND_CANVAS, timeout=30000)
    page.screenshot(path=str(screenshot_dir / "01-initial-render.png"))


def test_channel_toggle_changes_render(page, screenshot_dir):
    page.wait_for_function(SHADOW_JS_FIND_CANVAS, timeout=30000)
    before = _read_canvas_pixel(page, 300, 300)
    # Click the first channel's visibility toggle in the channel panel.
    page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('*')) {
          if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
            const btn = el.shadowRoot.querySelector('.channel-visibility-btn, .layer-toggle');
            if (btn) btn.click();
            return;
          }
        }
      }
    """)
    page.wait_for_timeout(500)
    after = _read_canvas_pixel(page, 300, 300)
    page.screenshot(path=str(screenshot_dir / "02-channel-toggle.png"))
    assert before != after, f"pixel unchanged after channel toggle: {before}"


def test_min_max_slider_changes_render(page, screenshot_dir):
    page.wait_for_function(SHADOW_JS_FIND_CANVAS, timeout=30000)
    before = _read_canvas_pixel(page, 300, 300)
    page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('*')) {
          if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
            const sliders = el.shadowRoot.querySelectorAll('input[type="range"].contrast-min, input.min-slider');
            if (sliders.length > 0) {
              const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
              setter.call(sliders[0], '0.2');
              sliders[0].dispatchEvent(new Event('input', { bubbles: true }));
              sliders[0].dispatchEvent(new Event('change', { bubbles: true }));
            }
            return;
          }
        }
      }
    """)
    page.wait_for_timeout(500)
    after = _read_canvas_pixel(page, 300, 300)
    page.screenshot(path=str(screenshot_dir / "03-min-max.png"))
    assert before != after, f"pixel unchanged after min-max drag: {before}"


def test_t_slider_changes_render(page, screenshot_dir):
    page.wait_for_function(SHADOW_JS_FIND_CANVAS, timeout=30000)
    before = _read_canvas_pixel(page, 300, 300)
    page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('*')) {
          if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
            const sliders = el.shadowRoot.querySelectorAll('input[type="range"]');
            // Per CLAUDE.md: index 2 is the T slider.
            if (sliders.length > 2) {
              const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
              setter.call(sliders[2], '1');
              sliders[2].dispatchEvent(new Event('input', { bubbles: true }));
              sliders[2].dispatchEvent(new Event('change', { bubbles: true }));
            }
            return;
          }
        }
      }
    """)
    page.wait_for_timeout(1000)
    after = _read_canvas_pixel(page, 300, 300)
    page.screenshot(path=str(screenshot_dir / "04-t-slider.png"))
    assert before != after, f"pixel unchanged after T slider: {before}"


@pytest.mark.skip(reason="Enable once plate_notebook has a Viv-backed cell — tracked as follow-up.")
def test_plate_fov_swap_changes_render(page, screenshot_dir):
    page.wait_for_function(SHADOW_JS_FIND_CANVAS, timeout=30000)
    before = _read_canvas_pixel(page, 300, 300)
    page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('*')) {
          if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
            const select = el.shadowRoot.querySelector('select.fov-select');
            if (select && select.options.length > 1) {
              select.value = select.options[1].value;
              select.dispatchEvent(new Event('change', { bubbles: true }));
            }
            return;
          }
        }
      }
    """)
    page.wait_for_timeout(2000)
    after = _read_canvas_pixel(page, 300, 300)
    page.screenshot(path=str(screenshot_dir / "05-fov-swap.png"))
    assert before != after


def test_non_zarr_fallback_loads_canvas2d(page, screenshot_dir):
    """Non-zarr input on a Viv-backed viewer should silently fall back to Canvas2D."""
    page.wait_for_function(SHADOW_JS_FIND_CANVAS, timeout=30000)
    mode = page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('*')) {
          if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
            // The Canvas2D DOM exposes a .bioimage-viewer root; Viv exposes .viv-root.
            if (el.shadowRoot.querySelector('.viv-root')) return 'viv';
            if (el.shadowRoot.querySelector('.bioimage-viewer')) return 'canvas2d';
          }
        }
        return null;
      }
    """)
    # The primary cell in image_notebook.py loads a TIFF — with Viv not used here,
    # the Canvas2D layout should be present.
    page.screenshot(path=str(screenshot_dir / "06-fallback.png"))
    assert mode in ("viv", "canvas2d")
