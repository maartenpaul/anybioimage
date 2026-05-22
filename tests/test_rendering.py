"""Rendering pipeline tests — verify that Python compositing output actually changes
when channel settings change. These tests are the backstop that pure state tests miss:
they catch bugs where settings are stored correctly but never applied to the output."""

import numpy as np
import pytest
from anybioimage import BioImageViewer


@pytest.fixture
def bioimage_viewer():
    """BioImageViewer loaded with the small fluocell.tif example (791 KB, multi-channel)."""
    bioio = pytest.importorskip("bioio")
    bioio_tifffile = pytest.importorskip("bioio_tifffile")
    img = bioio.BioImage("examples/fluocell.tif", reader=bioio_tifffile.Reader)
    viewer = BioImageViewer()
    viewer.set_image(img)
    return viewer


def _stop_precompute(viewer):
    """Cancel the background precompute thread and wait for it to finish."""
    event = getattr(viewer, "_precompute_event", None)
    if event:
        event.set()
    future = getattr(viewer, "_precompute_future", None)
    if future:
        try:
            future.result(timeout=5)
        except Exception:
            pass


def test_composite_changes_with_min_max(bioimage_viewer):
    """_get_composite_slice must produce different output after min/max changes."""
    viewer = bioimage_viewer
    _stop_precompute(viewer)

    composite_before = viewer._get_composite_slice(0, 0).copy()

    settings = [dict(ch, min=0.9, max=1.0) for ch in viewer._channel_settings]
    viewer._channel_settings = settings
    # Clear cache to bypass any stale entry and force recompute with new settings
    viewer._composite_cache.clear()

    composite_after = viewer._get_composite_slice(0, 0)
    assert not np.array_equal(composite_before, composite_after), (
        "Changing _channel_settings min/max must produce different composite output"
    )


def test_composite_changes_with_visibility(bioimage_viewer):
    """Hiding a channel must change the composite."""
    viewer = bioimage_viewer
    if len(viewer._channel_settings) < 2:
        pytest.skip("need at least 2 channels")

    _stop_precompute(viewer)
    composite_before = viewer._get_composite_slice(0, 0).copy()

    settings = list(viewer._channel_settings)
    settings[0] = {**settings[0], "visible": False}
    viewer._channel_settings = settings
    viewer._composite_cache.clear()

    composite_after = viewer._get_composite_slice(0, 0)
    assert not np.array_equal(composite_before, composite_after)


def test_channel_settings_change_clears_composite_cache(bioimage_viewer):
    """_on_channel_settings_change must clear the composite cache so stale data is not served."""
    viewer = bioimage_viewer
    _stop_precompute(viewer)

    # Prime the composite cache with the background thread fully stopped
    _ = viewer._get_composite_slice(0, 0)
    assert (0, 0, viewer.current_resolution) in getattr(viewer, "_composite_cache", {})

    # Change settings — observer must clear the cache
    settings = [dict(ch, min=0.5, max=1.0) for ch in viewer._channel_settings]
    viewer._channel_settings = settings

    assert (0, 0, viewer.current_resolution) not in getattr(viewer, "_composite_cache", {}), (
        "_composite_cache must be cleared when _channel_settings changes"
    )


def test_non_tile_mode_image_data_updates_on_contrast_change(bioimage_viewer):
    """For small images (non-tile mode), _on_channel_settings_change must push a new
    image_data PNG. Without this, the canvas is frozen at the old contrast forever."""
    viewer = bioimage_viewer
    if viewer._use_tile_mode:
        pytest.skip("image is in tile mode — non-tile path not exercised")

    image_data_before = viewer.image_data

    settings = [dict(ch, min=0.8, max=1.0) for ch in viewer._channel_settings]
    viewer._channel_settings = settings

    assert viewer.image_data != image_data_before, (
        "image_data must be refreshed after _channel_settings change in non-tile mode"
    )


def test_composite_channels_direct():
    """composite_channels utility applies min/max — no viewer needed."""
    from anybioimage.utils import composite_channels

    ch = np.full((8, 8), 32768, dtype=np.uint16)  # mid-range constant

    rgb_wide = composite_channels([ch], ["#ffffff"], mins=[0.0], maxs=[1.0],
                                  data_mins=[0.0], data_maxs=[65535.0])
    rgb_narrow = composite_channels([ch], ["#ffffff"], mins=[0.9], maxs=[1.0],
                                    data_mins=[0.0], data_maxs=[65535.0])

    # At mid-range intensity, wide window → ~50% brightness; narrow window (0.9–1.0) → near-zero
    assert rgb_wide.mean() > rgb_narrow.mean(), (
        "composite_channels must apply min/max contrast window"
    )
