# tests/playwright/conftest.py
"""Fixtures for Playwright smoke tests against a live marimo server."""

import os
import re
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCREENSHOT_DIR = Path("/tmp/anybioimage-screenshots")
NOTEBOOK = REPO_ROOT / "examples" / "image_notebook.py"


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_token(proc, timeout=30):
    deadline = time.time() + timeout
    buf = []
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                raise RuntimeError(f"marimo exited early:\n{''.join(buf)}")
            continue
        buf.append(line)
        m = re.search(r"access_token=([0-9a-f-]+)", line)
        if m:
            return m.group(1), "".join(buf)
    raise TimeoutError(f"access token never printed:\n{''.join(buf)}")


@pytest.fixture(scope="session")
def screenshot_dir():
    if SCREENSHOT_DIR.exists():
        shutil.rmtree(SCREENSHOT_DIR)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    yield SCREENSHOT_DIR
    # Keep artifacts on failure; the CI agent collects them. For local dev,
    # uncomment the next line to auto-clean after passing runs:
    # shutil.rmtree(SCREENSHOT_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def marimo_server():
    port = _free_port()
    env = {**os.environ, "ANYBIOIMAGE_PLAYWRIGHT": "1"}
    proc = subprocess.Popen(
        ["marimo", "edit", str(NOTEBOOK), "--port", str(port), "--no-token-check", "--headless"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        bufsize=1,
    )
    try:
        token, _ = _wait_for_token(proc)
        yield f"http://localhost:{port}?access_token={token}"
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture
def page(browser, marimo_server, screenshot_dir):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    page = ctx.new_page()
    page.goto(marimo_server)
    page.wait_for_load_state("networkidle", timeout=30000)
    yield page
    ctx.close()
