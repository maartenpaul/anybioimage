# anyimage API Reference

## Table of Contents
1. [BioImageViewer — Public Methods](#public-methods)
2. [Masks API](#masks-api)
3. [Annotations API](#annotations-api)
4. [SAM API](#sam-api)
5. [Traitlets (synced state)](#traitlets)
6. [Channel Settings](#channel-settings)
7. [Utility Functions](#utility-functions)

---

## Public Methods

### Image Loading

```python
viewer.set_image(data)
```
- `data`: `np.ndarray` (auto-squeezed to 2D) or `BioImage` object
- For numpy: no multi-dim controls shown
- For BioImage: full 5D support, lazy loading, channel settings auto-initialized

---

## Masks API

```python
mask_id = viewer.add_mask(
    labels,           # np.ndarray of integer labels (0 = background)
    name=None,        # str, auto-generated if None
    color=None,       # hex str e.g. "#ff0000", auto-cycles if None
    opacity=0.5,      # float 0–1
    visible=True,     # bool
    contours_only=False,  # bool, show boundary contours only
    contour_width=1,  # int, contour thickness in pixels
) -> str              # returns unique mask_id
```

```python
viewer.set_mask(labels, name=None, contours_only=False, contour_width=1)
# Clears all existing masks, then adds one mask
```

```python
viewer.remove_mask(mask_id)       # Remove a single mask by ID
viewer.clear_masks()              # Remove all masks
viewer.get_mask_ids() -> list     # List all current mask IDs
viewer.update_mask_settings(mask_id, **kwargs)
# Supported kwargs: name, color, opacity, visible, contours_only, contour_width
```

```python
viewer.masks_df  # pandas DataFrame
# Columns: id, name, visible, opacity, color, contours
```

**Color cycling palette:** 10 colors auto-assigned in order. Override with explicit `color="#rrggbb"`.

---

## Annotations API

All coordinates are in **image pixel space** (not screen/canvas space).

### ROIs (Rectangles)

```python
viewer.rois_df          # get: DataFrame with columns id, x, y, width, height
viewer.rois_df = df     # set: DataFrame with same columns
viewer.clear_rois()
```

### Polygons

```python
viewer.polygons_df          # get: DataFrame with columns id, points
viewer.polygons_df = df     # set
viewer.clear_polygons()
# points column: list of dicts [{x: float, y: float}, ...]
```

### Points

```python
viewer.points_df            # get: DataFrame with columns id, x, y
viewer.points_df = df       # set
viewer.clear_points()
```

### Clear all

```python
viewer.clear_all_annotations()
```

### Annotation display traitlets

```python
viewer.rois_visible = True
viewer.roi_color = "#ff0000"         # hex

viewer.polygons_visible = True
viewer.polygon_color = "#00ff00"     # hex

viewer.points_visible = True
viewer.point_color = "#0000ff"       # hex
viewer.point_radius = 5              # int, pixels

viewer.selected_annotation_id        # str, read-only (user interaction)
viewer.selected_annotation_type      # "roi" | "polygon" | "point"
```

### Tool modes

```python
viewer.tool_mode  # "pan" | "select" | "draw" | "polygon" | "point"
# Keyboard shortcuts in viewer: P=pan, V=select, R=rectangle, G=polygon, O=point
```

---

## SAM API

```python
viewer.enable_sam(model_type="mobile_sam")
# Downloads model on first use via Ultralytics
# Supported: "mobile_sam" (~40MB), "sam_b" (~375MB), "sam_l" (~1.2GB), "fast_sam" (~140MB)

viewer.disable_sam()
viewer.clear_sam_masks()
viewer.delete_sam_label_at(x, y)   # Delete SAM label at pixel coordinates
```

**Workflow:** After `enable_sam()`, drawing a rectangle or placing a point automatically triggers SAM segmentation. Results appear as a mask layer. The rectangle/point annotation is removed after processing.

---

## Traitlets

These are synchronized between Python and the JavaScript frontend. All can be read/written from Python.

### Image state

| Traitlet | Type | Description |
|----------|------|-------------|
| `image_data` | `Unicode` | Base64 PNG of current rendered frame |
| `width` | `Int` | Image width in pixels |
| `height` | `Int` | Image height in pixels |
| `image_visible` | `Bool` | Show/hide base image |
| `image_brightness` | `Float` | -1.0 to 1.0 |
| `image_contrast` | `Float` | -1.0 to 1.0 |
| `canvas_height` | `Int` | Canvas height in pixels (default 800) |

### Multi-dimensional navigation

| Traitlet | Type | Description |
|----------|------|-------------|
| `dim_t` | `Int` | Number of timeframes |
| `dim_c` | `Int` | Number of channels |
| `dim_z` | `Int` | Number of Z-slices |
| `current_t` | `Int` | Current timeframe (0-indexed) |
| `current_c` | `Int` | Current channel (single-channel mode) |
| `current_z` | `Int` | Current Z-slice |
| `current_resolution` | `Int` | Current resolution level |
| `resolution_levels` | `List` | Available resolution levels |

### Scenes

| Traitlet | Type | Description |
|----------|------|-------------|
| `scenes` | `List[Unicode]` | Available scene names |
| `current_scene` | `Unicode` | Active scene name |

---

## Channel Settings

`viewer._channel_settings` is a list of dicts, one per channel:

```python
{
    "name": str,         # Channel name
    "color": str,        # Hex color e.g. "#00ff00"
    "visible": bool,
    "min": float,        # Contrast lower bound (0–1, relative to data range)
    "max": float,        # Contrast upper bound (0–1, relative to data range)
    "data_min": float,   # Global data minimum for normalization
    "data_max": float,   # Global data maximum for normalization
}
```

Example: set channel 0 to red, channel 1 to cyan:

```python
settings = viewer._channel_settings.copy()
settings[0]["color"] = "#ff0000"
settings[1]["color"] = "#00ffff"
viewer._channel_settings = settings
```

Default channel colors follow the `CHANNEL_COLORS` palette: GFP green, RFP red, DAPI blue, etc.

---

## Utility Functions

```python
from anyimage import normalize_image, array_to_base64, labels_to_rgba, hex_to_rgb, composite_channels, MASK_COLORS, CHANNEL_COLORS
```

```python
normalize_image(data, global_min=None, global_max=None) -> np.ndarray
# Normalize array to uint8 (0-255). Uses data range if min/max not provided.

array_to_base64(data) -> str
# Convert (H,W), (H,W,3), or (H,W,4) array to base64 PNG string.

labels_to_rgba(labels, contours_only=False, contour_width=1) -> np.ndarray
# Convert integer label array to RGBA (H,W,4). 0 = transparent.

hex_to_rgb(hex_color) -> tuple[int, int, int]
# "#ff0000" -> (255, 0, 0)

composite_channels(channels, colors, mins, maxs, data_mins=None, data_maxs=None) -> np.ndarray
# Additive blend of multiple 2D channel arrays into RGB uint8.
# channels: list of (H,W) arrays
# colors: list of hex strings
# mins/maxs: contrast bounds per channel (0-1)

MASK_COLORS   # list of 10 hex colors for mask auto-assignment
CHANNEL_COLORS  # list of 8 hex colors for channel auto-assignment
```
