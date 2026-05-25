# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "anybioimage",
#     "bioio",
#     "bioio-tifffile",
#     "bioio-ome-zarr",
#     "bioio-ome-tiff",
#     "bioio-bioformats",
#     "pandas",
# ]
# ///
import marimo

__generated_with = "0.23.8"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    import bioio_tifffile
    import bioio_ome_zarr
    import bioio_ome_tiff
    import bioio_bioformats
    from bioio import BioImage
    from anybioimage import BioImageViewer

    return (
        BioImage,
        BioImageViewer,
        bioio_bioformats,
        bioio_ome_tiff,
        bioio_ome_zarr,
        bioio_tifffile,
        mo,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # anybioimage Demo
    Interactive biological image viewer — load an example dataset or upload your own image.
    """)
    return


@app.cell(hide_code=True)
def _(bioio_bioformats, bioio_ome_tiff, bioio_ome_zarr, bioio_tifffile, mo):
    EXAMPLE_DATASETS = {
        "IDR HCS plate — idr0013A": {
            "url": "https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0013A/3451.zarr",
            "type": "plate",
        },
        "IDR fluorescence — multichannel 5D": {
            "url": "https://livingobjects.ebi.ac.uk/idr/zarr/v0.1/6001243.zarr",
            "type": "image",
        },
    }

    READERS = {
        "Auto-detect": None,
        "TIFF": bioio_tifffile.Reader,
        "OME-TIFF": bioio_ome_tiff.Reader,
 #       "OME-Zarr (local)": bioio_ome_zarr.Reader,
        "BioFormats (CZI / ND2 / LIF...)": bioio_bioformats.Reader,
    }

    source = mo.ui.radio(
        {"Example dataset": "example", "Remote URL": "url", "Upload file": "upload"},
        value="Example dataset",
        inline=True,
        label="Image source",
    )

    example_select = mo.ui.dropdown(
        list(EXAMPLE_DATASETS.keys()),
        value=list(EXAMPLE_DATASETS.keys())[0],
        label="Dataset",
        full_width=True,
    )

    url_input = mo.ui.text(
        placeholder="https://...",
        label="Zarr or image URL",
        full_width=True,
    )

    reader_select = mo.ui.dropdown(
        list(READERS.keys()),
        value="Auto-detect",
        label="Reader",
    )

    file_upload = mo.ui.file(
        label="Image file",
        filetypes=[".tif", ".tiff", ".zarr", ".nd2", ".czi", ".lif"],
    )
    return (
        EXAMPLE_DATASETS,
        READERS,
        example_select,
        file_upload,
        reader_select,
        source,
        url_input,
    )


@app.cell(hide_code=True)
def _(
    EXAMPLE_DATASETS,
    example_select,
    file_upload,
    mo,
    reader_select,
    source,
    url_input,
):
    if source.value == "example":
        _url = EXAMPLE_DATASETS[example_select.value]["url"]
        _panel = mo.vstack([
            example_select,
            mo.callout(mo.md(f"**URL:** `{_url}`"), kind="info"),
        ])
    elif source.value == "url":
        _panel = url_input
    else:
        _panel = mo.hstack([file_upload, reader_select], align="end", gap=2)

    mo.vstack([source, _panel], gap=2)
    return


@app.cell(hide_code=True)
def _(
    BioImage,
    EXAMPLE_DATASETS,
    READERS,
    bioio_ome_zarr,
    example_select,
    file_upload,
    mo,
    reader_select,
    source,
    url_input,
):
    import pathlib, tempfile

    _img = None
    _img_type = "image"

    if source.value == "example":
        _dataset = EXAMPLE_DATASETS[example_select.value]
        _img_type = _dataset["type"]
        if _img_type == "image":
            try:
                _img = BioImage(_dataset["url"], reader=bioio_ome_zarr.Reader)
                _status = mo.callout(
                    mo.md(f"Loaded **{example_select.value}** — shape: `{_img.shape}`"),
                    kind="success",
                )
            except Exception as _e:
                _status = mo.callout(mo.md(f"Load failed: `{_e}`"), kind="danger")
        else:
            _status = mo.callout(mo.md(f"Plate dataset selected: **{example_select.value}**"), kind="success")

    elif source.value == "url":
        _u = url_input.value.strip()
        if _u:
            try:
                _img = BioImage(_u, reader=bioio_ome_zarr.Reader)
                _status = mo.callout(
                    mo.md(f"Loaded `{_u}` — shape: `{_img.shape}`"),
                    kind="success",
                )
            except Exception as _e:
                _status = mo.callout(mo.md(f"Load failed: `{_e}`"), kind="danger")
        else:
            _status = mo.callout(mo.md("Enter a URL above to load an image."), kind="neutral")

    elif file_upload.value:
        _fi = file_upload.value[0]
        _suffix = pathlib.Path(_fi.name).suffix or ".tif"
        _reader = READERS.get(reader_select.value)
        try:
            with tempfile.NamedTemporaryFile(suffix=_suffix, delete=False) as _f:
                _f.write(_fi.contents)
                _tmp = _f.name
            _kwargs = {"reader": _reader} if _reader else {}
            _img = BioImage(_tmp, **_kwargs)
            _status = mo.callout(
                mo.md(f"Loaded **{_fi.name}** — shape: `{_img.shape}`"),
                kind="success",
            )
        except Exception as _e:
            _status = mo.callout(mo.md(f"Load failed: `{_e}`"), kind="danger")
    else:
        _status = mo.callout(mo.md("Upload an image file to continue."), kind="neutral")

    loaded_img = _img
    loaded_img_type = _img_type
    _status
    return loaded_img, loaded_img_type


@app.cell(hide_code=True)
def _(
    BioImageViewer,
    EXAMPLE_DATASETS,
    example_select,
    loaded_img,
    loaded_img_type,
    mo,
):
    _viewer = BioImageViewer()

    if loaded_img_type == "plate":
        _dataset = EXAMPLE_DATASETS[example_select.value]
        _viewer.set_plate(_dataset["url"])
    elif loaded_img is not None:
        _viewer.set_image(loaded_img)

    widget = mo.ui.anywidget(_viewer)
    widget
    return (widget,)


@app.cell(hide_code=True)
def _(mo, widget):
    import pandas as pd

    _rois = widget.value.get("_rois_data", [])
    _polys = widget.value.get("_polygons_data", [])
    _pts = widget.value.get("_points_data", [])

    _rois_df = pd.DataFrame(_rois) if _rois else pd.DataFrame(columns=["id", "x", "y", "width", "height"])
    _polys_df = pd.DataFrame([{"id": p["id"], "num_vertices": len(p["points"])} for p in _polys]) if _polys else pd.DataFrame(columns=["id", "num_vertices"])
    _pts_df = pd.DataFrame(_pts) if _pts else pd.DataFrame(columns=["id", "x", "y"])

    mo.vstack([
        mo.md("## Annotations"),
        mo.hstack([
            mo.vstack([mo.md("**Rectangles**"), _rois_df]),
            mo.vstack([mo.md("**Polygons**"), _polys_df]),
            mo.vstack([mo.md("**Points**"), _pts_df]),
        ], gap=4),
    ])
    return


if __name__ == "__main__":
    app.run()
