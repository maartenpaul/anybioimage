"""Two BioImageViewers side-by-side for keyboard-isolation testing [spec §5.2]."""
import marimo

__generated_with = "0.19.0"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import numpy as np
    from anybioimage import BioImageViewer

    rng = np.random.default_rng(7)
    img_a = rng.integers(10000, 50000, size=(5, 1, 1, 128, 128), dtype=np.uint16)
    img_b = rng.integers(10000, 50000, size=(5, 1, 1, 128, 128), dtype=np.uint16)

    viewer_a = BioImageViewer()
    viewer_a.set_image(img_a)
    viewer_b = BioImageViewer()
    viewer_b.set_image(img_b)
    return (viewer_a, viewer_b)


@app.cell
def _(mo, viewer_a):
    mo.ui.anywidget(viewer_a)
    return


@app.cell
def _(mo, viewer_b):
    mo.ui.anywidget(viewer_b)
    return


if __name__ == "__main__":
    app.run()
