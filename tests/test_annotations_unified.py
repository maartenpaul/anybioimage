# tests/test_annotations_unified.py
"""Unified _annotations traitlet + legacy DataFrame back-compat [spec §5]."""
from __future__ import annotations

import pandas as pd
import pytest

from anybioimage import BioImageViewer


def make_viewer() -> BioImageViewer:
    return BioImageViewer()


def test_annotations_starts_empty():
    v = make_viewer()
    assert v._annotations == []
    assert v.rois_df.empty
    assert v.polygons_df.empty
    assert v.points_df.empty


def test_rois_df_setter_roundtrip():
    v = make_viewer()
    df = pd.DataFrame([
        {"id": "r1", "x": 10, "y": 20, "width": 5, "height": 6},
        {"id": "r2", "x": 1,  "y": 2,  "width": 3, "height": 4},
    ])
    v.rois_df = df
    assert len(v._annotations) == 2
    assert all(a["kind"] == "rect" for a in v._annotations)
    out = v.rois_df
    assert list(out.columns) == ["id", "x", "y", "width", "height"]
    pd.testing.assert_frame_equal(
        out.reset_index(drop=True), df.reset_index(drop=True), check_dtype=False)


def test_polygons_df_setter_roundtrip():
    v = make_viewer()
    pts = [{"x": 0, "y": 0}, {"x": 1, "y": 1}, {"x": 2, "y": 0}]
    v.polygons_df = pd.DataFrame([{"id": "p1", "points": pts}])
    out = v.polygons_df
    assert list(out.columns) == ["id", "points", "num_vertices"]
    assert out.iloc[0]["num_vertices"] == 3
    assert out.iloc[0]["points"] == pts


def test_points_df_setter_roundtrip():
    v = make_viewer()
    v.points_df = pd.DataFrame([
        {"id": "pt1", "x": 7, "y": 8},
        {"id": "pt2", "x": 9, "y": 10},
    ])
    assert len(v._annotations) == 2
    assert all(a["kind"] == "point" for a in v._annotations)
    assert list(v.points_df.columns) == ["id", "x", "y"]


def test_mixed_kinds_dont_leak_between_views():
    v = make_viewer()
    v.rois_df = pd.DataFrame([{"id": "r1", "x": 0, "y": 0, "width": 1, "height": 1}])
    v.points_df = pd.DataFrame([{"id": "pt1", "x": 5, "y": 5}])
    assert len(v._annotations) == 2
    assert len(v.rois_df) == 1
    assert len(v.points_df) == 1
    assert v.polygons_df.empty


def test_clear_rois_preserves_other_kinds():
    v = make_viewer()
    v.rois_df = pd.DataFrame([{"id": "r1", "x": 0, "y": 0, "width": 1, "height": 1}])
    v.points_df = pd.DataFrame([{"id": "pt1", "x": 5, "y": 5}])
    v.clear_rois()
    assert v.rois_df.empty
    assert len(v.points_df) == 1


def test_clear_all_annotations():
    v = make_viewer()
    v.rois_df = pd.DataFrame([{"id": "r1", "x": 0, "y": 0, "width": 1, "height": 1}])
    v.points_df = pd.DataFrame([{"id": "pt1", "x": 5, "y": 5}])
    v.clear_all_annotations()
    assert v._annotations == []


def test_legacy_private_traitlets_removed():
    v = make_viewer()
    # These were private in Phase 1 and no longer exist as traitlets.
    assert "_rois_data" not in v.trait_names()
    assert "_polygons_data" not in v.trait_names()
    assert "_points_data" not in v.trait_names()


def test_annotation_entry_shape():
    v = make_viewer()
    v.rois_df = pd.DataFrame([{"id": "r1", "x": 2, "y": 3, "width": 4, "height": 5}])
    entry = v._annotations[0]
    assert entry["kind"] == "rect"
    assert entry["id"] == "r1"
    assert entry["geometry"] == [2, 3, 6, 8]   # [x0, y0, x1, y1]
    assert "t" in entry and "z" in entry
    assert "created_at" in entry
    assert "metadata" in entry
