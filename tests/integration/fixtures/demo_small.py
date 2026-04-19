"""Minimal integration-test notebook — one viewer, one in-RAM image.

Loaded by the `marimo_server` fixture in conftest.py. The notebook must
expose a `viewer` symbol at module scope so helpers can reach it via
marimo's inspector API.
"""
import marimo

__generated_with = "0.19.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import numpy as np
    from anybioimage import BioImageViewer

    rng = np.random.default_rng(42)
    # 3 channels × 256 × 256 uint16 — small enough to render fast, big
    # enough to have non-black pixels.
    img = rng.integers(10000, 50000, size=(5, 3, 3, 256, 256), dtype=np.uint16)

    viewer = BioImageViewer()
    viewer.set_image(img)
    return (viewer,)


@app.cell
def _(mo, viewer):
    mo.ui.anywidget(viewer)
    return


if __name__ == "__main__":
    app.run()
