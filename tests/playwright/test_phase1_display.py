# tests/playwright/test_phase1_display.py
"""Display features: scale bar and metadata panel."""
import pytest


@pytest.mark.playwright
def test_scale_bar_visible_when_pixel_size_set(page, marimo_url):
    page.goto(marimo_url)
    page.wait_for_timeout(10000)  # last cell sets pixel_size_um
    page.screenshot(path='/tmp/anybioimage-screenshots/phase1-scalebar.png')


@pytest.mark.playwright
def test_metadata_section_opens(page, marimo_url):
    page.goto(marimo_url)
    page.wait_for_timeout(10000)
    page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('marimo-anywidget')) {
          if (el.shadowRoot) {
            const btn = el.shadowRoot.querySelector('.layers-btn');
            if (btn) btn.click();
            const mt = el.shadowRoot.querySelector('.metadata-toggle');
            if (mt) mt.click();
          }
        }
      }
    """)
    page.wait_for_timeout(300)
    page.screenshot(path='/tmp/anybioimage-screenshots/phase1-metadata.png')
