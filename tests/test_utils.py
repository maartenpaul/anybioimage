"""Tests for anybioimage utility functions."""

import base64
from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from anybioimage.utils import (
    array_to_base64,
    array_to_fast_png_base64,
    composite_channels,
    hex_to_rgb,
    labels_to_rgba,
    normalize_image,
)


class TestHexToRgb:
    def test_red(self):
        assert hex_to_rgb("#ff0000") == (255, 0, 0)

    def test_green(self):
        assert hex_to_rgb("#00ff00") == (0, 255, 0)

    def test_blue(self):
        assert hex_to_rgb("#0000ff") == (0, 0, 255)

    def test_without_hash(self):
        assert hex_to_rgb("ffffff") == (255, 255, 255)

    def test_black(self):
        assert hex_to_rgb("#000000") == (0, 0, 0)

    def test_mixed(self):
        assert hex_to_rgb("#80c0e0") == (128, 192, 224)


class TestNormalizeImage:
    def test_uint8_passthrough(self):
        arr = np.array([[0, 128, 255]], dtype=np.uint8)
        result = normalize_image(arr)
        np.testing.assert_array_equal(result, arr)

    def test_uint16_to_uint8(self):
        arr = np.array([[0, 32768, 65535]], dtype=np.uint16)
        result = normalize_image(arr)
        assert result.dtype == np.uint8
        assert result[0, 0] == 0
        assert result[0, 2] == 255

    def test_float_array(self):
        arr = np.array([[0.0, 0.5, 1.0]], dtype=np.float32)
        result = normalize_image(arr)
        assert result.dtype == np.uint8
        assert result[0, 0] == 0
        assert result[0, 2] == 255

    def test_constant_array(self):
        arr = np.full((4, 4), 42, dtype=np.uint16)
        result = normalize_image(arr)
        assert result.dtype == np.uint8
        np.testing.assert_array_equal(result, np.zeros((4, 4), dtype=np.uint8))

    def test_global_range(self):
        arr = np.array([[0, 100]], dtype=np.float32)
        result = normalize_image(arr, global_min=0.0, global_max=200.0)
        assert result[0, 0] == 0
        assert result[0, 1] == 127  # 100/200 * 255 ≈ 127

    def test_uint8_with_global_range_does_normalize(self):
        """uint8 with explicit global bounds should NOT skip normalization."""
        arr = np.array([[100]], dtype=np.uint8)
        result = normalize_image(arr, global_min=0.0, global_max=200.0)
        assert result.dtype == np.uint8
        # 100/200 * 255 ≈ 127
        assert result[0, 0] == 127

    def test_negative_float_range(self):
        """Negative values should normalize correctly."""
        arr = np.array([[-100.0, 0.0, 100.0]], dtype=np.float32)
        result = normalize_image(arr)
        assert result[0, 0] == 0
        assert result[0, 2] == 255
        # midpoint should be ~127
        assert 126 <= result[0, 1] <= 128

    def test_identical_global_bounds(self):
        """When global_min == global_max, output should be zeros."""
        arr = np.array([[50, 100, 150]], dtype=np.float32)
        result = normalize_image(arr, global_min=10.0, global_max=10.0)
        np.testing.assert_array_equal(result, np.zeros_like(result))

    def test_single_pixel(self):
        arr = np.array([[42]], dtype=np.uint16)
        result = normalize_image(arr)
        assert result.shape == (1, 1)
        assert result.dtype == np.uint8

    def test_large_uint16_range(self):
        """Full uint16 dynamic range."""
        arr = np.array([[0, 65535]], dtype=np.uint16)
        result = normalize_image(arr)
        assert result[0, 0] == 0
        assert result[0, 1] == 255


class TestArrayToBase64:
    def test_grayscale(self):
        arr = np.zeros((8, 8), dtype=np.uint8)
        result = array_to_base64(arr)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_rgb(self):
        arr = np.zeros((8, 8, 3), dtype=np.uint8)
        result = array_to_base64(arr)
        assert isinstance(result, str)

    def test_rgba(self):
        arr = np.zeros((8, 8, 4), dtype=np.uint8)
        result = array_to_base64(arr)
        assert isinstance(result, str)

    def test_unsupported_shape_raises(self):
        arr = np.zeros((8, 8, 2), dtype=np.uint8)
        with pytest.raises(ValueError):
            array_to_base64(arr)

    def test_single_pixel_rgb(self):
        """1x1 RGB image should encode correctly."""
        arr = np.array([[[255, 0, 0]]], dtype=np.uint8)
        result = array_to_base64(arr)
        # Decode and verify
        img = Image.open(BytesIO(base64.b64decode(result)))
        assert img.size == (1, 1)
        assert img.getpixel((0, 0)) == (255, 0, 0)

    def test_roundtrip_preserves_data(self):
        """Encoding then decoding should preserve pixel values."""
        arr = np.random.randint(0, 255, (16, 16, 3), dtype=np.uint8)
        b64 = array_to_base64(arr)
        decoded = np.array(Image.open(BytesIO(base64.b64decode(b64))))
        np.testing.assert_array_equal(arr, decoded)

    def test_grayscale_roundtrip(self):
        """Grayscale roundtrip."""
        arr = np.arange(64, dtype=np.uint8).reshape(8, 8)
        b64 = array_to_base64(arr)
        decoded = np.array(Image.open(BytesIO(base64.b64decode(b64))))
        np.testing.assert_array_equal(arr, decoded)


