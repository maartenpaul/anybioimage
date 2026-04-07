"""Integration tests for BioImageViewer end-to-end workflows."""

import numpy as np
import pytest

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

    def test_load_image_add_multiple_masks_then_clear(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))

        viewer.add_mask(np.ones((32, 32), dtype=np.int32), name="M1")
        viewer.add_mask(np.ones((32, 32), dtype=np.int32) * 2, name="M2")
        viewer.add_mask(np.ones((32, 32), dtype=np.int32) * 3, name="M3")
        assert len(viewer.get_mask_ids()) == 3

        viewer.clear_masks()
        assert len(viewer.get_mask_ids()) == 0

    def test_replace_image_resets_state(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 64), dtype=np.uint8))
        assert viewer.width == 64
        assert viewer.height == 32

        viewer.set_image(np.zeros((128, 256), dtype=np.uint8))
        assert viewer.width == 256
        assert viewer.height == 128


class TestChannelSettings:
    """Test channel settings behavior."""

    def test_default_channel_settings_single_channel(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        settings = viewer._channel_settings
        assert len(settings) == 1

    def test_channel_settings_update(self):
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        settings = list(viewer._channel_settings)
        settings[0] = {**settings[0], "color": "#0000ff"}
        viewer._channel_settings = settings
        assert viewer._channel_settings[0]["color"] == "#0000ff"


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
