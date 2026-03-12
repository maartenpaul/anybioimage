# anyimage Usage Examples

## Table of Contents
1. [Basic 2D Image Display](#basic-2d-image-display)
2. [Multichannel Fluorescence Image](#multichannel-fluorescence-image)
3. [Segmentation Mask Overlay](#segmentation-mask-overlay)
4. [Multiple Mask Layers](#multiple-mask-layers)
5. [SAM Segmentation Workflow](#sam-segmentation-workflow)
6. [Annotation Export Pipeline](#annotation-export-pipeline)
7. [Marimo Integration](#marimo-integration)
8. [Large Image (OME-Zarr)](#large-image-ome-zarr)

---

## Basic 2D Image Display

```python
from anyimage import BioImageViewer
import numpy as np

viewer = BioImageViewer()
viewer.set_image(np.random.randint(0, 255, (512, 512), dtype=np.uint8))
viewer.canvas_height = 600
viewer
```

---

## Multichannel Fluorescence Image

```python
from anyimage import BioImageViewer
from bioio import BioImage

viewer = BioImageViewer()
img = BioImage("dapi_gfp_rfp.ome.tiff")  # 3-channel fluorescence
viewer.set_image(img)
# UI shows channel controls with default colors: DAPI=blue, GFP=green, RFP=red
# User can toggle channels and adjust contrast in the viewer

# Programmatically set channel colors
settings = list(viewer._channel_settings)
settings[0]["color"] = "#0000ff"  # DAPI → blue
settings[1]["color"] = "#00ff00"  # GFP → green
settings[2]["color"] = "#ff0000"  # RFP → red
viewer._channel_settings = settings

viewer
```

---

## Segmentation Mask Overlay

```python
from anyimage import BioImageViewer
import numpy as np
from skimage.filters import threshold_otsu
from skimage.measure import label

# Load and segment
image = np.load("nuclei.npy")
thresh = threshold_otsu(image)
binary = image > thresh
labels = label(binary)  # integer label array

# Display with overlay
viewer = BioImageViewer()
viewer.set_image(image)
mask_id = viewer.add_mask(labels, name="Nuclei", color="#ff4400", opacity=0.6)

viewer
```

### Contours only

```python
viewer.add_mask(labels, name="Nuclei outlines", contours_only=True, contour_width=2)
```

---

## Multiple Mask Layers

```python
viewer = BioImageViewer()
viewer.set_image(image)

# Add multiple segmentation results as separate layers
nuc_id = viewer.add_mask(nuclei_labels, "Nuclei", "#ff0000", opacity=0.5)
cell_id = viewer.add_mask(cell_labels, "Cells", "#00ff00", contours_only=True)
mito_id = viewer.add_mask(mito_labels, "Mitochondria", "#0000ff", opacity=0.4)

# Inspect all layers
print(viewer.masks_df)

# Toggle visibility
viewer.update_mask_settings(mito_id, visible=False)

# Change opacity
viewer.update_mask_settings(cell_id, opacity=0.8)

viewer
```

---

## SAM Segmentation Workflow

```python
from anyimage import BioImageViewer
from bioio import BioImage

viewer = BioImageViewer()
img = BioImage("cells.tif")
viewer.set_image(img)

# Enable SAM (downloads model ~40MB on first use)
viewer.enable_sam("mobile_sam")

# Now interact in the viewer:
# - Draw rectangle (R key) → SAM segments the region
# - Click point (O key) → SAM segments the object at that point
# - Press Delete on a SAM mask to remove it
# - viewer.clear_sam_masks() to reset all SAM results

viewer
```

### Export SAM results as mask

```python
# After interactive segmentation, access the SAM mask layer
sam_mask_id = viewer._sam_mask_id
print(viewer.masks_df[viewer.masks_df["id"] == sam_mask_id])

# Or access the raw label array
sam_labels = viewer._sam_labels_array  # numpy array of integer labels
```

---

## Annotation Export Pipeline

```python
viewer = BioImageViewer()
viewer.set_image(image)
# User draws annotations interactively...

# Export all annotation types
rois = viewer.rois_df
polygons = viewer.polygons_df
points = viewer.points_df

print(f"ROIs: {len(rois)}, Polygons: {len(polygons)}, Points: {len(points)}")

# Save to CSV
rois.to_csv("rois.csv", index=False)
points.to_csv("points.csv", index=False)

# Filter by position
large_rois = rois[(rois["width"] > 50) & (rois["height"] > 50)]

# Set annotations programmatically (e.g. load from previous session)
viewer.rois_df = large_rois
```

---

## Marimo Integration

```python
import marimo as mo
from anyimage import BioImageViewer
from bioio import BioImage

@app.cell
def _():
    viewer = BioImageViewer()
    return viewer

@app.cell
def _(viewer):
    from bioio import BioImage
    img = BioImage("data.tif")
    viewer.set_image(img)
    return mo.ui.anywidget(viewer)

@app.cell
def _(viewer):
    # Reactive: updates when user draws annotations
    rois = viewer.rois_df
    return rois

@app.cell
def _(rois):
    # Display annotation table
    mo.ui.table(rois)
```

**Key marimo rules:**
- Always return `mo.ui.anywidget(viewer)` from the cell that displays the viewer
- Each cell should be a pure function of its inputs
- Run `marimo check --fix` after editing

---

## Large Image (OME-Zarr)

```python
from anyimage import BioImageViewer
from bioio import BioImage

viewer = BioImageViewer()

# Multi-resolution OME-Zarr with lazy loading
img = BioImage("large_dataset.ome.zarr")
viewer.set_image(img)

# Viewer automatically:
# - Uses tile-based rendering for 1MP+ images
# - Selects resolution level based on zoom
# - Prefetches adjacent Z/T slices during navigation
# - Shows resolution level controls if multiple levels available

viewer.canvas_height = 900
viewer
```

### Navigate programmatically

```python
# Set slice position
viewer.current_t = 5   # timeframe 5
viewer.current_z = 10  # z-slice 10
# Image updates automatically
```
