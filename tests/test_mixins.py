"""Tests for BioImageViewer mixin functionality."""

import numpy as np
import pandas as pd
import pytest

from anybioimage import BioImageViewer
from anybioimage.utils import labels_to_rgba


class TestImageLoadingMixin:
    """Tests for image loading and dimension handling."""

    def test_set_image_2d_grayscale(self):
        viewer = BioImageViewer()
        arr = np.zeros((64, 128), dtype=np.uint8)
        viewer.set_image(arr)
        assert viewer.width == 128
        assert viewer.height == 64
        assert viewer.dim_c == 1
        assert viewer.dim_t == 1
        assert viewer.dim_z == 1

    def test_set_image_3d_array(self):
        viewer = BioImageViewer()
        # 3D numpy arrays are interpreted as CYX (3 channels, 64 height, 128 width)
        arr = np.zeros((3, 64, 128), dtype=np.uint8)
        viewer.set_image(arr)
        assert viewer.width == 128
        assert viewer.height == 64

    def test_set_image_uint16(self):
        viewer = BioImageViewer()
        arr = np.zeros((64, 64), dtype=np.uint16)
        viewer.set_image(arr)
        assert viewer.width == 64
        assert viewer.height == 64

    def test_set_image_float32(self):
        viewer = BioImageViewer()
        arr = np.random.rand(32, 32).astype(np.float32)
        viewer.set_image(arr)
        assert viewer.width == 32
        assert viewer.height == 32

    def test_set_image_generates_image_data(self):
        viewer = BioImageViewer()
        arr = np.random.randint(0, 255, (32, 32), dtype=np.uint8)
        viewer.set_image(arr)
        assert len(viewer.image_data) > 0

    def test_set_image_replaces_previous(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        assert viewer.width == 32
        viewer.set_image(np.zeros((64, 128), dtype=np.uint8))
        assert viewer.width == 128
        assert viewer.height == 64

    def test_current_dimensions_default_zero(self):
        viewer = BioImageViewer()
        assert viewer.current_t == 0
        assert viewer.current_z == 0


class TestMaskManagementMixin:
    """Tests for mask overlay management."""

    def test_add_mask_returns_id(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        labels = np.zeros((32, 32), dtype=np.int32)
        labels[4:12, 4:12] = 1
        mask_id = viewer.add_mask(labels, name="Test")
        assert isinstance(mask_id, str)

    def test_add_mask_with_custom_color(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        labels = np.ones((32, 32), dtype=np.int32)
        mask_id = viewer.add_mask(labels, name="Red", color="#ff0000")
        masks = viewer._masks_data
        matching = [m for m in masks if m["id"] == mask_id]
        assert len(matching) == 1
        assert matching[0]["color"] == "#ff0000"

    def test_add_mask_with_opacity(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        labels = np.ones((32, 32), dtype=np.int32)
        mask_id = viewer.add_mask(labels, name="Translucent", opacity=0.3)
        masks = viewer._masks_data
        matching = [m for m in masks if m["id"] == mask_id]
        assert matching[0]["opacity"] == 0.3

    def test_add_multiple_masks(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        labels1 = np.ones((32, 32), dtype=np.int32)
        labels2 = np.ones((32, 32), dtype=np.int32) * 2
        id1 = viewer.add_mask(labels1, name="Mask1")
        id2 = viewer.add_mask(labels2, name="Mask2")
        assert id1 != id2
        assert len(viewer.get_mask_ids()) == 2

    def test_remove_mask(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        labels = np.ones((32, 32), dtype=np.int32)
        mask_id = viewer.add_mask(labels, name="ToRemove")
        assert mask_id in viewer.get_mask_ids()
        viewer.remove_mask(mask_id)
        assert mask_id not in viewer.get_mask_ids()

    def test_clear_masks(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        viewer.add_mask(np.ones((32, 32), dtype=np.int32), name="M1")
        viewer.add_mask(np.ones((32, 32), dtype=np.int32), name="M2")
        assert len(viewer.get_mask_ids()) == 2
        viewer.clear_masks()
        assert len(viewer.get_mask_ids()) == 0


class TestAnnotationsMixin:
    """Tests for annotation data access."""

    def test_rois_df_empty(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        df = viewer.rois_df
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_polygons_df_empty(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        df = viewer.polygons_df
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_points_df_empty(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        df = viewer.points_df
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_rois_df_with_data(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        viewer._rois_data = [
            {"id": "r1", "x": 10, "y": 20, "width": 30, "height": 40},
            {"id": "r2", "x": 5, "y": 15, "width": 25, "height": 35},
        ]
        df = viewer.rois_df
        assert len(df) == 2
        assert "x" in df.columns
        assert "width" in df.columns

    def test_points_df_with_data(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        viewer._points_data = [
            {"id": "p1", "x": 100, "y": 200},
            {"id": "p2", "x": 50, "y": 150},
        ]
        df = viewer.points_df
        assert len(df) == 2
        assert "x" in df.columns
        assert "y" in df.columns


class TestLabelsToRgba:
    """Tests for the labels_to_rgba utility function."""

    def test_empty_labels(self):
        labels = np.zeros((16, 16), dtype=np.int32)
        rgba = labels_to_rgba(labels)
        assert rgba.shape == (16, 16, 4)
        assert rgba.dtype == np.uint8
        # All transparent for zero labels
        assert np.all(rgba[:, :, 3] == 0)

    def test_single_label(self):
        labels = np.zeros((16, 16), dtype=np.int32)
        labels[4:8, 4:8] = 1
        rgba = labels_to_rgba(labels)
        # Labeled region should be opaque (hash-based color, non-zero alpha)
        assert rgba[5, 5, 3] == 255  # alpha
        # Unlabeled region should be transparent
        assert rgba[0, 0, 3] == 0

    def test_multiple_labels(self):
        labels = np.zeros((16, 16), dtype=np.int32)
        labels[0:4, 0:4] = 1
        labels[8:12, 8:12] = 2
        rgba = labels_to_rgba(labels)
        assert rgba[2, 2, 3] == 255
        assert rgba[10, 10, 3] == 255
        assert rgba[6, 6, 3] == 0


class TestWidgetCleanup:
    """Tests for widget lifecycle management."""

    def test_close_without_image(self):
        viewer = BioImageViewer()
        viewer.close()  # Should not raise

    def test_close_after_set_image(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        viewer.close()  # Should not raise
