"""Integration-test harness — marimo + playwright + widget-ready gating.

This is the third testing tier [spec §4]:
  - tests/            — pytest (headless, no browser)
  - tests/playwright/ — smoke screenshots (existing)
  - tests/integration/— THIS: real gestures, asserts via traitlets + pixel reads

Fixtures (session):
  marimo_server  → URL of a running marimo server loading fixtures/demo_small.py
  browser        → Playwright chromium

Fixtures (function):
  page           → fresh page + console error collector
  widget         → WidgetHandle wrapping (page, model-accessor helpers)
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _pick_port() -> int:
    """Find a free localhost port for this session."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_marimo(notebook: Path, port: int) -> tuple[subprocess.Popen, str]:
    """Launch `marimo edit` in headless mode; return (process, url_with_token)."""
    cmd = [
        sys.executable, "-m", "marimo", "edit",
        str(notebook),
        "--headless",
        "--host", "127.0.0.1",
        "--port", str(port),
        "--no-token",          # simplest for tests — bypass the access-token dance
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    # Poll until the port responds.
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return proc, f"http://127.0.0.1:{port}/?file={notebook.name}"
        except OSError:
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError(f"marimo server did not start on port {port}")


@pytest.fixture(scope="session")
def marimo_server():
    """Start one marimo server for the whole session against demo_small.py."""
    port = _pick_port()
    proc, url = _start_marimo(FIXTURES_DIR / "demo_small.py", port)
    yield url
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def browser():
    """Session-scoped Playwright chromium browser."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch(
            headless=True,
            args=["--use-gl=swiftshader", "--disable-dev-shm-usage"],
        )
        yield br
        br.close()


@pytest.fixture
def page(browser):
    """Function-scoped page with console-error collector attached."""
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = context.new_page()
    pg._console_log = []   # type: ignore[attr-defined]
    pg.on("console", lambda m: pg._console_log.append((m.type, m.text)))
    yield pg
    context.close()


@pytest.fixture
def widget(page, marimo_server):
    """Load demo_small.py, wait for _render_ready, return a WidgetHandle."""
    from tests.integration.helpers.widget import WidgetHandle

    page.goto(marimo_server)
    page.wait_for_load_state("networkidle")
    handle = WidgetHandle(page, widget_index=0)
    handle.wait_for_ready(timeout_ms=30000)
    return handle
