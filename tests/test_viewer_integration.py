"""Integration tests for BioImageViewer end-to-end workflows."""

import base64
from io import BytesIO

import numpy as np
from PIL import Image

from anybioimage import BioImageViewer


class TestViewerWorkflow:
    """Test complete viewer workflows."""

    def test_load_image_then_add_mask(self):
        viewer = BioImageViewer()
        image = np.random.randint(0, 255, (64, 64), dtype=np.uint8)
        viewer.set_image(image)

        labels = np.zeros((64, 64), dtype=np.int32)
        labels[10:30, 10:30] = 1
        mask_id = viewer.add_mask(labels, name="Nuclei", color="#ff0000", opacity=0.5)

        assert viewer.width == 64
        assert viewer.height == 64
        assert mask_id in viewer.get_mask_ids()

    def test_load_image_add_masks_then_clear(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))

        viewer.add_mask(np.ones((32, 32), dtype=np.int32), name="M1")
        viewer.add_mask(np.ones((32, 32), dtype=np.int32) * 2, name="M2")
        viewer.add_mask(np.ones((32, 32), dtype=np.int32) * 3, name="M3")
        assert len(viewer.get_mask_ids()) == 3

        viewer.clear_masks()
        assert len(viewer.get_mask_ids()) == 0

    def test_replace_image_preserves_clean_state(self):
        """Replacing image should update dimensions and generate new display."""
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 64), dtype=np.uint8))
        assert viewer.width == 64
        data1 = viewer.image_data

        viewer.set_image(np.ones((128, 256), dtype=np.uint8) * 128)
        assert viewer.width == 256
        assert viewer.height == 128
        assert viewer.image_data != data1

    def test_image_to_masks_to_annotations(self):
        """Full workflow: image → masks → annotations."""
        viewer = BioImageViewer()
        viewer.set_image(np.random.randint(0, 255, (64, 64), dtype=np.uint8))

        # Add mask
        labels = np.zeros((64, 64), dtype=np.int32)
        labels[10:30, 10:30] = 1
        viewer.add_mask(labels, name="Seg")

        # Add annotations
        viewer._rois_data = [{"id": "r1", "x": 10, "y": 10, "width": 20, "height": 20}]
        viewer._points_data = [{"id": "pt1", "x": 15, "y": 15}]
        viewer._polygons_data = [{"id": "pg1", "points": [
            {"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 10, "y": 10}
        ]}]

        # Verify all data accessible
        assert len(viewer.get_mask_ids()) == 1
        assert len(viewer.rois_df) == 1
        assert len(viewer.points_df) == 1
        assert len(viewer.polygons_df) == 1
        assert viewer.polygons_df.iloc[0]["num_vertices"] == 3

        # Clear everything
        viewer.clear_masks()
        viewer.clear_all_annotations()
        assert len(viewer.get_mask_ids()) == 0
        assert len(viewer.rois_df) == 0


class TestChannelSettings:
    """Test channel settings behavior."""

    def test_default_channel_settings(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        settings = viewer._channel_settings
        assert len(settings) == 1
        assert settings[0]["visible"] is True
        assert settings[0]["min"] == 0.0
        assert settings[0]["max"] == 1.0

    def test_channel_settings_update_color(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        settings = list(viewer._channel_settings)
        settings[0] = {**settings[0], "color": "#0000ff"}
        viewer._channel_settings = settings
        assert viewer._channel_settings[0]["color"] == "#0000ff"

    def test_channel_settings_reflect_data_range(self):
        """Data range should match actual array min/max."""
        viewer = BioImageViewer()
        arr = np.array([[50, 200]], dtype=np.uint8).reshape(1, 2)
        viewer.set_image(arr)
        assert viewer._channel_settings[0]["data_min"] == 50.0
        assert viewer._channel_settings[0]["data_max"] == 200.0


class TestToolMode:
    """Test tool mode traitlet."""

    def test_default_tool_mode(self):
        viewer = BioImageViewer()
        assert viewer.tool_mode == "pan"

    def test_set_tool_mode(self):
        viewer = BioImageViewer()
        viewer.tool_mode = "draw"
        assert viewer.tool_mode == "draw"

    def test_all_tool_modes(self):
        viewer = BioImageViewer()
        for mode in ["pan", "select", "draw", "polygon", "point"]:
            viewer.tool_mode = mode
            assert viewer.tool_mode == mode


class TestDimensionTraitlets:
    """Test dimension-related traitlets."""

    def test_canvas_height_default(self):
        viewer = BioImageViewer()
        assert viewer.canvas_height == 800

    def test_canvas_height_custom(self):
        viewer = BioImageViewer(canvas_height=600)
        assert viewer.canvas_height == 600

    def test_tile_size_default(self):
        viewer = BioImageViewer()
        assert viewer._tile_size == 256

    def test_use_jpeg_tiles_default(self):
        viewer = BioImageViewer()
        assert viewer.use_jpeg_tiles is False

    def test_dimensions_after_set_image(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((100, 200), dtype=np.uint8))
        assert viewer.dim_t == 1
        assert viewer.dim_c == 1
        assert viewer.dim_z == 1
        assert viewer.current_t == 0
        assert viewer.current_z == 0


class TestImageDataOutput:
    """Test that image_data contains valid base64 PNG."""

    def test_image_data_is_valid_png(self):
        viewer = BioImageViewer()
        arr = np.random.randint(0, 255, (32, 32), dtype=np.uint8)
        viewer.set_image(arr)
        # Decode base64 and verify it's a valid PNG
        img = Image.open(BytesIO(base64.b64decode(viewer.image_data)))
        assert img.size == (32, 32)

    def test_white_image_not_all_black(self):
        """Non-zero image data should produce non-black display."""
        viewer = BioImageViewer()
        arr = np.full((8, 8), 255, dtype=np.uint8)
        viewer.set_image(arr)
        img = Image.open(BytesIO(base64.b64decode(viewer.image_data)))
        pixels = np.array(img)
        assert pixels.max() == 255  # Should have white pixels

    def test_gradient_image_has_range(self):
        """Gradient image should produce output with tonal range."""
        viewer = BioImageViewer()
        arr = np.arange(256, dtype=np.uint8).reshape(16, 16)
        viewer.set_image(arr)
        img = Image.open(BytesIO(base64.b64decode(viewer.image_data)))
        pixels = np.array(img)
        assert pixels.min() == 0
        assert pixels.max() == 255

    def test_uint16_gradient_normalizes_to_full_range(self):
        """uint16 data should normalize to fill 0-255 range."""
        viewer = BioImageViewer()
        arr = np.array([[0, 32768, 65535]], dtype=np.uint16).reshape(1, 3)
        viewer.set_image(arr)
        img = Image.open(BytesIO(base64.b64decode(viewer.image_data)))
        pixels = np.array(img)
        assert pixels[0, 0] == 0
        assert pixels[0, 2] == 255


class TestMaskContourIntegration:
    """Test mask contour rendering end-to-end."""

    def test_filled_mask_has_opaque_interior(self):
        """Filled mask should have opaque interior pixels."""
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        labels = np.zeros((32, 32), dtype=np.int32)
        labels[8:24, 8:24] = 1
        mask_id = viewer.add_mask(labels, contours_only=False)

        # Decode mask data and check
        mask = [m for m in viewer._masks_data if m["id"] == mask_id][0]
        img = Image.open(BytesIO(base64.b64decode(mask["data"])))
        rgba = np.array(img)
        # Interior should be opaque
        assert rgba[16, 16, 3] == 255
        # Exterior should be transparent
        assert rgba[0, 0, 3] == 0

    def test_contour_mask_has_transparent_interior(self):
        """Contour mask should have transparent interior."""
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        labels = np.zeros((32, 32), dtype=np.int32)
        labels[8:24, 8:24] = 1
        mask_id = viewer.add_mask(labels, contours_only=True, contour_width=1)

        mask = [m for m in viewer._masks_data if m["id"] == mask_id][0]
        img = Image.open(BytesIO(base64.b64decode(mask["data"])))
        rgba = np.array(img)
        # Interior should be transparent (eroded away)
        assert rgba[16, 16, 3] == 0
        # Boundary should be opaque
        assert rgba[8, 8, 3] == 255


class TestAnnotationDataFrameEdgeCases:
    """Test annotation DataFrame edge cases."""

    def test_rois_df_with_extra_columns(self):
        """Extra columns in ROI data should be preserved."""
        viewer = BioImageViewer()
        viewer._rois_data = [
            {"id": "r1", "x": 10, "y": 20, "width": 30, "height": 40, "label": "cell"}
        ]
        df = viewer.rois_df
        assert "label" in df.columns
        assert df.iloc[0]["label"] == "cell"

    def test_polygons_df_roundtrip(self):
        """Polygon data survives get → set round-trip."""
        viewer = BioImageViewer()
        points = [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 10, "y": 10}, {"x": 0, "y": 10}]
        viewer._polygons_data = [{"id": "p1", "points": points}]

        df = viewer.polygons_df
        assert df.iloc[0]["num_vertices"] == 4

        # Set back (only keeps id + points)
        viewer.polygons_df = df[["id", "points"]]
        assert len(viewer._polygons_data) == 1
        assert len(viewer._polygons_data[0]["points"]) == 4

    def test_empty_annotation_clearing(self):
        """Clearing already-empty annotations should not error."""
        viewer = BioImageViewer()
        viewer.clear_all_annotations()  # Should not raise
        assert viewer._rois_data == []
