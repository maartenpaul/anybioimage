# examples/full_demo.py
"""anybioimage — full demo notebook.

Run with: `marimo edit examples/full_demo.py`

Phase-1 sections exercise every v0.7.0 feature: unified pipeline, chunk bridge,
channel LUTs, metadata panel, scale bar, pixel-info hover, keyboard shortcuts.
"""

import marimo

__generated_with = "0.16.0"
app = marimo.App(width="full")


@app.cell
def _welcome():
    import marimo as mo
    mo.md(
        """
        # anybioimage demo

        One widget, every input format. Pan & zoom with the mouse, scrub T/Z with
        the sliders, toggle channels and their LUTs in the Layers panel.

        **Keyboard:** `←/→` time · `↑/↓` Z · `[/]` channel · `V` select · `P` pan
        """
    )
    return (mo,)


@app.cell
def _local_numpy(mo):
    import numpy as _np
    from anybioimage import BioImageViewer as _BioImageViewer
    _rng = _np.random.default_rng(0)
    _data = _rng.integers(0, 65535, size=(3, 2, 1, 1024, 1024), dtype=_np.uint16)
    _v = _BioImageViewer()
    _v.set_image(_data)
    mo.md("## 1 — Numpy array (chunk bridge)")
    mo.ui.anywidget(_v)
    return


@app.cell
def _local_zarr(mo):
    from pathlib import Path as _Path
    from anybioimage import BioImageViewer as _BioImageViewer2
    _zarr = _Path(__file__).parent / "image.zarr"
    _v2 = _BioImageViewer2()
    if _zarr.exists():
        _v2.set_image(str(_zarr))
        _ = mo.vstack([
            mo.md("## 2 — Local OME-Zarr (direct browser fetch)"),
            mo.ui.anywidget(_v2),
        ])
    else:
        _ = mo.md(f"**Skipped** — `{_zarr}` not present. Unpack `examples/image.zarr.tar.xz`.")
    _
    return


@app.cell
def _remote_zarr(mo):
    from anybioimage import BioImageViewer as _BioImageViewer3
    _v3 = _BioImageViewer3()
    # IDR sample — small multi-timepoint OME-Zarr
    _v3.set_image("https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0101A/13457537.zarr")
    mo.md("## 3 — Remote OME-Zarr (zarrita.js direct fetch)")
    mo.ui.anywidget(_v3)
    return


@app.cell
def _hcs_plate(mo):
    from anybioimage import BioImageViewer as _BioImageViewer4
    _v4 = _BioImageViewer4()
    try:
        _v4.set_plate("https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0001A/2551.zarr")
        _ = mo.vstack([
            mo.md("## 4 — HCS plate (Well + FOV dropdowns)"),
            mo.ui.anywidget(_v4),
        ])
    except Exception as _e:
        _ = mo.md(f"**Skipped** — plate fetch failed: {_e}")
    _
    return


@app.cell
def _display_features(mo):
    import numpy as _np2
    from anybioimage import BioImageViewer as _BioImageViewer5
    _v5 = _BioImageViewer5()
    _data2 = _np2.fromfunction(lambda c, y, x: ((x + y) * (c + 1)) % 65535,
                               (3, 512, 512), dtype=_np2.int32).astype(_np2.uint16)[None, :, None, :, :]
    _v5.set_image(_data2)
    _v5.pixel_size_um = 0.325   # synthetic scale
    mo.md("""
    ## 5 — Display features

    - Open the **Layers** panel → pick **LUT** instead of **Solid** for a channel, try `viridis`, `magma`.
    - Toggle **Scale bar** in the Layers-panel footer.
    - Hover over the image — `x, y · ch0:..., ch1:...` shows in the status bar.
    - Open **Metadata** at the top of the Layers panel.
    """)
    mo.ui.anywidget(_v5)
    return


@app.cell
def _perf(mo):
    import numpy as _np_perf
    from anybioimage import BioImageViewer as _BioImageViewerPerf

    _v_perf = _BioImageViewerPerf()
    _data_perf = _np_perf.random.randint(0, 65535, size=(10, 3, 5, 1024, 1024), dtype=_np_perf.uint16)
    _v_perf.set_image(_data_perf)

    mo.md("""
    ## 6 — Performance cell

    This cell measures the Phase-1 budget from the spec. Click through the widget
    to drive the metrics (T slider scrub, channel slider drag, etc.); the
    numbers update at the rate JS receives events.

    **Budget targets (spec §10):**

    | Metric | Target |
    |---|---|
    | Pan / zoom steady | 60 fps |
    | Channel slider drag → GPU | ≤16 ms |
    | T slider scrub (in-RAM) | ≤30 ms |
    | Cold tile fetch (local) | ≤30 ms |

    Open browser devtools performance panel while exercising the widget to
    capture detailed frame-timing numbers for a formal regression run.
    """)
    _ = mo.ui.anywidget(_v_perf)
    return


@app.cell
def _annotations(mo):
    from anybioimage import BioImageViewer
    import numpy as np

    v = BioImageViewer()
    v.set_image(np.random.randint(0, 255, (5, 1, 1, 512, 512), dtype=np.uint8))

    mo.md("""
    ## 7 — Annotations (Phase 2)

    Draw rectangles, polygons, and points interactively. The DataFrame views
    update live. Select the tool in the toolbar, then draw on the canvas:

    - **Rectangle** — drag.
    - **Polygon** — click vertices, double-click to close (or press Enter).
    - **Point** — click to place.
    """)
    return (v,)


@app.cell
def _annotations_tables(v, mo):
    mo.md("**Live DataFrame views (reactive):**")
    mo.ui.anywidget(v)
    return


@app.cell
def _annotations_rois_df(v, mo):
    mo.md("### Rectangles (`rois_df`)")
    mo.ui.table(v.rois_df)
    return


@app.cell
def _annotations_polygons_df(v, mo):
    mo.md("### Polygons (`polygons_df`)")
    mo.ui.table(v.polygons_df)
    return


@app.cell
def _annotations_points_df(v, mo):
    mo.md("### Points (`points_df`)")
    mo.ui.table(v.points_df)
    return


@app.cell
def _sam_section(mo):
    try:
        import ultralytics as _ultralytics  # noqa: F401
        _sam_available = True
    except Exception:
        _sam_available = False

    if _sam_available:
        from anybioimage import BioImageViewer as _BioImageViewerSam
        import numpy as _np_sam

        _v_sam = _BioImageViewerSam()
        # Small synthetic example — replace with a real cell image in practice.
        _data_sam = _np_sam.random.randint(0, 255, (1, 1, 1, 256, 256), dtype=_np_sam.uint8)
        _v_sam.set_image(_data_sam)
        _v_sam.enable_sam("mobile_sam")

        _ = mo.vstack([
            mo.md("""
    ## 8 — SAM walkthrough

    The Layers panel has a "Use SAM on next rect / point" checkbox. When
    enabled, drawing a rectangle (or placing a point) runs SAM and adds the
    resulting mask to the Masks section — no extra code required.
    """),
            mo.ui.anywidget(_v_sam),
        ])
    else:
        _ = mo.md("""
    ## 8 — SAM (optional)

    Install with `pip install anybioimage[sam]` to enable this section.
    """)
    _
    return


if __name__ == "__main__":
    app.run()
