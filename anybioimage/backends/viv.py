"""Viv backend loader — reads the bundled JS from the wheel data files."""

from importlib.resources import files

_ESM_CACHE: str | None = None


def load_esm() -> str:
    """Return the compiled Viv bundle ESM string (cached after first read)."""
    global _ESM_CACHE
    if _ESM_CACHE is None:
        _ESM_CACHE = (
            files("anybioimage.frontend.viv") / "dist" / "viv-bundle.js"
        ).read_text(encoding="utf-8")
    return _ESM_CACHE
