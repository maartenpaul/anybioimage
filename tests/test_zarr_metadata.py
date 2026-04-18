"""Tests for the metadata-only zarr load path (`_set_zarr_url`)."""

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


def test_dimensions_populated_from_metadata(zarr_viewer):
    # The test zarr is a 10T×3Z×2×2048×2048 image per CLAUDE.md
    assert zarr_viewer.dim_t >= 1
    assert zarr_viewer.dim_c >= 1
    assert zarr_viewer.dim_z >= 1
    assert zarr_viewer.width > 0
    assert zarr_viewer.height > 0


def test_channel_settings_populated(zarr_viewer):
    assert len(zarr_viewer._channel_settings) == zarr_viewer.dim_c
    for ch in zarr_viewer._channel_settings:
        assert "color" in ch
        assert "visible" in ch
        assert 0.0 <= ch["min"] <= 1.0
        assert 0.0 <= ch["max"] <= 1.0


def test_resolution_levels_populated(zarr_viewer):
    # image.zarr has three levels: s0, s1, s2
    assert len(zarr_viewer.resolution_levels) >= 1


def test_viv_mode_stays_viv_for_zarr(zarr_viewer):
    assert zarr_viewer._viv_mode == "viv"


def test_no_precompute_started(zarr_viewer):
    # The precompute future is only set by _set_bioimage; the zarr-url path must not start it.
    assert zarr_viewer._precompute_future is None


def test_no_thumbnail_encoded(zarr_viewer):
    # On the Viv path, image_data stays empty — no PNG encoded.
    assert zarr_viewer.image_data == ""


def test_full_array_not_loaded(zarr_viewer):
    assert zarr_viewer._full_array is None
