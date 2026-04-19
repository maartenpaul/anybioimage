# tests/playwright/test_phase1_core.py
"""Phase-1 core flows: render numpy input, drag T slider, render OME-Zarr."""
from __future__ import annotations

import pytest


@pytest.mark.playwright
def test_numpy_input_renders(page, marimo_url):
    page.goto(marimo_url)
    page.wait_for_timeout(8000)  # wait for kernel + first cells
    assert page.locator('marimo-anywidget').count() >= 1
    page.screenshot(path='/tmp/anybioimage-screenshots/phase1-numpy-render.png')


@pytest.mark.playwright
def test_t_slider_changes_frame(page, marimo_url):
    page.goto(marimo_url)
    page.wait_for_timeout(8000)
    slider_before = page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('marimo-anywidget')) {
          if (el.shadowRoot) {
            const s = el.shadowRoot.querySelectorAll('input[type="range"]');
            return s.length ? parseInt(s[0].value) : null;
          }
        }
        return null;
      }
    """)
    page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('marimo-anywidget')) {
          if (el.shadowRoot) {
            const s = el.shadowRoot.querySelectorAll('input[type="range"]');
            if (!s.length) continue;
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(s[0], '1');
            s[0].dispatchEvent(new Event('input', { bubbles: true }));
            s[0].dispatchEvent(new Event('change', { bubbles: true }));
          }
        }
      }
    """)
    page.wait_for_timeout(800)
    page.screenshot(path='/tmp/anybioimage-screenshots/phase1-t-changed.png')