class TestArrayToFastPngBase64:
    def test_produces_valid_png(self):
        arr = np.random.randint(0, 255, (32, 32, 3), dtype=np.uint8)
        b64 = array_to_fast_png_base64(arr)
        img = Image.open(BytesIO(base64.b64decode(b64)))
        assert img.size == (32, 32)

    def test_same_pixel_values_as_standard(self):
        """Fast and standard PNG should decode to identical pixels."""
        arr = np.random.randint(0, 255, (16, 16, 3), dtype=np.uint8)
        standard = array_to_base64(arr)
        fast = array_to_fast_png_base64(arr)
        img_std = np.array(Image.open(BytesIO(base64.b64decode(standard))))
        img_fast = np.array(Image.open(BytesIO(base64.b64decode(fast))))
        np.testing.assert_array_equal(img_std, img_fast)

    def test_unsupported_shape_raises(self):
        arr = np.zeros((8, 8, 5), dtype=np.uint8)
        with pytest.raises(ValueError):
            array_to_fast_png_base64(arr)


class TestLabelsToRgba:
    def test_all_background(self):
        labels = np.zeros((16, 16), dtype=np.int32)
        rgba = labels_to_rgba(labels)
        assert rgba.shape == (16, 16, 4)
        assert np.all(rgba[:, :, 3] == 0)

    def test_single_label_opaque(self):
        labels = np.zeros((16, 16), dtype=np.int32)
        labels[4:8, 4:8] = 1
        rgba = labels_to_rgba(labels)
        # Labeled pixels are opaque
        assert np.all(rgba[4:8, 4:8, 3] == 255)
        # Background is transparent
        assert np.all(rgba[0:4, :, 3] == 0)

    def test_different_labels_get_different_colors(self):
        """Two labels should get different hash-based colors."""
        labels = np.zeros((16, 16), dtype=np.int32)
        labels[0:4, 0:4] = 1
        labels[8:12, 8:12] = 2
        rgba = labels_to_rgba(labels)
        color1 = tuple(rgba[2, 2, :3])
        color2 = tuple(rgba[10, 10, :3])
        assert color1 != color2, "Different labels should have different colors"

    def test_deterministic_colors(self):
        """Same label should always produce same color."""
        labels1 = np.zeros((8, 8), dtype=np.int32)
        labels1[2:4, 2:4] = 5
        labels2 = np.zeros((16, 16), dtype=np.int32)
        labels2[10:12, 10:12] = 5
        rgba1 = labels_to_rgba(labels1)
        rgba2 = labels_to_rgba(labels2)
        assert tuple(rgba1[2, 2, :3]) == tuple(rgba2[10, 10, :3])

    def test_contours_only(self):
        """Contour mode should only color the boundary."""
        labels = np.zeros((32, 32), dtype=np.int32)
        labels[8:24, 8:24] = 1  # 16x16 filled region
        rgba = labels_to_rgba(labels, contours_only=True, contour_width=1)
        # Interior pixel should be transparent (eroded away)
        assert rgba[16, 16, 3] == 0
        # Boundary pixel should be opaque
        assert rgba[8, 8, 3] == 255

    def test_contours_wide(self):
        """Wider contours should color more boundary pixels."""
        labels = np.zeros((32, 32), dtype=np.int32)
        labels[8:24, 8:24] = 1
        rgba_thin = labels_to_rgba(labels, contours_only=True, contour_width=1)
        rgba_wide = labels_to_rgba(labels, contours_only=True, contour_width=3)
        # Wide contour should have more opaque pixels
        thin_opaque = np.sum(rgba_thin[:, :, 3] > 0)
        wide_opaque = np.sum(rgba_wide[:, :, 3] > 0)
        assert wide_opaque > thin_opaque

    def test_many_labels(self):
        """Handles many unique labels without error."""
        labels = np.arange(100, dtype=np.int32).reshape(10, 10)
        rgba = labels_to_rgba(labels)
        # Label 0 (top-left) transparent, rest opaque
        assert rgba[0, 0, 3] == 0
        assert rgba[1, 1, 3] == 255


