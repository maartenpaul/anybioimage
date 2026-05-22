# tests/playwright/test_phase1_channels.py
"""Channel controls: open Layers panel, switch a channel to LUT."""
import pytest


@pytest.mark.playwright
def test_open_layers_and_switch_lut(page, marimo_url):
    page.goto(marimo_url)
    page.wait_for_timeout(8000)
    page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('marimo-anywidget')) {
          if (el.shadowRoot) {
            const btn = el.shadowRoot.querySelector('.layers-btn');
            if (btn) btn.click();
          }
        }
      }
    """)
    page.wait_for_timeout(300)
    page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('marimo-anywidget')) {
          if (el.shadowRoot) {
            const selects = [...el.shadowRoot.querySelectorAll('select')]
              .filter((s) => s.querySelector('option[value="solid"]'));
            if (selects.length) {
              selects[0].value = 'lut';
              selects[0].dispatchEvent(new Event('change', { bubbles: true }));
            }
          }
        }
      }
    """)
    page.wait_for_timeout(500)
    page.screenshot(path='/tmp/anybioimage-screenshots/phase1-lut.png')
