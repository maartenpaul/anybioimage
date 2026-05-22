# tests/playwright/test_phase2_draw_rect.py
"""Phase 2 smoke — draw a rectangle via pointer events."""
from __future__ import annotations

import os
import subprocess
import time

import pytest
from playwright.sync_api import sync_playwright

SCREENSHOTS = "/tmp/anybioimage-screenshots"


def ensure_screenshots_dir() -> None:
    os.makedirs(SCREENSHOTS, exist_ok=True)


@pytest.mark.playwright
def test_phase2_draw_rect():
    ensure_screenshots_dir()
    # Assume a marimo server is already running — CI starts one in conftest.
    token = os.environ.get("MARIMO_TOKEN", "")
    url = f"http://localhost:2718?access_token={token}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        # Switch to rectangle tool.
        page.evaluate("""() => {
          for (const el of document.querySelectorAll('*')) {
            if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
              const btn = [...el.shadowRoot.querySelectorAll('button')].find(
                b => b.title && b.title.startsWith('Rectangle'));
              btn.click();
              return;
            }
          }
        }""")
        time.sleep(0.5)

        # Drag on the canvas.
        box = page.evaluate("""() => {
          for (const el of document.querySelectorAll('*')) {
            if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
              const c = el.shadowRoot.querySelector('canvas');
              const r = c.getBoundingClientRect();
              return { x: r.left, y: r.top, w: r.width, h: r.height };
            }
          }
        }""")
        assert box
        sx = box["x"] + box["w"] * 0.25
        sy = box["y"] + box["h"] * 0.25
        ex = box["x"] + box["w"] * 0.5
        ey = box["y"] + box["h"] * 0.5
        page.mouse.move(sx, sy)
        page.mouse.down()
        page.mouse.move(ex, ey, steps=10)
        page.mouse.up()
        time.sleep(1.0)

        page.screenshot(path=f"{SCREENSHOTS}/phase2-rect-drawn.png")
        browser.close()
