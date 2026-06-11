"""Default backend: main's original inline Canvas2D viewer, served as a raw
ESM string. Self-contained vanilla JS — no Node toolchain involved."""
from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=1)
def get_esm() -> str:
    chrome = files("anybioimage") / "frontend" / "viewer" / "src" / "canvas2d-chrome.js"
    try:
        return chrome.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise RuntimeError(
            "Canvas2D chrome not found — the anybioimage installation is missing "
            "frontend/viewer/src/canvas2d-chrome.js (broken package build?)"
        ) from e
