# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "anybioimage",
#     "bioio",
#     "bioio-ome-zarr",
#     "numpy",
# ]
# ///

import marimo

__generated_with = "0.23.8"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import numpy as np

    from anybioimage import BioImageViewer

    return BioImageViewer, mo, np


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Viv backend showcase — browser-direct remote OME-Zarr

    `BioImageViewer(render_backend="viv")` renders **remote OME-Zarr straight in
    the browser**. The notebook server only fetches the OME metadata once (axes,
    shape, OMERO channels); every pixel chunk is then pulled directly from the
    object store by Viv / deck.gl on a WebGL2 canvas. No precompute, no PNG
    thumbnails, no per-slice round-trips through the kernel.

    Pick a backend and a public dataset below and compare. The **same URL string**
    drives both backends — only the rendering path differs:

    | | `viv` | `canvas2d` (default) |
    |---|---|---|
    | Pixel source | browser → S3/HTTP chunks | kernel decodes + streams tiles |
    | First frame | metadata fetch, then GPU | RAM load + tile precompute |
    | Z / channel nav | new chunk GETs in browser | cached composites from kernel |

    Viv only takes over for URL-schemed `.zarr` / `.ome.zarr` strings — anything
    else (numpy arrays, local BioImage objects) silently falls back to Canvas2D on
    the same widget. The last cell demonstrates that fallback.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # (url, is_plate) — plates load via set_plate() (adds Well/FOV selectors),
    # single images via set_image(). Passing a plate to set_image() raises a
    # clear error pointing to set_plate().
    DATASETS = {
        "IDR idr0001A — 2551 (HCS plate)": (
            "https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0001A/2551.zarr",
            True,
        ),
        "IDR idr0062A — 6001247 (multichannel)": (
            "https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0062A/6001247.zarr",
            False,
        ),
        "EMBL zarr CORS issue": (
            "https://s3.embl.de/i2k-2020/spatial-transcriptomics-example/pos42/images/ome-zarr/MMStack_Pos42.ome.zarr",
            False,
        ),
    }

    backend = mo.ui.radio(
        {"Viv (browser-direct)": "viv", "Canvas2D (kernel tiles)": "canvas2d"},
        value="Viv (browser-direct)",
        inline=True,
        label="Render backend",
    )
    dataset = mo.ui.dropdown(
        list(DATASETS),
        value=list(DATASETS)[0],
        label="Public OME-Zarr dataset",
        full_width=True,
    )

    mo.vstack([backend, dataset], gap=1)
    return DATASETS, backend, dataset


@app.cell
def _(BioImageViewer, DATASETS, backend, dataset, mo):
    url, is_plate = DATASETS[dataset.value]

    viewer = BioImageViewer(render_backend=backend.value)
    if is_plate:
        viewer.set_plate(url)
    else:
        viewer.set_image(url)

    widget = mo.ui.anywidget(viewer)
    widget
    return (viewer,)


@app.cell(hide_code=True)
def _(backend, mo, viewer):
    # Live view of the viv-backend traitlets, so you can see which path is active.
    _source = viewer._zarr_source or {}
    _active = "viv (browser-direct)" if _source.get("url") else "canvas2d (kernel tiles)"

    mo.callout(
        mo.md(
            f"""
            **Requested backend:** `{backend.value}`
            **Active render path:** `{_active}`
            **`_render_backend`:** `{viewer._render_backend}`
            **`_zarr_source.url`:** `{_source.get("url", "—")}`
            **`_render_ready`:** `{viewer._render_ready}` (flips `True` once Viv paints the first frame)
            **Dimensions (T×C×Z×Y×X):** `{viewer.dim_t}×{viewer.dim_c}×{viewer.dim_z}×{viewer.height}×{viewer.width}`
            """
        ),
        kind="info" if _source.get("url") else "neutral",
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Fallback: numpy input on the viv backend

    A `BioImageViewer(render_backend="viv")` given a plain numpy array (not a zarr
    URL) renders through the Canvas2D pipeline on the same widget — one `INFO` log
    line, no error. `_zarr_source` stays empty.
    """)
    return


@app.cell
def _(BioImageViewer, mo, np):
    fallback_viewer = BioImageViewer(render_backend="viv")
    fallback_viewer.set_image((np.random.rand(2, 256, 256) * 65535).astype("uint16"))

    mo.vstack(
        [
            mo.ui.anywidget(fallback_viewer),
            mo.md(f"`_zarr_source` is empty → `{fallback_viewer._zarr_source}`"),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
