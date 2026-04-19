"""Tests for the metadata-only zarr load path (`_set_zarr_url`).

NOTE: Many tests in this module were written for the Canvas2D compositor era and
reference removed internals (_viv_mode, _precompute_future, _full_array).
They are marked xfail and scheduled for deletion in Phase 2.
"""

from pathlib import Path

import pytest

from anybioimage import BioImageViewer

EXAMPLE_ZARR = Path(__file__).parent.parent / "examples" / "image.zarr"


@pytest.fixture
def zarr_viewer():
    if not EXAMPLE_ZARR.is_dir():
        pytest.skip(f"{EXAMPLE_ZARR} missing (run examples/create_test_plate.py)")
    viewer = BioImageViewer(render_backend="viv")
    viewer.set_image(str(EXAMPLE_ZARR))
    return viewer


def test_zarr_source_set_to_url(zarr_viewer):
    assert zarr_viewer._zarr_source.get("url") == str(EXAMPLE_ZARR)


@pytest.mark.xfail(reason="Removed with Canvas2D compositor in 2026-04-19 unified viewer; dims are now populated JS-side for zarr — delete in Phase 2")
def test_dimensions_populated_from_metadata(zarr_viewer):
    # The test zarr is a 10T×3Z×2×2048×2048 image per CLAUDE.md
    assert zarr_viewer.dim_t >= 1
    assert zarr_viewer.dim_c >= 1
    assert zarr_viewer.dim_z >= 1
    assert zarr_viewer.width > 0
    assert zarr_viewer.height > 0


@pytest.mark.xfail(reason="Removed with Canvas2D compositor in 2026-04-19 unified viewer; channel_settings are now populated JS-side for zarr — delete in Phase 2")
def test_channel_settings_populated(zarr_viewer):
    assert len(zarr_viewer._channel_settings) == zarr_viewer.dim_c
    for ch in zarr_viewer._channel_settings:
        assert "color" in ch
        assert "visible" in ch
        assert 0.0 <= ch["min"] <= 1.0
        assert 0.0 <= ch["max"] <= 1.0


@pytest.mark.xfail(reason="Removed with Canvas2D compositor in 2026-04-19 unified viewer; resolution_levels now populated JS-side for zarr — delete in Phase 2")
def test_resolution_levels_populated(zarr_viewer):
    # image.zarr has three levels: s0, s1, s2
    assert len(zarr_viewer.resolution_levels) >= 1


@pytest.mark.xfail(reason="Removed with Canvas2D compositor in 2026-04-19 unified viewer; _viv_mode traitlet deleted — delete in Phase 2")
def test_viv_mode_stays_viv_for_zarr(zarr_viewer):
    assert zarr_viewer._viv_mode == "viv"


@pytest.mark.xfail(reason="Removed with Canvas2D compositor in 2026-04-19 unified viewer; _precompute_future removed — delete in Phase 2")
def test_no_precompute_started(zarr_viewer):
    # The precompute future is only set by _set_bioimage; the zarr-url path must not start it.
    assert zarr_viewer._precompute_future is None


def test_no_thumbnail_encoded(zarr_viewer):
    # On the Viv path, image_data stays empty — no PNG encoded.
    assert zarr_viewer.image_data == ""


@pytest.mark.xfail(reason="Removed with Canvas2D compositor in 2026-04-19 unified viewer; _full_array removed — delete in Phase 2")
def test_full_array_not_loaded(zarr_viewer):
    assert zarr_viewer._full_array is None


@pytest.mark.xfail(reason="Removed with Canvas2D compositor in 2026-04-19 unified viewer; _viv_mode and _raw_numpy_array removed — delete in Phase 2")
def test_numpy_then_zarr_keeps_image_data_empty():
    """If a numpy image is loaded first, a subsequent zarr URL must leave image_data empty."""
    import numpy as np

    if not EXAMPLE_ZARR.is_dir():
        pytest.skip(f"{EXAMPLE_ZARR} missing")
    viewer = BioImageViewer(render_backend="viv")
    viewer.set_image(np.ones((64, 64), dtype=np.uint8))  # flips to canvas2d-fallback
    viewer.set_image(str(EXAMPLE_ZARR))                   # re-enters Viv path
    assert viewer._viv_mode == "viv"
    assert viewer.image_data == "", f"stale PNG of {len(viewer.image_data)} chars"
    assert viewer._raw_numpy_array is None


