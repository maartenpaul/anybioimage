"""Remote OME-Zarr fixture — loads a known-good public IDR URL [spec §5.3].

If IDR's URL changes or goes offline, swap for another known-good public zarr.
Verified upfront per risk §10 of the spec.
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
    from anybioimage import BioImageViewer

    # IDR 9822151.zarr — a public multiscale OME-Zarr. Swap if flaky.
    URL = "https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0062A/6001240.zarr"
    viewer = BioImageViewer()
    viewer.set_image(URL)
    return (viewer,)


@app.cell
def _(mo, viewer):
    mo.ui.anywidget(viewer)
    return


if __name__ == "__main__":
    app.run()
