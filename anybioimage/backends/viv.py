"""Temporary loader; merged into viewer.py in a later task."""
from importlib.resources import files


def load_esm() -> str:
    path = files("anybioimage.frontend.viewer.dist").joinpath("viewer-bundle.js")
    return path.read_text(encoding="utf-8")
