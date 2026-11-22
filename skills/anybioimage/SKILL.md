---
name: anybioimage
description: "Use when writing or debugging notebook code (Jupyter or marimo) that displays or annotates biological images with anybioimage / BioImageViewer: numpy arrays, BioImage files, OME-Zarr paths or URLs, time-lapse or z-stack sliders, segmentation masks and label stacks, user-drawn rectangles / polygons / points read back into Python (rois_df, points_df, widget.value), SAM interactive segmentation, HCS plates, or the opt-in Viv backend for large and remote OME-Zarr."
---

# anybioimage

`BioImageViewer` is an anywidget for Jupyter and marimo: a 5D (TCZYX) viewer with
channel controls, mask overlays, drawing tools and SAM. This skill covers version
0.4.0 and later. Everything below is checked against the package source in this repo.

## Install

```bash
pip install anybioimage            # numpy arrays only (light)
pip install "anybioimage[all]"     # + bioio/TIFF, OME-Zarr, S3/GCS, contours (recommended)
pip install "anybioimage[zarr]"    # + OME-Zarr paths, HCS plates
pip install "anybioimage[sam]"     # + SAM via ultralytics (PyTorch; Python 3.11-3.12)
```

Python >= 3.11. Contour masks need scipy (`[contours]`, included in `[all]`). Opening a
zarr store without the `zarr` extra raises an ImportError naming `anybioimage[zarr]`.

## Show an image

`set_image` takes a numpy array, a bioio `BioImage`, an OME-Zarr path / `http(s)` /
`s3://` / `gs://` URL, or (viv backend only) a `zarr.Group`.

**numpy axes are read from `ndim` alone.** There is no `dims=` argument for images:

| `arr.ndim` | read as | sliders |
|---|---|---|
| 2 | YX | none |
| 3, last axis <= 4 | YXC (RGB/RGBA) | none |
| 3, otherwise | **CYX** (channels, not time) | none |
| 4 | **CZYX** | Z |
| 5 | TCZYX | T and Z |

Reshape to TCZYX before passing anything that is not in that order:

```python
viewer.set_image(movie[:, None, None])   # (T, Y, X)      -> (T, 1, 1, Y, X)
viewer.set_image(stack[:, None])         # (T, Z, Y, X)   -> (T, 1, Z, Y, X)
viewer.set_image(np.moveaxis(a, -1, 1)[:, :, None])  # (T, Y, X, C) -> (T, C, 1, Y, X)
```

Use `BioImage("file.ome.tif")` when the file carries its own dimension metadata.

**The viewer changes the resolution level of the `BioImage` you pass.** Zooming out
calls `img.set_resolution_level(n)` on that same object, so `img.dask_data` /
`img.get_image_data(...)` afterwards return the lower level. Read analysis data and crops
from a second `BioImage` opened on the same path. Do not reset the level on the object the
viewer uses: the viewer would then read level-0 data at the lower level's size.

**Channels** (colour, visibility, contrast) live in `viewer._channel_settings`, a list of
dicts. Assign a new list of copied dicts; editing the dicts in place does nothing:

```python
settings = [dict(c) for c in viewer._channel_settings]
settings[0].update(color="#0000ff", name="DAPI")
settings[1].update(color="#00ff00", visible=False, min=0.05, max=0.6)
viewer._channel_settings = settings
```

`min` / `max` are fractions of that channel's `[data_min, data_max]` (also in the dict). For a
percentile window: `lo = (np.percentile(ch, 2) - data_min) / (data_max - data_min)`.

## Jupyter vs marimo

```python
# Jupyter: the viewer object is the widget
viewer = BioImageViewer()
viewer.set_image(img)
viewer
```

```python
# marimo: wrap it, and return / display the wrapper
@app.cell
def _(BioImageViewer, mo, img):
    viewer = BioImageViewer()
    viewer.set_image(img)
    widget = mo.ui.anywidget(viewer)
    widget
    return viewer, widget
```

**Reading what the user draws, in marimo:** a cell that reads `viewer.rois_df` does not
re-run when the user draws. Read `widget.value` instead; marimo re-runs that cell on
every change:

```python
@app.cell
def _(pd, widget):
    points = pd.DataFrame(widget.value.get("_points_data", []), columns=["id", "x", "y", "t", "z"])
    rects = pd.DataFrame(widget.value.get("_rois_data", []), columns=["id", "x", "y", "width", "height", "t", "z"])
    points
    return points, rects
```

In Jupyter, `viewer.rois_df` / `polygons_df` / `points_df` always return the current
state; re-run the cell after drawing.

## Masks

```python
viewer.add_mask(labels)                         # 2D: shown on every plane
viewer.add_mask(tracks)                         # (T, Y, X): follows the T slider
viewer.add_mask(nuclei_3d)                      # (Z, Y, X): follows the Z slider
viewer.add_mask(labels_tzyx)                    # (T, Z, Y, X): follows both
viewer.add_mask(labels, dims="ZYX")             # needed only when the image has T == Z
viewer.add_mask(labels, color="#ffff00")        # whole mask in one colour
viewer.add_mask(labels, contours_only=True, contour_width=2)   # outlines (needs scipy)
viewer.update_mask_settings(mask_id, opacity=0.8, visible=False, contours=True)
viewer.remove_mask(mask_id); viewer.clear_masks(); viewer.masks_df
```