class TestCompositeChannels:
    def test_single_channel_red(self):
        ch = np.full((4, 4), 255, dtype=np.uint8)
        result = composite_channels(
            [ch], ["#ff0000"], [0.0], [1.0],
            data_mins=[0.0], data_maxs=[255.0],
        )
        assert result.shape == (4, 4, 3)
        assert result[0, 0, 0] == 255  # red
        assert result[0, 0, 1] == 0    # green
        assert result[0, 0, 2] == 0    # blue

    def test_two_channels_composite(self):
        red_ch = np.full((4, 4), 255, dtype=np.uint8)
        green_ch = np.full((4, 4), 255, dtype=np.uint8)
        result = composite_channels(
            [red_ch, green_ch], ["#ff0000", "#00ff00"], [0.0, 0.0], [1.0, 1.0],
            data_mins=[0.0, 0.0], data_maxs=[255.0, 255.0],
        )
        assert result.shape == (4, 4, 3)
        assert result[0, 0, 0] > 0   # red channel contributed
        assert result[0, 0, 1] > 0   # green channel contributed

    def test_empty_channels(self):
        result = composite_channels([], [], [], [])
        assert result.shape == (1, 1, 3)

    def test_output_dtype(self):
        ch = np.zeros((4, 4), dtype=np.uint8)
        result = composite_channels([ch], ["#ffffff"], [0.0], [1.0])
        assert result.dtype == np.uint8

    def test_single_channel_green_only(self):
        """Channel with #00ff00 should only affect green plane (r=0 skipped)."""
        ch = np.full((8, 8), 200, dtype=np.uint8)
        result = composite_channels(
            [ch], ["#00ff00"], [0.0], [1.0],
            data_mins=[0.0], data_maxs=[200.0],
        )
        assert result[0, 0, 0] == 0    # no red
        assert result[0, 0, 1] == 255  # full green
        assert result[0, 0, 2] == 0    # no blue

    def test_uint16_single_channel(self):
        """uint16 data uses LUT fast path."""
        ch = np.full((4, 4), 32768, dtype=np.uint16)
        result = composite_channels(
            [ch], ["#ffffff"], [0.0], [1.0],
            data_mins=[0.0], data_maxs=[65535.0],
        )
        # Mid-range value → ~128
        assert 120 <= result[0, 0, 0] <= 135

    def test_float32_single_channel(self):
        """float32 data uses the non-integer path."""
        ch = np.full((4, 4), 0.5, dtype=np.float32)
        result = composite_channels(
            [ch], ["#ffffff"], [0.0], [1.0],
            data_mins=[0.0], data_maxs=[1.0],
        )
        # 0.5 normalized → ~127
        assert 120 <= result[0, 0, 0] <= 135

    def test_contrast_window(self):
        """Contrast windowing with min/max should clip appropriately."""
        # Linear ramp 0-255
        ch = np.arange(256, dtype=np.uint8).reshape(16, 16)
        result = composite_channels(
            [ch], ["#ffffff"], [0.2], [0.8],  # narrow window
            data_mins=[0.0], data_maxs=[255.0],
        )
        # Values below 20% of range should be black
        assert result[0, 0, 0] == 0  # pixel value 0, below window
        # Values above 80% of range should be white
        assert result[15, 15, 0] == 255  # pixel value 255, above window

    def test_zero_span_data(self):
        """When data_min == data_max (constant data), result should be zero."""
        ch = np.full((4, 4), 100, dtype=np.uint16)
        result = composite_channels(
            [ch], ["#ffffff"], [0.0], [1.0],
            data_mins=[100.0], data_maxs=[100.0],
        )
        np.testing.assert_array_equal(result, np.zeros((4, 4, 3), dtype=np.uint8))

    def test_multi_channel_overflow_clipping(self):
        """Three saturated channels should clip to 255, not overflow."""
        ch = np.full((4, 4), 255, dtype=np.uint8)
        result = composite_channels(
            [ch, ch, ch],
            ["#ff0000", "#00ff00", "#0000ff"],
            [0.0, 0.0, 0.0], [1.0, 1.0, 1.0],
            data_mins=[0.0, 0.0, 0.0], data_maxs=[255.0, 255.0, 255.0],
        )
        # Each channel contributes 255 to its plane → clipped to 255
        assert result[0, 0, 0] == 255
        assert result[0, 0, 1] == 255
        assert result[0, 0, 2] == 255

    def test_multi_channel_additive_blending(self):
        """Two channels contributing to same plane add up."""
        ch = np.full((4, 4), 200, dtype=np.uint8)
        result = composite_channels(
            [ch, ch],
            ["#ff0000", "#800000"],  # both contribute to red
            [0.0, 0.0], [1.0, 1.0],
            data_mins=[0.0, 0.0], data_maxs=[200.0, 200.0],
        )
        # First channel: 255, second: ~128. Sum clipped to 255.
        assert result[0, 0, 0] == 255

    def test_big_endian_uint16(self):
        """Non-native byte order should be handled correctly."""
        ch_native = np.array([[0, 128, 255]], dtype=np.uint16)
        ch_be = ch_native.astype(">u2")
        result_native = composite_channels(
            [ch_native], ["#ffffff"], [0.0], [1.0],
            data_mins=[0.0], data_maxs=[255.0],
        )
        result_be = composite_channels(
            [ch_be], ["#ffffff"], [0.0], [1.0],
            data_mins=[0.0], data_maxs=[255.0],
        )
        np.testing.assert_array_equal(result_native, result_be)

    def test_no_data_mins_provided(self):
        """When data_mins/data_maxs are None, should auto-compute from data."""
        ch = np.array([[0, 128, 255]], dtype=np.uint8).reshape(1, 3)
        result = composite_channels(
            [ch], ["#ffffff"], [0.0], [1.0],
        )
        assert result[0, 0, 0] == 0    # min → black
        assert result[0, 2, 0] == 255  # max → white

    def test_zero_width_array(self):
        """Zero-width array should return fallback."""
        ch = np.zeros((10, 0), dtype=np.uint8)
        result = composite_channels([ch], ["#ffffff"], [0.0], [1.0])
        assert result.shape == (1, 1, 3)

    def test_multi_channel_float32(self):
        """Multi-channel float path with uint16 accumulator."""
        ch1 = np.full((4, 4), 0.8, dtype=np.float32)
        ch2 = np.full((4, 4), 0.5, dtype=np.float32)
        result = composite_channels(
            [ch1, ch2],
            ["#ff0000", "#00ff00"],
            [0.0, 0.0], [1.0, 1.0],
            data_mins=[0.0, 0.0], data_maxs=[1.0, 1.0],
        )
        # Red channel from ch1: ~204 (0.8 * 255)
        assert 195 <= result[0, 0, 0] <= 210
        # Green channel from ch2: ~128 (0.5 * 255)
        assert 120 <= result[0, 0, 1] <= 135

    def test_multi_channel_mixed_dtypes(self):
        """Channels of different dtypes in multi-channel composite."""
        ch_u8 = np.full((4, 4), 255, dtype=np.uint8)
        ch_f32 = np.full((4, 4), 1.0, dtype=np.float32)
        result = composite_channels(
            [ch_u8, ch_f32],
            ["#ff0000", "#00ff00"],
            [0.0, 0.0], [1.0, 1.0],
            data_mins=[0.0, 0.0], data_maxs=[255.0, 1.0],
        )
        assert result[0, 0, 0] == 255  # red from uint8
        assert result[0, 0, 1] == 255  # green from float32


