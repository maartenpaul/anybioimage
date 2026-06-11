"""Rendering-backend registry: maps a backend name to its anywidget ESM source."""
KNOWN_BACKENDS = ("canvas2d", "viv")


def get_backend_esm(name: str) -> str:
    """Return the anywidget ESM source string for the given backend."""
    if name == "canvas2d":
        from . import canvas2d
        return canvas2d.get_esm()
    if name == "viv":
        from . import viv
        return viv.get_esm()
    raise ValueError(f"Unknown render_backend {name!r}; expected one of {KNOWN_BACKENDS}")
