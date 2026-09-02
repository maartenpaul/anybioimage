# /// script
# requires-python = ">=3.11"
# dependencies = ["marimo", "anybioimage", "zarr"]
# ///

import marimo

__generated_with = "0.23.8"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    from anybioimage import BioImageViewer

    return BioImageViewer, mo


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Viv backend — local OME-Zarr through the kernel chunk bridge

    The browser cannot fetch files from disk, so for local / S3 / GCS stores the
    kernel opens the zarr with zarr-python and streams per-level tiles to Viv.
    Only the tiles Viv asks for are read; whole chunk blocks are cached so
    scrubbing T/Z inside a chunk is free.
    """)
    return


@app.cell
def _(mo):
    path = mo.ui.text(
        value="examples/image.zarr", label="OME-Zarr path", full_width=True
    )
    path
    return (path,)


@app.cell
def _(BioImageViewer, mo, path):
    viewer = BioImageViewer(render_backend="viv")
    viewer.set_image(path.value)
    mo.ui.anywidget(viewer)
    return


if __name__ == "__main__":
    app.run()
