# anybioimage

Interactive bioimage viewer widget for Jupyter and marimo notebooks. Built on [anywidget](https://anywidget.dev), it supports multi-dimensional images, multi-channel composites, mask overlays, annotation tools, and HCS plate navigation.

## Installation

```bash
uv pip install anybioimage

# With all recommended dependencies (excludes SAM/PyTorch)
uv pip install "anybioimage[all]"

# With SAM support (Python 3.10–3.12, requires PyTorch)
uv pip install "anybioimage[complete]"
```

## Quick Start

```python
from anybioimage import BioImageViewer

v = BioImageViewer()
v.set_image("https://s3.example.com/my.ome.zarr")   # remote OME-Zarr
v.set_image("local.tif")                             # local TIFF / CZI / ND2
v.set_image(numpy_array)                             # in-memory numpy
v.set_plate("plate.zarr")                            # HCS plate
```

### Jupyter

```python
from anybioimage import BioImageViewer

viewer = BioImageViewer()
viewer.set_image("image.tif")  # or pass a numpy array / remote URL
viewer  # renders inline
```

### marimo

```python
import marimo as mo
from anybioimage import BioImageViewer

viewer = BioImageViewer()
viewer.set_image("image.tif")  # or pass a numpy array / remote URL
mo.ui.anywidget(viewer)
```

## Features

### Multi-dimensional images

Supports 5D arrays (TCZYX: Time, Channel, Z-stack, Y, X) with sliders for T, Z, and per-channel controls. Pass a `BioImage` object for lazy loading — efficient for large TIFF and OME-Zarr files.

```python
from bioio import BioImage
import bioio_tifffile
import bioio_ome_zarr

img = BioImage("image.tif",  reader=bioio_tifffile.Reader)
img = BioImage("image.zarr", reader=bioio_ome_zarr.Reader)
viewer.set_image(img)  # activates T/Z sliders, per-channel LUT controls
```

### Multi-channel composites

Each channel has independent color, brightness/contrast (LUT), and visibility controls via the **Layers** panel in the toolbar. Channel settings can also be set programmatically:

```python
# Access and modify channel settings
settings = list(viewer._channel_settings)
settings[0] = {**settings[0], "name": "DAPI", "color": "#0000ff"}
viewer._channel_settings = settings
```

### Mask overlays

Add segmentation masks as overlay layers with configurable color, opacity, and contour rendering:

```python
viewer.add_mask(labels, name="Nuclei", color="#ff0000", opacity=0.5)
viewer.add_mask(cells, name="Cells", color="#00ff00", contours_only=True)

# Manage masks
viewer.update_mask_settings(mask_id, opacity=0.3)
viewer.remove_mask(mask_id)
viewer.clear_masks()
```

### HCS plate support

Load OME-Zarr HCS plates with well and FOV navigation dropdowns built into the widget:

```python
viewer = BioImageViewer()
viewer.set_plate("plate.zarr")
viewer  # shows Well / FOV dropdowns
```

### Annotation tools

| Tool | Shortcut | Description |
|------|----------|-------------|
| Pan | `P` | Navigate and zoom |
| Select | `V` | Select annotations; `Delete` to remove |
| Rectangle | `R` | Draw bounding boxes |
| Polygon | `G` | Click vertices, double-click to close |
| Point | `O` | Place point markers |

Export annotations as DataFrames:

```python
viewer.rois_df      # rectangles: id, x, y, width, height
viewer.polygons_df  # polygons: id, points, num_vertices
viewer.points_df    # points: id, x, y
```

### SAM integration

Automatic segmentation with [Segment Anything Model](https://segment-anything.com) when drawing rectangles or placing points:

```python
viewer.enable_sam(model_type="mobile_sam")  # ~40 MB, fastest
viewer.enable_sam(model_type="sam_b")       # SAM base, ~375 MB
```

Requires `uv pip install "anybioimage[sam]"` (Python 3.10–3.12).

## Optional dependencies

| Extra | Installs | Use case |
|-------|----------|----------|
| `bioio` | `bioio`, `bioio-tifffile` | TIFF / OME-Zarr loading |
| `contours` | `scipy` | Contour-only mask rendering |
| `sam` | `ultralytics` (PyTorch) | SAM segmentation |
| `all` | bioio + contours | Recommended (no PyTorch) |
| `complete` | all + sam | Everything |

## Rendering

`BioImageViewer` uses a unified WebGL2 rendering pipeline (Viv + deck.gl) for every input format. Browsers without WebGL2 see a guidance message instead of the widget.

> **Note:** The `render_backend` kwarg is accepted for one release with a `DeprecationWarning`; it is ignored and will be removed in v0.8.0.

## Acknowledgements

Built on the following MIT-licensed projects:

- [`@hms-dbmi/viv`](https://github.com/hms-dbmi/viv) — WebGL2 multiscale image rendering
- [`zarrita.js`](https://github.com/manzt/zarrita.js) — browser-side Zarr v2/v3 client (bundled by Viv)
- [`deck.gl`](https://github.com/visgl/deck.gl) — view and layer management
- [`nebula.gl`](https://github.com/uber/nebula.gl) — annotation editing layers (used from Phase 3)

## License

MIT
