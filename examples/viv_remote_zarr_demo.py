import marimo

__generated_with = "0.19.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    from anybioimage import BioImageViewer

    # Public IDR OME-Zarr (same fixture URL the viv-backend branch validated against)
    URL = "https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0062A/6001240.zarr"
    viewer = BioImageViewer(render_backend="viv")
    viewer.set_image(URL)
    mo.ui.anywidget(viewer)
    return (viewer,)


@app.cell
def _(viewer):
    # Readiness probe for browser tests: flips True once the Viv canvas rendered.
    viewer._render_ready
    return


@app.cell
def _(mo):
    import numpy as np

    from anybioimage import BioImageViewer as _BIV

    # Fallback check: numpy input on the viv backend renders via Canvas2D
    fallback_viewer = _BIV(render_backend="viv")
    fallback_viewer.set_image(
        (np.random.rand(2, 256, 256) * 65535).astype("uint16")
    )
    mo.ui.anywidget(fallback_viewer)
    return


if __name__ == "__main__":
    app.run()