class TestBioImageViewer:
    def test_import(self):
        from anybioimage import BioImageViewer
        assert BioImageViewer is not None

    def test_instantiate(self):
        from anybioimage import BioImageViewer
        viewer = BioImageViewer()
        assert viewer is not None

    def test_set_image_numpy(self):
        from anybioimage import BioImageViewer
        viewer = BioImageViewer()
        arr = np.random.randint(0, 255, (64, 64), dtype=np.uint8)
        viewer.set_image(arr)
        assert viewer.width == 64
        assert viewer.height == 64

    @pytest.mark.xfail(reason="Removed with Canvas2D compositor in 2026-04-19 unified viewer; new pipeline preserves all 5D dims from numpy — delete in Phase 2")
    def test_set_image_numpy_always_2d(self):
        from anybioimage import BioImageViewer
        viewer = BioImageViewer()
        # Raw numpy arrays are squeezed to 2D — use BioImage for 5D support
        arr = np.random.randint(0, 255, (2, 3, 1, 32, 32), dtype=np.uint8)
        viewer.set_image(arr)
        # Squeezed to 2D, so dims reset to 1
        assert viewer.dim_t == 1
        assert viewer.dim_c == 1
        assert viewer.dim_z == 1

    def test_add_and_clear_mask(self):
        from anybioimage import BioImageViewer
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        labels = np.zeros((32, 32), dtype=np.int32)
        labels[8:16, 8:16] = 1
        mask_id = viewer.add_mask(labels, name="Test", color="#ff0000")
        assert mask_id in viewer.get_mask_ids()
        viewer.clear_masks()
        assert len(viewer.get_mask_ids()) == 0

    def test_annotations_dataframes(self):
        from anybioimage import BioImageViewer
        viewer = BioImageViewer()
        viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
        assert hasattr(viewer, "rois_df")
        assert hasattr(viewer, "polygons_df")
        assert hasattr(viewer, "points_df")
