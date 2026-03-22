---
name: anybioimage
description: "Integrate and use the anybioimage BioImageViewer widget to display biological images, overlays, and annotations in Jupyter and marimo notebooks. Use this skill when asked to display images with BioImageViewer, add mask overlays or segmentation results, annotate images with rectangles/polygons/points, enable SAM (Segment Anything Model) for interactive segmentation, load multi-dimensional 5D images (TCZYX) with BioImage, show multichannel fluorescence images with per-channel colors and contrast, export annotations as DataFrames, or integrate anybioimage into a marimo or Jupyter workflow."
---

# anybioimage Skill

`anybioimage` provides `BioImageViewer`, an interactive widget for visualizing biological images with mask overlays, annotations, and SAM segmentation in Jupyter and marimo notebooks.

## Installation

```bash
uv pip install -e ".[all]"   # Full install with all dependencies
uv pip install -e ".[sam]"   # SAM support only
```

## Quickstart

### Jupyter

```python
from anybioimage import BioImageViewer
import numpy as np

viewer = BioImageViewer()
viewer.set_image(np.random.randint(0, 255, (512, 512), dtype=np.uint8))
viewer  # Display inline
```

### Marimo

```python
import marimo as mo
from anybioimage import BioImageViewer

@app.cell
def _():
    viewer = BioImageViewer()
    viewer.set_image(image_data)
    return mo.ui.anywidget(viewer)
```

**Marimo rules:**
- Always wrap with `mo.ui.anywidget(viewer)`
- Only edit code inside `@app.cell` decorators
- Run `marimo check --fix` after editing

## Image Input

| Input | Method | Notes |
|-------|--------|-------|
| numpy array | `set_image(arr)` | Auto-squeezed to 2D |
| BioImage | `set_image(BioImage("file.tif"))` | Full 5D, lazy loading |
| OME-Zarr | `set_image(BioImage("file.ome.zarr"))` | Multi-resolution |

### BioImage (5D multichannel)

```python
from bioio import BioImage

viewer = BioImageViewer()
img = BioImage("multichannel.ome.tiff")
viewer.set_image(img)
# Dimension controls (T, C, Z) appear automatically in the UI
```

## Masks / Overlays

```python
# Add a segmentation mask
mask_id = viewer.add_mask(labels_array, name="Nuclei", color="#ff0000", opacity=0.5)

# Contour-only overlay
mask_id2 = viewer.add_mask(cell_labels, name="Cells", contours_only=True, contour_width=2)

# Convenience: clear all + add one
viewer.set_mask(labels_array, name="Segmentation")

# Update settings
viewer.update_mask_settings(mask_id, opacity=0.8, visible=False)

# Remove
viewer.remove_mask(mask_id)
viewer.clear_masks()

# Inspect
print(viewer.masks_df)  # DataFrame: id, name, visible, opacity, color, contours
```

`color` accepts hex strings. Colors auto-cycle from a 10-color palette if not specified.

## Annotations

```python
# Access as DataFrames (user-drawn or programmatically set)
rois     = viewer.rois_df      # columns: id, x, y, width, height
polygons = viewer.polygons_df  # columns: id, points (list of {x, y})
points   = viewer.points_df    # columns: id, x, y

# Export
rois.to_csv("rois.csv")

# Set programmatically
viewer.rois_df = existing_rois_df

# Clear
viewer.clear_rois()
viewer.clear_polygons()
viewer.clear_points()
viewer.clear_all_annotations()
```

**Drawing tools (keyboard shortcuts):** Pan (P), Select (V), Rectangle (R), Polygon (G), Point (O)

## SAM Integration

```python
# Enable (downloads model on first use via Ultralytics)
viewer.enable_sam("mobile_sam")   # Recommended: ~40MB, fast

# Draw rectangles or click points → SAM auto-segments
# SAM results appear as a mask overlay layer

viewer.clear_sam_masks()  # Clear SAM results
viewer.disable_sam()      # Disable and unload model
```

Model options: `"mobile_sam"` (default), `"sam_b"`, `"sam_l"`, `"fast_sam"`

## Visual Settings

```python
viewer.image_visible = True
viewer.image_brightness = 0.2   # -1.0 to 1.0
viewer.image_contrast = 0.3     # -1.0 to 1.0
viewer.canvas_height = 600      # pixels

# Annotation colors
viewer.roi_color = "#ff0000"
viewer.polygon_color = "#00ff00"
viewer.point_color = "#0000ff"
viewer.point_radius = 5         # pixels
```

## Reference Files

- **[api_reference.md](references/api_reference.md)** — Full method signatures, all traitlets, channel settings, internal details
- **[examples.md](references/examples.md)** — Complete workflow examples (fluorescence imaging, segmentation pipelines, annotation export)
