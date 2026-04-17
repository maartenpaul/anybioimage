"""Rendering backend registry for BioImageViewer."""

from . import canvas2d, viv

KNOWN_BACKENDS = ("canvas2d", "viv")


def get_backend_esm(name: str) -> str:
    """Return the ESM source string for a given rendering backend.

    Args:
        name: One of the strings in KNOWN_BACKENDS.

    Raises:
        ValueError: if name is not a known backend.
    """
    if name == "canvas2d":
        return canvas2d.load_esm()
    if name == "viv":
        return viv.load_esm()
    raise ValueError(f"unknown render_backend: {name!r}")
