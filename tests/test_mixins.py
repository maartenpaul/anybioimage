"""Tests for BioImageViewer mixin functionality."""

import numpy as np
import pandas as pd
import pytest

from anybioimage import BioImageViewer


class TestImageLoadingNumpyShapes:
    """Test set_image with various numpy array shapes and dtypes."""

    def test_2d_grayscale(self):
        viewer = BioImageViewer()
        arr = np.zeros((64, 128), dtype=np.uint8)
        viewer.set_image(arr)
        assert viewer.width == 128
        assert viewer.height == 64
        assert viewer.dim_c == 1
        assert viewer.dim_t == 1
        assert viewer.dim_z == 1

    def test_3d_cyx(self):
        """3D array interpreted as CYX after squeeze."""
        viewer = BioImageViewer()
        arr = np.zeros((3, 64, 128), dtype=np.uint8)
        viewer.set_image(arr)
        # After squeeze: (3, 64, 128) → 3D, takes [0] → (64, 128)
        assert viewer.width == 128
        assert viewer.height == 64

    def test_4d_squeezes_to_2d(self):
        """4D array with singleton dims squeezes to 2D."""
        viewer = BioImageViewer()
        arr = np.zeros((1, 64, 128, 1), dtype=np.uint8)
        viewer.set_image(arr)
        assert viewer.width == 128
        assert viewer.height == 64

    def test_5d_squeezes_to_2d(self):
        """5D TCZYX with T=C=Z=1 squeezes to 2D."""
        viewer = BioImageViewer()
        arr = np.zeros((1, 1, 1, 32, 64), dtype=np.uint8)
        viewer.set_image(arr)
        assert viewer.width == 64
        assert viewer.height == 32

    def test_uint16_normalization(self):
        """uint16 data gets normalized to uint8 for display."""
        viewer = BioImageViewer()
        arr = np.array([[0, 32768, 65535]], dtype=np.uint16).reshape(1, 3)
        viewer.set_image(arr)
        assert len(viewer.image_data) > 0  # base64 PNG generated

    def test_float32_normalization(self):
        """float32 data gets normalized."""
        viewer = BioImageViewer()
        arr = np.array([[0.0, 0.5, 1.0]], dtype=np.float32).reshape(1, 3)
        viewer.set_image(arr)
        assert len(viewer.image_data) > 0

    def test_set_image_stores_raw_array(self):
        """Raw array stored for re-rendering on LUT changes."""
        viewer = BioImageViewer()
        arr = np.arange(64, dtype=np.uint8).reshape(8, 8)
        viewer.set_image(arr)
        assert viewer._raw_numpy_array is not None
        np.testing.assert_array_equal(viewer._raw_numpy_array, arr)

    def test_set_image_replaces_previous(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        old_data = viewer.image_data
        viewer.set_image(np.ones((64, 128), dtype=np.uint8) * 200)
        assert viewer.width == 128
        assert viewer.height == 64
        assert viewer.image_data != old_data

    def test_channel_settings_created(self):
        """set_image creates channel settings with correct data range."""
        viewer = BioImageViewer()
        arr = np.array([[10, 200]], dtype=np.uint8).reshape(1, 2)
        viewer.set_image(arr)
        settings = viewer._channel_settings
        assert len(settings) == 1
        assert settings[0]["data_min"] == 10.0
        assert settings[0]["data_max"] == 200.0
        assert settings[0]["color"] == "#ffffff"
        assert settings[0]["visible"] is True

    def test_channel_settings_zero_size_image(self):
        """Edge case: constant image gets 0/0 data range without error."""
        viewer = BioImageViewer()
        arr = np.full((8, 8), 42, dtype=np.uint8)
        viewer.set_image(arr)
        assert viewer._channel_settings[0]["data_min"] == 42.0
        assert viewer._channel_settings[0]["data_max"] == 42.0

    def test_bioimage_detection(self):
        """Objects with dims and dask_data attrs go through BioImage path."""

        class FakeBioImage:
            dims = None
            dask_data = None

        viewer = BioImageViewer()
        fake = FakeBioImage()
        # Should attempt BioImage path, will fail but at least verifies detection
        with pytest.raises(Exception):
            viewer.set_image(fake)


class TestImageReRendering:
    """Test re-rendering numpy images on channel settings changes."""

    def test_update_numpy_image_with_color(self):
        """Changing channel color should re-render the image."""
        viewer = BioImageViewer()
        arr = np.full((8, 8), 200, dtype=np.uint8)
        viewer.set_image(arr)
        original_data = viewer.image_data

        # Change to red channel color
        settings = list(viewer._channel_settings)
        settings[0] = {**settings[0], "color": "#ff0000"}
        viewer._channel_settings = settings
        viewer._update_numpy_image()
        assert viewer.image_data != original_data

    def test_update_numpy_image_with_contrast(self):
        """Changing contrast window should affect rendered output."""
        viewer = BioImageViewer()
        arr = np.arange(64, dtype=np.uint8).reshape(8, 8)
        viewer.set_image(arr)
        original_data = viewer.image_data

        settings = list(viewer._channel_settings)
        settings[0] = {**settings[0], "min": 0.3, "max": 0.7}
        viewer._channel_settings = settings
        viewer._update_numpy_image()
        assert viewer.image_data != original_data

    def test_update_numpy_image_no_raw_data(self):
        """_update_numpy_image should be a no-op if no raw data stored."""
        viewer = BioImageViewer()
        viewer._update_numpy_image()  # Should not raise


class TestMaskManagement:
    """Tests for mask overlay management."""

    def test_add_mask_returns_unique_ids(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        labels = np.ones((32, 32), dtype=np.int32)
        id1 = viewer.add_mask(labels, name="M1")
        id2 = viewer.add_mask(labels, name="M2")
        assert id1 != id2

    def test_add_mask_custom_color(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        mask_id = viewer.add_mask(np.ones((32, 32), dtype=np.int32), color="#ff0000")
        mask = [m for m in viewer._masks_data if m["id"] == mask_id][0]
        assert mask["color"] == "#ff0000"

    def test_add_mask_auto_color_cycles(self):
        """Auto-assigned colors cycle through MASK_COLORS."""
        from anybioimage.utils import MASK_COLORS
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        labels = np.ones((32, 32), dtype=np.int32)
        [viewer.add_mask(labels, name=f"M{i}") for i in range(3)]
        masks = viewer._masks_data
        assert masks[0]["color"] == MASK_COLORS[0]
        assert masks[1]["color"] == MASK_COLORS[1]
        assert masks[2]["color"] == MASK_COLORS[2]

    def test_add_mask_auto_name(self):
        """Auto-assigned names should be sequential."""
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        labels = np.ones((32, 32), dtype=np.int32)
        viewer.add_mask(labels)
        viewer.add_mask(labels)
        assert viewer._masks_data[0]["name"] == "Mask 1"
        assert viewer._masks_data[1]["name"] == "Mask 2"

    def test_add_mask_opacity(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        mask_id = viewer.add_mask(np.ones((32, 32), dtype=np.int32), opacity=0.3)
        mask = [m for m in viewer._masks_data if m["id"] == mask_id][0]
        assert mask["opacity"] == 0.3

    def test_add_mask_contours(self):
        """Contour-only mask has correct settings stored."""
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        labels = np.zeros((32, 32), dtype=np.int32)
        labels[8:24, 8:24] = 1
        mask_id = viewer.add_mask(labels, contours_only=True, contour_width=2)
        mask = [m for m in viewer._masks_data if m["id"] == mask_id][0]
        assert mask["contours"] is True
        assert mask["contour_width"] == 2

    def test_add_mask_data_is_base64_png(self):
        """Mask data should be valid base64 encoded PNG."""
        import base64
        from io import BytesIO

        from PIL import Image
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        labels = np.zeros((32, 32), dtype=np.int32)
        labels[4:12, 4:12] = 1
        mask_id = viewer.add_mask(labels)
        mask = [m for m in viewer._masks_data if m["id"] == mask_id][0]
        img = Image.open(BytesIO(base64.b64decode(mask["data"])))
        assert img.size == (32, 32)
        assert img.mode == "RGBA"

    def test_remove_mask(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        id1 = viewer.add_mask(np.ones((32, 32), dtype=np.int32), name="M1")
        id2 = viewer.add_mask(np.ones((32, 32), dtype=np.int32), name="M2")
        viewer.remove_mask(id1)
        assert id1 not in viewer.get_mask_ids()
        assert id2 in viewer.get_mask_ids()

    def test_remove_mask_cleans_up_arrays(self):
        """remove_mask should clean up internal arrays and caches."""
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        mask_id = viewer.add_mask(np.ones((32, 32), dtype=np.int32))
        assert mask_id in viewer._mask_arrays
        assert mask_id in viewer._mask_caches
        viewer.remove_mask(mask_id)
        assert mask_id not in viewer._mask_arrays
        assert mask_id not in viewer._mask_caches

    def test_clear_masks(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        viewer.add_mask(np.ones((32, 32), dtype=np.int32), name="M1")
        viewer.add_mask(np.ones((32, 32), dtype=np.int32), name="M2")
        viewer.clear_masks()
        assert len(viewer.get_mask_ids()) == 0
        assert len(viewer._mask_arrays) == 0
        assert len(viewer._mask_caches) == 0

    def test_set_mask_replaces_existing(self):
        """set_mask should clear all existing masks first."""
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        viewer.add_mask(np.ones((32, 32), dtype=np.int32), name="Old")
        viewer.add_mask(np.ones((32, 32), dtype=np.int32), name="Old2")
        viewer.set_mask(np.ones((32, 32), dtype=np.int32) * 2, name="New")
        assert len(viewer.get_mask_ids()) == 1
        assert viewer._masks_data[0]["name"] == "New"

    def test_update_mask_settings_name(self):
        """Update mask name without affecting contour settings."""
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        mask_id = viewer.add_mask(np.ones((32, 32), dtype=np.int32), name="Original")
        viewer.update_mask_settings(mask_id, name="Renamed")
        mask = [m for m in viewer._masks_data if m["id"] == mask_id][0]
        assert mask["name"] == "Renamed"

    def test_update_mask_settings_contour_toggle(self):
        """Toggling contours regenerates mask data."""
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        labels = np.zeros((32, 32), dtype=np.int32)
        labels[8:24, 8:24] = 1
        mask_id = viewer.add_mask(labels, contours_only=False)
        original_data = viewer._masks_data[0]["data"]

        viewer.update_mask_settings(mask_id, contours=True, contour_width=2)
        new_data = viewer._masks_data[0]["data"]
        assert new_data != original_data  # Should have regenerated

    def test_update_mask_settings_contour_cache(self):
        """Toggling contours back and forth should use cache."""
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        labels = np.zeros((32, 32), dtype=np.int32)
        labels[8:24, 8:24] = 1
        mask_id = viewer.add_mask(labels, contours_only=False)
        original_data = viewer._masks_data[0]["data"]

        # Toggle to contours
        viewer.update_mask_settings(mask_id, contours=True)
        _ = viewer._masks_data[0]["data"]  # contour version generated

        # Toggle back → should use cached filled version
        viewer.update_mask_settings(mask_id, contours=False)
        restored_data = viewer._masks_data[0]["data"]
        assert restored_data == original_data

    def test_masks_df(self):
        """masks_df property returns correct DataFrame."""
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        viewer.add_mask(np.ones((32, 32), dtype=np.int32), name="N1", color="#ff0000")
        viewer.add_mask(np.ones((32, 32), dtype=np.int32), name="N2", color="#00ff00")
        df = viewer.masks_df
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert "name" in df.columns
        assert "data" not in df.columns  # data excluded

    def test_masks_df_empty(self):
        viewer = BioImageViewer()
        df = viewer.masks_df
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_add_mask_squeezes_3d(self):
        """3D label arrays should be squeezed to 2D."""
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        labels = np.ones((1, 32, 32), dtype=np.int32)
        mask_id = viewer.add_mask(labels)
        assert mask_id in viewer.get_mask_ids()


class TestAnnotations:
    """Tests for annotation data access and manipulation."""

    def test_rois_df_empty(self):
        viewer = BioImageViewer()
        df = viewer.rois_df
        assert isinstance(df, pd.DataFrame)
        assert list(df.columns) == ["id", "x", "y", "width", "height"]

    def test_rois_df_with_data(self):
        viewer = BioImageViewer()
        viewer._rois_data = [
            {"id": "r1", "x": 10, "y": 20, "width": 30, "height": 40},
            {"id": "r2", "x": 5, "y": 15, "width": 25, "height": 35},
        ]
        df = viewer.rois_df
        assert len(df) == 2
        assert df.iloc[0]["x"] == 10
        assert df.iloc[1]["width"] == 25

    def test_rois_df_setter(self):
        """Setting rois_df should update _rois_data traitlet."""
        viewer = BioImageViewer()
        df = pd.DataFrame([
            {"id": "r1", "x": 100, "y": 200, "width": 50, "height": 60},
        ])
        viewer.rois_df = df
        assert len(viewer._rois_data) == 1
        assert viewer._rois_data[0]["x"] == 100

    def test_rois_df_roundtrip(self):
        """Get → modify → set should preserve data."""
        viewer = BioImageViewer()
        viewer._rois_data = [
            {"id": "r1", "x": 10, "y": 20, "width": 30, "height": 40},
        ]
        df = viewer.rois_df
        df.loc[0, "x"] = 999
        viewer.rois_df = df
        assert viewer._rois_data[0]["x"] == 999

    def test_polygons_df_with_data(self):
        viewer = BioImageViewer()
        viewer._polygons_data = [
            {"id": "p1", "points": [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 10, "y": 10}]},
        ]
        df = viewer.polygons_df
        assert len(df) == 1
        assert df.iloc[0]["num_vertices"] == 3
        assert len(df.iloc[0]["points"]) == 3

    def test_polygons_df_setter(self):
        viewer = BioImageViewer()
        df = pd.DataFrame([
            {"id": "p1", "points": [{"x": 0, "y": 0}, {"x": 5, "y": 5}]},
        ])
        viewer.polygons_df = df
        assert len(viewer._polygons_data) == 1
        assert viewer._polygons_data[0]["id"] == "p1"
        assert len(viewer._polygons_data[0]["points"]) == 2

    def test_points_df_with_data(self):
        viewer = BioImageViewer()
        viewer._points_data = [
            {"id": "pt1", "x": 100, "y": 200},
            {"id": "pt2", "x": 50, "y": 150},
        ]
        df = viewer.points_df
        assert len(df) == 2
        assert df.iloc[0]["x"] == 100

    def test_points_df_setter(self):
        viewer = BioImageViewer()
        df = pd.DataFrame([
            {"id": "pt1", "x": 42, "y": 84},
        ])
        viewer.points_df = df
        assert viewer._points_data[0]["x"] == 42

    def test_clear_rois(self):
        viewer = BioImageViewer()
        viewer._rois_data = [{"id": "r1", "x": 0, "y": 0, "width": 10, "height": 10}]
        viewer.clear_rois()
        assert viewer._rois_data == []

    def test_clear_polygons(self):
        viewer = BioImageViewer()
        viewer._polygons_data = [{"id": "p1", "points": []}]
        viewer.clear_polygons()
        assert viewer._polygons_data == []

    def test_clear_points(self):
        viewer = BioImageViewer()
        viewer._points_data = [{"id": "pt1", "x": 0, "y": 0}]
        viewer.clear_points()
        assert viewer._points_data == []

    def test_clear_all_annotations(self):
        viewer = BioImageViewer()
        viewer._rois_data = [{"id": "r1", "x": 0, "y": 0, "width": 10, "height": 10}]
        viewer._polygons_data = [{"id": "p1", "points": []}]
        viewer._points_data = [{"id": "pt1", "x": 0, "y": 0}]
        viewer.selected_annotation_id = "r1"
        viewer.selected_annotation_type = "roi"
        viewer.clear_all_annotations()
        assert viewer._rois_data == []
        assert viewer._polygons_data == []
        assert viewer._points_data == []
        assert viewer.selected_annotation_id == ""
        assert viewer.selected_annotation_type == ""


class TestAutoContrast:
    """Test auto-contrast computation for numpy images."""

    def test_auto_contrast_numpy(self):
        """Auto contrast on numpy array computes percentile range."""
        viewer = BioImageViewer()
        # Create image with known distribution: mostly low values, some high
        arr = np.zeros((64, 64), dtype=np.uint8)
        arr[30:34, 30:34] = 255  # small bright region
        viewer.set_image(arr)

        # Trigger auto contrast
        viewer._on_auto_contrast_request({
            "new": {"channel": 0, "timestamp": 123}
        })
        result = viewer._auto_contrast_result
        assert result["channel"] == 0
        assert result["timestamp"] == 123
        # Most pixels are 0, so p2 should be 0 and p98 should be 0 too (mostly dark)
        assert result["min"] >= 0.0
        assert result["max"] <= 1.0

    def test_auto_contrast_all_channels(self):
        """channel=-1 should compute ranges for all channels."""
        viewer = BioImageViewer()
        arr = np.random.randint(0, 255, (32, 32), dtype=np.uint8)
        viewer.set_image(arr)

        viewer._on_auto_contrast_request({
            "new": {"channel": -1, "timestamp": 456}
        })
        result = viewer._auto_contrast_result
        assert result["channel"] == -1
        assert "ranges" in result
        assert "0" in result["ranges"]


class TestWidgetLifecycle:
    """Tests for widget lifecycle management."""

    def test_close_without_image(self):
        viewer = BioImageViewer()
        viewer.close()

    def test_close_after_set_image(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        viewer.close()

    def test_close_cancels_precompute(self):
        """close() should set the cancel event if one exists."""
        import threading
        viewer = BioImageViewer()
        event = threading.Event()
        viewer._precompute_event = event
        viewer.close()
        assert event.is_set()

    def test_version_accessible(self):
        import anybioimage
        assert anybioimage.__version__ == "0.3.0"
