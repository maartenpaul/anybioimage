"""BioImageViewer - Main anywidget for viewing bioimages with multi-dimensional support."""

import anywidget
import traitlets

from .mixins import (
    AnnotationsMixin,
    ImageLoadingMixin,
    MaskManagementMixin,
    PixelSourceMixin,
    PlateLoadingMixin,
    SAMIntegrationMixin,
)


class BioImageViewer(
    ImageLoadingMixin,
    PixelSourceMixin,
    PlateLoadingMixin,
    MaskManagementMixin,
    AnnotationsMixin,
    SAMIntegrationMixin,
    anywidget.AnyWidget,
):
    """Interactive biological image viewer widget for Jupyter and marimo notebooks.

    Built on anywidget, BioImageViewer supports multi-dimensional images (5D: TCZYX),
    multi-channel composites with per-channel LUT controls, mask overlays, annotation
    tools, SAM integration, and HCS plate navigation.

    Basic usage::

        from anybioimage import BioImageViewer
        import numpy as np

        viewer = BioImageViewer()
        viewer.set_image(np.random.randint(0, 255, (512, 512), dtype=np.uint8))
        viewer  # displays in notebook

    With BioImage for lazy loading::

        from bioio import BioImage
        viewer = BioImageViewer()
        viewer.set_image(BioImage("image.tif"))

    Key public methods:
        - ``set_image(data)`` -- Load a numpy array or BioImage object
        - ``set_plate(path)`` -- Load an HCS OME-Zarr plate
        - ``add_mask(labels, name, color, opacity)`` -- Add a mask overlay layer
        - ``remove_mask(mask_id)`` / ``clear_masks()`` -- Remove mask layers
        - ``enable_sam(model_type)`` -- Enable SAM segmentation

    Key properties:
        - ``rois_df`` -- DataFrame of rectangle annotations
        - ``polygons_df`` -- DataFrame of polygon annotations
        - ``points_df`` -- DataFrame of point annotations

    Observable traitlets (sync=True):
        - ``current_t``, ``current_z`` -- Current time/Z position
        - ``tool_mode`` -- Active annotation tool ('pan', 'select', 'draw', 'polygon', 'point')
        - ``dim_t``, ``dim_c``, ``dim_z`` -- Image dimension sizes
        - ``width``, ``height`` -- Image pixel dimensions

    The widget is composed of several mixins that can be extended independently:
        - ``ImageLoadingMixin`` -- Image loading, caching, and tile-based rendering
        - ``MaskManagementMixin`` -- Mask overlay layer management
        - ``AnnotationsMixin`` -- Annotation tools (rectangles, polygons, points)
        - ``PlateLoadingMixin`` -- HCS OME-Zarr plate navigation
        - ``SAMIntegrationMixin`` -- Segment Anything Model integration
    """

    # Image data
    image_data = traitlets.Unicode("").tag(sync=True)

    # Multiple mask layers: [{id, name, data, visible, opacity, color, contours}]
    _masks_data = traitlets.List(traitlets.Dict()).tag(sync=True)

    # Layer controls
    image_visible = traitlets.Bool(True).tag(sync=True)
    image_brightness = traitlets.Float(0.0).tag(sync=True)  # -1.0 to 1.0
    image_contrast = traitlets.Float(0.0).tag(sync=True)    # -1.0 to 1.0

    # Image dimensions
    width = traitlets.Int(0).tag(sync=True)
    height = traitlets.Int(0).tag(sync=True)

    # 5D dimension sizes (TCZYX)
    dim_t = traitlets.Int(1).tag(sync=True)
    dim_c = traitlets.Int(1).tag(sync=True)
    dim_z = traitlets.Int(1).tag(sync=True)

    # Current position in each dimension
    current_t = traitlets.Int(0).tag(sync=True)
    current_c = traitlets.Int(0).tag(sync=True)
    current_z = traitlets.Int(0).tag(sync=True)

    # Multi-resolution support
    resolution_levels = traitlets.List(traitlets.Int()).tag(sync=True)
    current_resolution = traitlets.Int(0).tag(sync=True)
    _preview_mode = traitlets.Bool(False).tag(sync=True)  # True when actively scrubbing

    # Scene support
    scenes = traitlets.List(traitlets.Unicode()).tag(sync=True)
    current_scene = traitlets.Unicode("").tag(sync=True)

    # HCS plate support
    plate_wells = traitlets.List(traitlets.Unicode()).tag(sync=True)
    plate_fovs = traitlets.List(traitlets.Unicode()).tag(sync=True)
    current_well = traitlets.Unicode("").tag(sync=True)
    current_fov = traitlets.Unicode("").tag(sync=True)

    # Channel settings for composite view: [{name, color, visible, min, max}]
    # Colors are hex strings, min/max are 0-1 normalized contrast limits
    _channel_settings = traitlets.List(traitlets.Dict()).tag(sync=True)

    # Tool mode
    tool_mode = traitlets.Unicode("pan").tag(sync=True)

    # Annotations
    _rois_data = traitlets.List(traitlets.Dict()).tag(sync=True)
    rois_visible = traitlets.Bool(True).tag(sync=True)
    roi_color = traitlets.Unicode("#ff0000").tag(sync=True)

    _polygons_data = traitlets.List(traitlets.Dict()).tag(sync=True)
    polygons_visible = traitlets.Bool(True).tag(sync=True)
    polygon_color = traitlets.Unicode("#00ff00").tag(sync=True)

    _points_data = traitlets.List(traitlets.Dict()).tag(sync=True)
    points_visible = traitlets.Bool(True).tag(sync=True)
    point_color = traitlets.Unicode("#0066ff").tag(sync=True)
    point_radius = traitlets.Int(5).tag(sync=True)

    # Selection
    selected_annotation_id = traitlets.Unicode("").tag(sync=True)
    selected_annotation_type = traitlets.Unicode("").tag(sync=True)

    # SAM label deletion - set coordinates to delete SAM label at that position
    _delete_sam_at = traitlets.Dict(allow_none=True).tag(sync=True)

    # Viewer layout
    canvas_height = traitlets.Int(800).tag(sync=True)

    # Tile-based loading (Canvas2D legacy — kept for backward compat until Task 18)
    _tile_size = traitlets.Int(256).tag(sync=True)
    _tile_request = traitlets.Dict(allow_none=True).tag(sync=True)
    _tiles_data = traitlets.Dict({}).tag(sync=True)
    _use_tile_mode = traitlets.Bool(False).tag(sync=True)  # Set by JS when tile mode is active
    _cache_progress = traitlets.Float(0.0).tag(sync=True)  # 0.0–1.0 background cache fill progress

    # Auto-contrast request/response
    _auto_contrast_request = traitlets.Dict(allow_none=True).tag(sync=True)
    _auto_contrast_result = traitlets.Dict(allow_none=True).tag(sync=True)

    # Histogram request/response
    _histogram_request = traitlets.Dict(allow_none=True).tag(sync=True)
    _histogram_data = traitlets.Dict(allow_none=True).tag(sync=True)

    # Rendering backend — set at construction, not swappable mid-session.
    _render_backend = traitlets.Unicode("canvas2d").tag(sync=True)

    # Viv backend state (all sync=True so JS sees changes).
    _zarr_source = traitlets.Dict({}).tag(sync=True)
    # Pixel-intensity readout from JS hover; None when pointer is outside the canvas.
    _pixel_info = traitlets.Dict(allow_none=True, default_value=None).tag(sync=True)

    # NEW traitlets for unified pipeline
    _pixel_source_mode = traitlets.Unicode("none").tag(sync=True)   # "none"|"zarr"|"chunk_bridge"
    _image_shape = traitlets.Dict(allow_none=True, default_value=None).tag(sync=True)
    _image_dtype = traitlets.Unicode("Uint16").tag(sync=True)
    _display_mode = traitlets.Unicode("composite").tag(sync=True)   # "composite"|"single"
    pixel_size_um = traitlets.Float(allow_none=True, default_value=None).tag(sync=True)
    scale_bar_visible = traitlets.Bool(True).tag(sync=True)

    def __init__(self, *, render_backend: str = "canvas2d", **kwargs):
        super().__init__(**kwargs)
        self._mask_arrays = {}  # Store raw label arrays by mask id
        self._mask_caches = {}  # Cache rendered versions by mask id
        self._plate_path = None  # HCS plate zarr path
        self._plate_store = None
        self._plate_metadata = None
        self._plate_well_paths = []
        self._current_well_path = None
        self._current_well_fov_paths = []

        # Observer for SAM label deletion
        self.observe(self._on_delete_sam_at, names=["_delete_sam_at"])

        # Observers for plate navigation
        self.observe(self._on_well_change, names=["current_well"])
        self.observe(self._on_fov_change, names=["current_fov"])

        from .backends import get_backend_esm
        self._render_backend = render_backend
        self._esm = get_backend_esm(render_backend)

        self.on_msg(self._route_message)

    def _send_chunk_response(self, msg: dict, buffers) -> None:
        """Override of PixelSourceMixin transport hook — uses anywidget's send()."""
        self.send(msg, buffers)

    def _route_message(self, widget, content, buffers):
        """Dispatch custom JS → Py messages by `kind` key."""
        if not isinstance(content, dict):
            return
        kind = content.get("kind")
        if kind == "chunk":
            self.handle_chunk_request(content)

    def close(self):
        """Clean up resources when the widget is closed."""
        super().close()

    # _esm is assigned per-instance in __init__ based on render_backend.
    # See anybioimage.backends for the registry.

    _css = """
    .bioimage-viewer {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        background: #f8f9fa;
        border-radius: 8px;
        overflow: hidden;
        outline: none;
    }
    .bioimage-viewer:focus {
        box-shadow: 0 0 0 2px #0d6efd33;
    }
    .toolbar {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        background: #ffffff;
        border-bottom: 1px solid #e0e0e0;
    }
    .tool-group {
        display: flex;
        gap: 2px;
    }
    .toolbar-separator {
        width: 1px;
        height: 24px;
        background: #e0e0e0;
        margin: 0 4px;
    }
    .tool-btn {
        width: 32px;
        height: 32px;
        padding: 6px;
        border: none;
        border-radius: 6px;
        background: transparent;
        color: #555;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.15s ease;
    }
    .tool-btn:hover {
        background: #f0f0f0;
        color: #333;
    }
    .tool-btn.active {
        background: #0d6efd;
        color: white;
    }
    .tool-btn.danger:hover {
        background: #dc3545;
        color: white;
    }
    .tool-btn svg {
        width: 18px;
        height: 18px;
    }
    .layers-group {
        margin-left: auto;
    }
    .layers-btn {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        border: 1px solid #e0e0e0;
        border-radius: 6px;
        background: #fff;
        color: #555;
        cursor: pointer;
        font-size: 13px;
    }
    .layers-btn:hover {
        background: #f8f8f8;
    }
    .layers-btn svg {
        width: 16px;
        height: 16px;
    }
    .content-area {
        display: flex;
        flex-direction: row;
    }
    .layers-panel {
        width: 0;
        overflow: hidden;
        background: #fff;
        border-left: 1px solid #e0e0e0;
        transition: width 0.15s ease;
        overflow-y: auto;
        padding: 0;
    }
    .layers-panel.open {
        width: 260px;
        padding: 8px 0;
    }
    .layer-header {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px;
        font-size: 11px;
        font-weight: 600;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .layer-header svg {
        width: 14px;
        height: 14px;
    }
    .layer-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        font-size: 13px;
        color: #333;
    }
    .layer-item:hover {
        background: #f8f9fa;
    }
    .layer-item.sub-item {
        padding-left: 44px;
        padding-top: 4px;
        padding-bottom: 4px;
    }
    .layer-item.mask-layer {
        background: #f8f9fa;
    }
    .mask-name {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .mask-actions {
        display: flex;
        align-items: center;
        gap: 4px;
    }
    .layer-action-btn {
        width: 24px;
        height: 24px;
        padding: 4px;
        border: none;
        border-radius: 4px;
        background: transparent;
        color: #666;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.15s ease;
    }
    .layer-action-btn:hover {
        background: #e0e0e0;
        color: #333;
    }
    .layer-action-btn svg {
        width: 14px;
        height: 14px;
    }
    .layer-toggle {
        width: 24px;
        height: 24px;
        padding: 4px;
        border: none;
        border-radius: 4px;
        background: transparent;
        color: #999;
        cursor: pointer;
    }
    .layer-toggle.visible {
        color: #0d6efd;
    }
    .layer-toggle svg {
        width: 16px;
        height: 16px;
    }
    .layer-divider {
        height: 1px;
        background: #e0e0e0;
        margin: 8px 0;
    }
    .color-swatch {
        width: 24px;
        height: 24px;
        padding: 0;
        border: 1px solid #ccc;
        border-radius: 4px;
        cursor: pointer;
        flex-shrink: 0;
    }
    .opacity-item {
        flex-direction: column;
        align-items: stretch;
        gap: 4px;
    }
    .opacity-item input[type="range"] {
        width: 100%;
        height: 6px;
        border-radius: 3px;
        -webkit-appearance: none;
        background: #e0e0e0;
        cursor: pointer;
    }
    .opacity-item input[type="range"]::-webkit-slider-thumb {
        -webkit-appearance: none;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: #0d6efd;
        cursor: pointer;
        border: 2px solid #fff;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        margin-top: -6px;
    }
    .slider-item {
        flex-direction: column;
        align-items: stretch;
        gap: 6px;
    }
    .slider-label {
        font-size: 11px;
        color: #666;
        font-weight: 500;
    }
    .adjustment-slider {
        width: 100%;
        height: 6px;
        border-radius: 3px;
        -webkit-appearance: none;
        background: linear-gradient(to right, #666 0%, #e0e0e0 50%, #fff 100%);
        cursor: pointer;
    }
    .adjustment-slider::-webkit-slider-thumb {
        -webkit-appearance: none;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: #0d6efd;
        cursor: pointer;
        border: 2px solid #fff;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        margin-top: -6px;
    }
    .adjustment-slider::-moz-range-thumb {
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: #0d6efd;
        cursor: pointer;
        border: 2px solid #fff;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }
    .canvas-wrapper {
        position: relative;
        flex: 1;
        min-width: 0;
        height: 800px;
        overflow: hidden;
    }
    .viewer-canvas {
        display: block;
    }
    .status-bar {
        display: flex;
        gap: 24px;
        padding: 6px 12px;
        background: #f0f0f0;
        border-top: 1px solid #e0e0e0;
        font-size: 12px;
        color: #666;
    }
    .status-item {
        white-space: nowrap;
    }
    .dim-status {
        margin-left: auto;
        font-weight: 500;
    }
    .dimension-controls {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 8px 12px;
        background: #f4f4f4;
        border-top: 1px solid #e0e0e0;
    }
    .dim-slider-wrapper {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .dim-label {
        font-size: 12px;
        font-weight: 600;
        color: #555;
        min-width: 16px;
    }
    .play-btn {
        width: 24px;
        height: 24px;
        border: none;
        border-radius: 4px;
        background: #0d6efd;
        color: white;
        cursor: pointer;
        font-size: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .play-btn:hover {
        background: #0b5ed7;
    }
    .dim-slider {
        width: 100px;
        height: 6px;
        border-radius: 3px;
        -webkit-appearance: none;
        background: #ddd;
        cursor: pointer;
    }
    .dim-slider::-webkit-slider-thumb {
        -webkit-appearance: none;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: #0d6efd;
        cursor: pointer;
        border: 2px solid #fff;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
        margin-top: -6px;
    }
    .dim-slider::-moz-range-thumb {
        width: 18px;
        height: 18px;
        border-radius: 50%;
        background: #0d6efd;
        cursor: pointer;
        border: 2px solid #fff;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }
    .dim-value {
        font-size: 11px;
        color: #666;
        min-width: 40px;
    }
    .scene-selector-wrapper {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .scene-select {
        padding: 4px 8px;
        font-size: 12px;
        border: 1px solid #ccc;
        border-radius: 4px;
        background: white;
        cursor: pointer;
    }
    .channel-layer-item {
        padding-left: 24px;
    }
    .channel-layer-item .channel-dot {
        width: 10px;
        height: 10px;
        border-radius: 2px;
        border: 1px solid rgba(0,0,0,0.2);
        flex-shrink: 0;
    }
    .channel-layer-item .channel-name {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-size: 12px;
    }
    .channel-contrast-row {
        padding-left: 52px;
    }
    .channel-contrast-row .slider-label {
        min-width: 28px;
    }
    .slider-value {
        font-size: 10px;
        color: #666;
        min-width: 32px;
        text-align: right;
    }
    .auto-contrast-btn {
        padding: 2px 8px;
        font-size: 11px;
        border: 1px solid #ccc;
        border-radius: 4px;
        background: #f8f8f8;
        color: #555;
        cursor: pointer;
        white-space: nowrap;
        margin-left: auto;
    }
    .auto-contrast-btn:hover {
        background: #e8e8e8;
        border-color: #999;
    }
    .histogram-canvas {
        flex: 1;
        min-width: 0;
        height: 40px;
        border-radius: 4px;
        background: #f8f8f8;
    }

    @media (prefers-color-scheme: dark) {
        .bioimage-viewer {
            background: #1e1e1e;
        }
        .toolbar {
            background: #2d2d2d;
            border-color: #404040;
        }
        .toolbar-separator {
            background: #404040;
        }
        .tool-btn {
            color: #aaa;
        }
        .tool-btn:hover {
            background: #3d3d3d;
            color: #fff;
        }
        .tool-btn.active {
            background: #0d6efd;
            color: white;
        }
        .layers-btn {
            background: #2d2d2d;
            border-color: #404040;
            color: #aaa;
        }
        .layers-btn:hover {
            background: #3d3d3d;
        }
        .layers-panel {
            background: #2d2d2d;
            border-color: #404040;
        }
        .auto-contrast-btn {
            background: #3d3d3d;
            border-color: #555;
            color: #aaa;
        }
        .auto-contrast-btn:hover {
            background: #4d4d4d;
            border-color: #777;
        }
        .histogram-canvas {
            background: #333;
        }
        .layer-header {
            color: #888;
        }
        .layer-item {
            color: #e0e0e0;
        }
        .layer-item:hover {
            background: #3d3d3d;
        }
        .layer-item.mask-layer {
            background: #353535;
        }
        .layer-toggle {
            color: #666;
        }
        .layer-toggle.visible {
            color: #0d6efd;
        }
        .layer-action-btn {
            color: #888;
        }
        .layer-action-btn:hover {
            background: #404040;
            color: #fff;
        }
        .layer-divider {
            background: #404040;
        }
        .status-bar {
            background: #252525;
            border-color: #404040;
            color: #888;
        }
        .opacity-item input[type="range"] {
            background: #404040;
        }
        .slider-label {
            color: #888;
        }
        .adjustment-slider {
            background: linear-gradient(to right, #333 0%, #666 50%, #999 100%);
        }
        .dimension-controls {
            background: #252525;
            border-color: #404040;
        }
        .dim-label {
            color: #aaa;
        }
        .dim-slider {
            background: #404040;
        }
        .dim-value {
            color: #888;
        }
        .scene-select {
            background: #333;
            border-color: #555;
            color: #eee;
        }
        .channel-layer-item .channel-dot {
            border-color: rgba(255,255,255,0.2);
        }
        .channel-layer-item .channel-name {
            color: #bbb;
        }
        .slider-value {
            color: #aaa;
        }
    }
    """