- Without `color`, each label value gets its own colour (good for instances). With
  `color`, `color_mode` is `"single"`. The layers-panel swatch does the same.
- A stack must match the image's T or Z size; otherwise `ValueError`. Leading singleton
  axes and TCZYX with one channel are accepted.
- Call `add_mask` after `set_image`: the stack is matched to the image's `dim_t` / `dim_z`.

## Annotations

Tools: Pan (P), Select (V), Rectangle (R, `tool_mode="draw"`), Polygon (G), Point (O).
Set the starting tool with `viewer.tool_mode = "point"`.

| DataFrame | columns |
|---|---|
| `viewer.rois_df` | id, x, y, width, height, t, z |
| `viewer.polygons_df` | id, points (list of {x, y}), num_vertices, t, z |
| `viewer.points_df` | id, x, y, t, z |

- `t` / `z` are the slider position when the shape was drawn. Crop with
  `img[t, z, y:y+height, x:x+width]` on your TCZYX array (index the channel too).
- Coordinates are pixels of the **displayed resolution level**. Every `BioImage` input
  has levels (OME-Zarr's own, or a 2x/4x pyramid built for flat files such as TIFF);
  wheel-zooming out below 50% switches to a lower level and `viewer.width` / `height`
  shrink with it. A shape does not record the level it was drawn at. Reliable options:
  ask the user to draw at 50% zoom or more (level 0), or check that
  `viewer.current_resolution` has not changed since drawing and multiply by
  `2 ** viewer.current_resolution` (OME-Zarr levels are usually factor 2; check the store
  if not). numpy input has no levels.
- Set annotations with `viewer.rois_df = df` (missing t/z default to 0). Clear with
  `clear_rois()`, `clear_polygons()`, `clear_points()`, `clear_all_annotations()`.
- `viewer.annotation_scope = "current"` shows only shapes drawn on the current T/Z.

## SAM

```python
viewer.enable_sam("mobile_sam")   # or "sam_b", "sam_l", "fast_sam"; downloads on first use
# rectangle or point in the viewer -> SAM mask layer
viewer.clear_sam_masks(); viewer.disable_sam()
```

## Large or remote OME-Zarr: the Viv backend

```python
viewer = BioImageViewer(render_backend="viv")              # WebGL (Viv / deck.gl)
viewer.set_image("https://host/data.ome.zarr")             # browser fetches chunks: zarr v2 only, server needs CORS
viewer.set_image("/data/big.ome.zarr")                     # local: kernel serves chunks, v2 + v3   [zarr]
viewer.set_image("s3://bucket/x.ome.zarr",
                 storage_options={"anon": True})           # S3/GCS through the kernel             [remote]
viewer.set_plate("https://host/plate.zarr")                # HCS: Well / FOV dropdowns
```

- Inactive on Viv-rendered images (alpha): masks, annotation tools, SAM, brightness /
  contrast, histograms. Contrast is set per channel (min / max) in the layers panel.
  Use the default backend when the user needs those.
- Non-zarr input on a viv viewer falls back to the default renderer automatically.
- An unreachable host raises `ConnectionError` naming the URL.

## What to expect (default backend, 2048x2048 planes)

- Stepping T/Z to a plane already in the browser: ~50-60 ms. First visit to a plane not
  yet in the browser: ~1-2 s (tiles travel through the kernel); the old picture is dimmed
  with a "Loading T 5/9" badge meanwhile. Neighbouring planes are prefetched.
- numpy arrays and BioImage data up to 2 GB are held in RAM; larger BioImage data is read
  lazily per plane.
- For a slow remote JupyterHub, `viewer.use_jpeg_tiles = True` sends smaller lossy tiles.

## Common mistakes

| Symptom | Cause | Fix |
|---|---|---|
| A time-lapse shows as many coloured channels, no T slider | 3D array read as CYX | `set_image(movie[:, None, None])` |
| Z-stack shows no Z slider, or T and Z swapped | 4D read as CZYX | build TCZYX: `stack[:, None]` for (T, Z, Y, X) |
| Table of drawn shapes never updates (marimo) | cell reads `viewer.rois_df` | read `widget.value["_rois_data"]` |
| `ValueError` from `add_mask` with a stack | stack length matches neither T nor Z, or T == Z | check shapes; pass `dims="TYX"` / `"ZYX"` |
| Crops come out at half / quarter size or offset | drawn at a lower pyramid level | draw at >= 50% zoom, or scale by `2 ** level` of the level used while drawing |
| Masks / drawing tools do nothing | Viv backend | drop `render_backend="viv"` for annotation work |
| `ImportError ... anybioimage[zarr]` | zarr extra missing | `pip install "anybioimage[zarr]"` |
| Full-resolution reads from a `BioImage` come back smaller | the viewer switched its level | read from a second `BioImage(path)` |
| Channel colour change has no effect | dicts in `_channel_settings` edited in place | assign `[dict(c) for c in ...]` with changes |
| marimo shows nothing | viewer not wrapped | `mo.ui.anywidget(viewer)` as the cell output |

## Reference files

- [references/api_reference.md](references/api_reference.md): method signatures, traitlets, channel settings.
- [references/examples.md](references/examples.md): longer workflows (fluorescence, segmentation, SAM, export).
