"""The T/Z sliders send ``_preview_mode=True``, the new index, then
``_preview_mode=False`` with the same index. Small (non-tile) images must
still end up showing the new plane."""
import numpy as np
import pytest

from anybioimage import BioImageViewer


@pytest.fixture
def small_viewer():
    """4 time points x 3 z planes, 64x64, each plane with a distinct pattern."""
    arr = np.zeros((4, 1, 3, 64, 64), dtype=np.uint16)
    for t in range(4):
        for z in range(3):
            arr[t, 0, z, 8 * t : 8 * t + 16, 8 * z : 8 * z + 16] = 4000
    viewer = BioImageViewer()
    viewer.set_image(arr)
    assert not viewer._use_tile_mode
    return viewer


def _reference(viewer, **position):
    """image_data the widget produces for a direct (non-slider) move."""
    for name, value in position.items():
        setattr(viewer, name, value)
    data = viewer.image_data
    viewer.current_t = 0
    viewer.current_z = 0
    return data


@pytest.mark.parametrize("axis, index", [("current_t", 2), ("current_z", 1)])
def test_slider_move_updates_small_in_memory_image(small_viewer, axis, index):
    expected = _reference(small_viewer, **{axis: index})
    start = small_viewer.image_data
    assert expected != start

    small_viewer._preview_mode = True
    setattr(small_viewer, axis, index)
    assert small_viewer.image_data == expected, "plane must update while scrubbing"

    small_viewer._preview_mode = False
    assert small_viewer.image_data == expected


def test_leaving_preview_mode_renders_a_plane_skipped_while_scrubbing(small_viewer):
    """Lazy images skip uncached planes during a scrub; the final plane must
    be rendered when the scrub ends even though the index no longer changes."""
    expected = _reference(small_viewer, current_t=3)
    full = small_viewer._full_array

    # Emulate a lazy image: no in-RAM array while scrubbing, so the plane is skipped.
    small_viewer._preview_mode = True
    small_viewer._full_array = None
    small_viewer._bioimage = object()
    small_viewer.current_t = 3
    assert small_viewer.image_data != expected

    small_viewer._bioimage = None
    small_viewer._full_array = full
    small_viewer._preview_mode = False
    assert small_viewer.image_data == expected
