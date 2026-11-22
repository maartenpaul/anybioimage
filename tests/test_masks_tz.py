"""Masks given as a label stack follow the T/Z sliders."""
import numpy as np
import pytest

from anybioimage import BioImageViewer


def _viewer(t=4, z=3, size=32):
    viewer = BioImageViewer()
    viewer.set_image(np.zeros((t, 1, z, size, size), dtype=np.uint16))
    return viewer


def _stack(n, size=32):
    """n frames, frame i has a square of label i+1 at a different place."""
    labels = np.zeros((n, size, size), dtype=np.int32)
    for i in range(n):
        labels[i, 2 * i : 2 * i + 6, 2 * i : 2 * i + 6] = i + 1
    return labels


def _data(viewer, mask_id):
    return next(m["data"] for m in viewer._masks_data if m["id"] == mask_id)


def test_tyx_stack_follows_time_slider():
    viewer = _viewer(t=4, z=3)
    labels = _stack(4)
    mask_id = viewer.add_mask(labels)
    frames = {}
    for t in range(4):
        viewer.current_t = t
        np.testing.assert_array_equal(viewer._mask_arrays[mask_id], labels[t])
        frames[t] = _data(viewer, mask_id)
    assert len(set(frames.values())) == 4
    viewer.current_z = 2  # z does not change a TYX mask
    assert _data(viewer, mask_id) == frames[3]


def test_zyx_stack_follows_z_slider():
    viewer = _viewer(t=4, z=3)
    labels = _stack(3)
    mask_id = viewer.add_mask(labels)
    viewer.current_z = 2
    np.testing.assert_array_equal(viewer._mask_arrays[mask_id], labels[2])


def test_tzyx_stack_follows_both():
    viewer = _viewer(t=2, z=3)
    labels = np.arange(6 * 8 * 8, dtype=np.int32).reshape(2, 3, 8, 8)
    mask_id = viewer.add_mask(labels)
    viewer.current_t, viewer.current_z = 1, 2
    np.testing.assert_array_equal(viewer._mask_arrays[mask_id], labels[1, 2])


def test_tczyx_with_one_channel_is_accepted():
    viewer = _viewer(t=2, z=3)
    labels = np.zeros((2, 1, 3, 8, 8), dtype=np.int32)
    labels[1, 0, 2, 0, 0] = 5
    mask_id = viewer.add_mask(labels)
    viewer.current_t, viewer.current_z = 1, 2
    assert viewer._mask_arrays[mask_id][0, 0] == 5


def test_2d_mask_is_static():
    viewer = _viewer()
    labels = _stack(1)[0]
    mask_id = viewer.add_mask(labels)
    before = _data(viewer, mask_id)
    viewer.current_t = 3
    assert _data(viewer, mask_id) == before


def test_leading_singleton_axes_are_ignored():
    viewer = _viewer()
    mask_id = viewer.add_mask(np.ones((1, 1, 32, 32), dtype=np.int32))
    assert viewer._mask_arrays[mask_id].shape == (32, 32)


def test_ambiguous_stack_needs_dims():
    viewer = _viewer(t=3, z=3)
    with pytest.raises(ValueError, match="dims='TYX' or dims='ZYX'"):
        viewer.add_mask(_stack(3))
    mask_id = viewer.add_mask(_stack(3), dims="zyx")
    viewer.current_z = 1
    np.testing.assert_array_equal(viewer._mask_arrays[mask_id], _stack(3)[1])


def test_stack_that_does_not_fit_raises():
    viewer = _viewer(t=4, z=3)
    with pytest.raises(ValueError, match="has 5 frames"):
        viewer.add_mask(_stack(5))


def test_contour_change_keeps_following_slider():
    viewer = _viewer(t=4, z=1)
    labels = _stack(4)
    mask_id = viewer.add_mask(labels)
    viewer.current_t = 2
    viewer.update_mask_settings(mask_id, contours=True, contour_width=2)
    filled_t2 = _data(viewer, mask_id)
    viewer.current_t = 3
    assert _data(viewer, mask_id) != filled_t2
    mask = next(m for m in viewer._masks_data if m["id"] == mask_id)
    assert mask["contours"] is True


def test_frame_cache_is_bounded(monkeypatch):
    from anybioimage.mixins import mask_management

    monkeypatch.setattr(mask_management, "_MASK_FRAME_CACHE_SIZE", 3)
    viewer = _viewer(t=8, z=1)
    mask_id = viewer.add_mask(_stack(8))
    for t in range(8):
        viewer.current_t = t
    assert len(viewer._mask_caches[mask_id]) == 3


def test_remove_mask_drops_stack():
    viewer = _viewer()
    mask_id = viewer.add_mask(_stack(4))
    viewer.remove_mask(mask_id)
    assert mask_id not in viewer._mask_stacks
    viewer.current_t = 1  # no error with the stack gone