class TestChannelSettingsFromOmero:
    @pytest.mark.xfail(reason="Removed with Canvas2D compositor in 2026-04-19 unified viewer; new _channel_settings_from_omero uses different default palette and name format — delete in Phase 2")
    def test_no_omero_block_returns_defaults(self):
        from anybioimage.mixins.image_loading import _channel_settings_from_omero
        from anybioimage.utils import CHANNEL_COLORS

        result = _channel_settings_from_omero({}, dim_c=3)
        assert len(result) == 3
        for i, ch in enumerate(result):
            assert ch["color"] == CHANNEL_COLORS[i % len(CHANNEL_COLORS)]
            assert ch["visible"] is True
            assert ch["name"] == f"Channel {i}"

    @pytest.mark.xfail(reason="Removed with Canvas2D compositor in 2026-04-19 unified viewer; new _channel_settings_from_omero does not lowercase hex colors — delete in Phase 2")
    def test_omero_hex_color_normalized(self):
        from anybioimage.mixins.image_loading import _channel_settings_from_omero

        ome = {"omero": {"channels": [{"color": "FF0000"}]}}
        result = _channel_settings_from_omero(ome, dim_c=1)
        assert result[0]["color"] == "#ff0000"

    @pytest.mark.xfail(reason="Removed with Canvas2D compositor in 2026-04-19 unified viewer; new _channel_settings_from_omero does not lowercase hex colors — delete in Phase 2")
    def test_omero_hex_color_with_hash_preserved(self):
        from anybioimage.mixins.image_loading import _channel_settings_from_omero

        ome = {"omero": {"channels": [{"color": "#00FF00"}]}}
        result = _channel_settings_from_omero(ome, dim_c=1)
        assert result[0]["color"] == "#00ff00"

    @pytest.mark.xfail(reason="Removed with Canvas2D compositor in 2026-04-19 unified viewer; new _channel_settings_from_omero always sets visible=True — delete in Phase 2")
    def test_omero_active_false_respected(self):
        from anybioimage.mixins.image_loading import _channel_settings_from_omero

        ome = {"omero": {"channels": [{"active": False}]}}
        result = _channel_settings_from_omero(ome, dim_c=1)
        assert result[0]["visible"] is False

    def test_omero_label_used_as_name(self):
        from anybioimage.mixins.image_loading import _channel_settings_from_omero

        ome = {"omero": {"channels": [{"label": "DAPI"}]}}
        result = _channel_settings_from_omero(ome, dim_c=1)
        assert result[0]["name"] == "DAPI"

    def test_omero_window_maps_to_normalized_min_max(self):
        from anybioimage.mixins.image_loading import _channel_settings_from_omero

        ome = {"omero": {"channels": [{
            "window": {"min": 0.0, "max": 1000.0, "start": 100.0, "end": 800.0}
        }]}}
        result = _channel_settings_from_omero(ome, dim_c=1)
        assert abs(result[0]["min"] - 0.1) < 1e-6  # 100/1000
        assert abs(result[0]["max"] - 0.8) < 1e-6  # 800/1000
        assert result[0]["data_min"] == 0.0
        assert result[0]["data_max"] == 1000.0

    @pytest.mark.xfail(reason="Removed with Canvas2D compositor in 2026-04-19 unified viewer; new _channel_settings_from_omero uses different default names/palette — delete in Phase 2")
    def test_omero_channels_shorter_than_dim_c_fills_defaults(self):
        from anybioimage.mixins.image_loading import _channel_settings_from_omero
        from anybioimage.utils import CHANNEL_COLORS

        # Only one channel in omero, but dim_c=3 — remaining fall back to defaults
        ome = {"omero": {"channels": [{"label": "DAPI", "color": "0000FF"}]}}
        result = _channel_settings_from_omero(ome, dim_c=3)
        assert result[0]["name"] == "DAPI"
        assert result[0]["color"] == "#0000ff"
        assert result[1]["name"] == "Channel 1"
        assert result[1]["color"] == CHANNEL_COLORS[1 % len(CHANNEL_COLORS)]
        assert result[2]["name"] == "Channel 2"
