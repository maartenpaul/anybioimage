import numpy as np
import pytest
from anybioimage import BioImageViewer


def make_viewer(shape=(64, 64), dtype=np.uint16, seed=42):
    """Create a viewer with a numpy array. Uses 2D shape (numpy path, single channel)."""
    rng = np.random.default_rng(seed)
    high = 255 if np.dtype(dtype).itemsize == 1 else 65535
    data = rng.integers(0, high, shape, dtype=dtype)
    viewer = BioImageViewer()
    viewer.set_image(data)
    return viewer, data


def test_auto_contrast_single_channel():
    viewer, _ = make_viewer()
    viewer.auto_contrast(channel=0)
    s = viewer._channel_settings[0]
    assert 0.0 <= s["min"] <= 1.0
    assert 0.0 <= s["max"] <= 1.0
    assert s["min"] < s["max"]


def test_auto_contrast_all_channels():
    viewer, _ = make_viewer()
    viewer.auto_contrast()
    for ch in viewer._channel_settings:
        assert ch["min"] < ch["max"]


def test_auto_contrast_normalised_in_range():
    viewer, _ = make_viewer()
    viewer.auto_contrast()
    for ch in viewer._channel_settings:
        assert 0.0 <= ch["min"] <= 1.0
        assert 0.0 <= ch["max"] <= 1.0


def test_auto_contrast_changes_settings():
    """auto_contrast should shift from the initial load values for a random image."""
    viewer, _ = make_viewer()
    before = [(ch["min"], ch["max"]) for ch in viewer._channel_settings]
    viewer.auto_contrast()
    after = [(ch["min"], ch["max"]) for ch in viewer._channel_settings]
    # At least one channel should differ (p2/p98 vs initial p0.5/p99.5)
    assert before != after


def test_auto_contrast_uint8():
    viewer, _ = make_viewer(dtype=np.uint8)
    viewer.auto_contrast()
    for ch in viewer._channel_settings:
        assert 0.0 <= ch["min"] <= 1.0
        assert 0.0 <= ch["max"] <= 1.0
        assert ch["min"] < ch["max"]


def test_auto_contrast_single_channel_image():
    viewer, _ = make_viewer(shape=(64, 64))
    viewer.auto_contrast(channel=0)
    s = viewer._channel_settings[0]
    assert s["min"] < s["max"]


def test_compute_auto_contrast_returns_dict():
    viewer, _ = make_viewer()
    result = viewer._compute_auto_contrast(0)
    assert "min" in result and "max" in result
    assert result["min"] < result["max"]


def test_auto_contrast_request_observer():
    """Simulates the JS button click: setting _auto_contrast_request should update settings."""
    viewer, _ = make_viewer()
    before = list(viewer._channel_settings)
    viewer._auto_contrast_request = {"channel": 0, "t": 0, "z": 0, "timestamp": 1}
    after = list(viewer._channel_settings)
    # min/max for channel 0 should have changed
    assert before[0]["min"] != after[0]["min"] or before[0]["max"] != after[0]["max"]
