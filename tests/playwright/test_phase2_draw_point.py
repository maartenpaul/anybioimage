# tests/playwright/test_phase2_draw_point.py
"""Phase 2 smoke — place a point."""
from __future__ import annotations

import os
import time

import pytest
from playwright.sync_api import sync_playwright

SCREENSHOTS = "/tmp/anybioimage-screenshots"


@pytest.mark.playwright
def test_phase2_draw_point():
    os.makedirs(SCREENSHOTS, exist_ok=True)
    token = os.environ.get("MARIMO_TOKEN", "")
    url = f"http://localhost:2718?access_token={token}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        page.evaluate("""() => {
          for (const el of document.querySelectorAll('*')) {
            if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
              [...el.shadowRoot.querySelectorAll('button')]
                .find(b => b.title && b.title.startsWith('Point')).click();
              return;
            }
          }
        }""")
        time.sleep(0.3)

        box = page.evaluate("""() => {
          for (const el of document.querySelectorAll('*')) {
            if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
              const c = el.shadowRoot.querySelector('canvas');
              const r = c.getBoundingClientRect();
              return { x: r.left, y: r.top, w: r.width, h: r.height };
            }
          }
        }""")
        page.mouse.click(box["x"] + box["w"] * 0.5, box["y"] + box["h"] * 0.5)
        time.sleep(0.5)
        page.screenshot(path=f"{SCREENSHOTS}/phase2-point-placed.png")
        browser.close()
