"""Canvas2D backend loader — reads the ESM from the shipped source file."""

from importlib.resources import files

_ESM_CACHE: str | None = None


def load_esm() -> str:
    """Return the Canvas2D ESM source string (cached after first read)."""
    global _ESM_CACHE
    if _ESM_CACHE is None:
        _ESM_CACHE = (
            files("anybioimage.frontend.shared") / "canvas2d.js"
        ).read_text(encoding="utf-8")
    return _ESM_CACHE
