import marimo

__generated_with = "0.19.6"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    from bioio import BioImage
    import bioio_tifffile
    from anyimage import BioImageViewer
    return BioImage, BioImageViewer, bioio_tifffile, mo, pd


@app.cell
def _(BioImage, bioio_tifffile):
    img = BioImage("image.tif", reader=bioio_tifffile.Reader)
    mask = BioImage("mask.tif", reader=bioio_tifffile.Reader)
    return img, mask


@app.cell
def _(BioImageViewer, img, mask, mo):
    viewer = BioImageViewer()
    viewer.set_image(img.data)
    viewer.set_mask(mask.data)
    widget = mo.ui.anywidget(viewer)
    widget
    return (widget,)


@app.cell
def _(mo):
    mo.md("""
    ## ROI Annotations

    Use the **Draw ROI** button to switch to draw mode, then click and drag to create rectangles.
    The table below updates reactively as you draw.
    """)
    return


@app.cell
def _(pd, widget):
    rois_data = widget.value.get("_rois_data", [])
    rois_df = pd.DataFrame(rois_data) if rois_data else pd.DataFrame(columns=['id', 'x', 'y', 'width', 'height'])
    rois_df
    return


if __name__ == "__main__":
    app.run()
