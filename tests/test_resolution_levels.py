"""Resolution levels: the viewer's coordinates stay full resolution at every level.

width/height, annotations and masks are level-0 pixels; switching level only
changes the tile grid (_level_shape) and which pixels tiles are cut from. The
caller's BioImage is never switched to another level.
"""
import numpy as np
import pytest

from anybioimage import BioImageViewer

bioio = pytest.importorskip("bioio")
from bioio import BioImage  # noqa: E402


def _stop_precompute(viewer):
    event = getattr(viewer, "_precompute_event", None)
    if event:
        event.set()
    future = getattr(viewer, "_precompute_future", None)
    if future:
        try:
            future.result(timeout=10)
        except Exception:
            pass


@pytest.fixture
def flat_viewer():
    """1024x1536 single-plane BioImage without native levels -> synthetic pyramid."""
    data = (np.arange(1024 * 1536, dtype=np.uint32) % 4000).astype(np.uint16).reshape(1, 1, 1, 1024, 1536)
    viewer = BioImageViewer()
    viewer.set_image(BioImage(data))
    _stop_precompute(viewer)
    return viewer


def test_synthetic_level_keeps_full_resolution_size(flat_viewer):
    v = flat_viewer
    assert v.resolution_levels == [0, 1, 2]
    v.current_resolution = 1
    _stop_precompute(v)
    assert (v.width, v.height) == (1536, 1024)
    assert v._level_shape == [512, 768, 1]
    assert v._level_hw() == (512, 768)


def test_synthetic_level_tiles_cut_from_level(flat_viewer):
    v = flat_viewer
    v.current_resolution = 2
    _stop_precompute(v)
    # level 2 is 256 x 384: tile (1, 0) is the right 128 columns, tile (0, 1) is past the bottom
    tile = v._get_tile(0, 0, 1, 0)
    assert (tile["w"], tile["h"]) == (128, 256)
    assert v._get_tile(0, 0, 0, 1) is None


def test_back_to_level_zero_clears_level_shape(flat_viewer):
    v = flat_viewer
    v.current_resolution = 1
    v.current_resolution = 0
    _stop_precompute(v)
    assert v._level_shape == []
    assert v._level_hw() == (1024, 1536)


def test_new_image_resets_level(flat_viewer):
    v = flat_viewer
    v.current_resolution = 2
    _stop_precompute(v)
    v.set_image(np.zeros((64, 80), dtype=np.uint8))
    assert v.current_resolution == 0
    assert v._level_shape == []
    assert (v.width, v.height) == (80, 64)


def test_rois_stay_in_full_resolution_pixels(flat_viewer):
    v = flat_viewer
    v.rois_df = __import__("pandas").DataFrame([{"id": "r1", "x": 1000, "y": 800, "width": 100, "height": 50}])
    v.current_resolution = 2
    _stop_precompute(v)
    row = v.rois_df.iloc[0]
    assert (row.x, row.y, row.width, row.height) == (1000, 800, 100, 50)


def test_mask_keeps_full_resolution_at_lower_level(flat_viewer):
    v = flat_viewer
    labels = np.zeros((1024, 1536), dtype=np.uint16)
    labels[900:1000, 1400:1500] = 1
    mid = v.add_mask(labels)
    v.current_resolution = 2
    _stop_precompute(v)
    import base64
    import io

    from PIL import Image
    mask = next(m for m in v._masks_data if m["id"] == mid)
    png = Image.open(io.BytesIO(base64.b64decode(mask["data"])))
    assert png.size == (v.width, v.height) == (1536, 1024)


# --- native pyramids (OME-Zarr) -------------------------------------------------

@pytest.fixture
def zarr_bioimage(tmp_path):
    pytest.importorskip("bioio_ome_zarr")
    from tests.conftest import write_v04_image
    path = write_v04_image(tmp_path / "pyr.ome.zarr", shape=(1, 1, 1, 128, 192),
                           chunks=(1, 1, 1, 64, 64), n_levels=2)
    return BioImage(path)


def test_native_level_does_not_change_callers_bioimage(zarr_bioimage):
    img = zarr_bioimage
    v = BioImageViewer()
    v.set_image(img)
    _stop_precompute(v)
    v.current_resolution = 1
    _stop_precompute(v)
    assert img.current_resolution_level == 0
    assert img.dims.Y == 128 and img.dims.X == 192
    assert (v.width, v.height) == (192, 128)
    assert v._level_shape == [64, 96, 1]


def test_native_bioimage_at_other_level_starts_at_zero(zarr_bioimage):
    img = zarr_bioimage
    img.set_resolution_level(1)
    v = BioImageViewer()
    v.set_image(img)
    _stop_precompute(v)
    assert (v.width, v.height) == (192, 128)
    assert img.current_resolution_level == 1  # the caller's choice is left alone


# --- SAM prompt scaling ----------------------------------------------------------

def test_sam_scale_maps_full_resolution_to_level(flat_viewer):
    v = flat_viewer
    level_image = np.zeros((256, 384), dtype=np.uint8)
    assert v._sam_scale(level_image) == (0.25, 0.25)
