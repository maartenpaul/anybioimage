"""Mask settings changed in the layers panel take effect, and color= picks
single-colour mode."""
import numpy as np

from anybioimage import BioImageViewer


def _viewer_with_mask(**kwargs):
    viewer = BioImageViewer()
    viewer.set_image(np.zeros((64, 64), dtype=np.uint8))
    labels = np.zeros((64, 64), dtype=np.int32)
    labels[8:24, 8:24] = 1
    labels[30:50, 30:50] = 2
    mask_id = viewer.add_mask(labels, **kwargs)
    return viewer, mask_id


def _entry(viewer, mask_id):
    return next(m for m in viewer._masks_data if m["id"] == mask_id)


def test_default_is_per_label_colours():
    viewer, mask_id = _viewer_with_mask()
    assert _entry(viewer, mask_id)["color_mode"] == "labels"


def test_explicit_color_selects_single_colour():
    viewer, mask_id = _viewer_with_mask(color="#00ff00")
    entry = _entry(viewer, mask_id)
    assert entry["color_mode"] == "single" and entry["color"] == "#00ff00"


def test_contours_toggled_in_panel_rerenders():
    viewer, mask_id = _viewer_with_mask()
    filled = _entry(viewer, mask_id)["data"]
    # What the layers panel does: write the field directly into _masks_data.
    viewer._masks_data = [{**m, "contours": True} for m in viewer._masks_data]
    outlined = _entry(viewer, mask_id)["data"]
    assert outlined != filled
    viewer._masks_data = [{**m, "contours": False} for m in viewer._masks_data]
    assert _entry(viewer, mask_id)["data"] == filled


def test_panel_colour_change_does_not_rerender():
    """Colour is applied by the frontend; the PNG stays the same."""
    viewer, mask_id = _viewer_with_mask()
    data = _entry(viewer, mask_id)["data"]
    viewer._masks_data = [{**m, "color": "#123456", "color_mode": "single"} for m in viewer._masks_data]
    assert _entry(viewer, mask_id)["data"] == data
    assert _entry(viewer, mask_id)["color_mode"] == "single"


def test_masks_df_reports_colour_mode():
    viewer, _ = _viewer_with_mask(color="#ff0000")
    assert viewer.masks_df["color_mode"].tolist() == ["single"]


def test_stale_frontend_update_after_contour_toggle_is_corrected():
    """marimo can apply the frontend's update a second time, after the observer
    replaced the picture: the stored picture must still end up as outlines."""
    viewer, mask_id = _viewer_with_mask()
    filled = _entry(viewer, mask_id)["data"]
    stale = [{**m, "contours": True} for m in viewer._masks_data]  # old picture, new flag
    viewer._masks_data = stale
    outlined = _entry(viewer, mask_id)["data"]
    viewer._masks_data = [dict(m) for m in stale]  # same frontend value again
    assert _entry(viewer, mask_id)["data"] == outlined != filled
    viewer.update_mask_settings(mask_id, opacity=0.6)  # a later Python update keeps outlines
    assert _entry(viewer, mask_id)["data"] == outlined
