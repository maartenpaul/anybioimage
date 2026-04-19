"""Annotations mixin for BioImageViewer.

Phase 2 [spec §5]: annotations are stored in a single `_annotations` traitlet.
This mixin exposes `.rois_df` / `.polygons_df` / `.points_df` as DataFrame views
filtered by `kind` so existing notebooks and other mixins (notably the SAM
integration that observes rectangle/point additions) keep working unchanged.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rect_entry(rec: dict[str, Any]) -> dict[str, Any]:
    x = float(rec["x"]); y = float(rec["y"])
    w = float(rec["width"]); h = float(rec["height"])
    return {
        "id": str(rec["id"]),
        "kind": "rect",
        "geometry": [x, y, x + w, y + h],
        "label": rec.get("label", ""),
        "color": rec.get("color", "#ff0000"),
        "visible": bool(rec.get("visible", True)),
        "t": int(rec.get("t", 0)),
        "z": int(rec.get("z", 0)),
        "created_at": rec.get("created_at") or _now_iso(),
        "metadata": dict(rec.get("metadata", {})),
    }


def _polygon_entry(rec: dict[str, Any]) -> dict[str, Any]:
    pts = rec["points"]
    if pts and isinstance(pts[0], dict):
        geom = [[float(p["x"]), float(p["y"])] for p in pts]
    else:
        geom = [[float(p[0]), float(p[1])] for p in pts]
    return {
        "id": str(rec["id"]),
        "kind": "polygon",
        "geometry": geom,
        "label": rec.get("label", ""),
        "color": rec.get("color", "#00ff00"),
        "visible": bool(rec.get("visible", True)),
        "t": int(rec.get("t", 0)),
        "z": int(rec.get("z", 0)),
        "created_at": rec.get("created_at") or _now_iso(),
        "metadata": dict(rec.get("metadata", {})),
    }


def _point_entry(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(rec["id"]),
        "kind": "point",
        "geometry": [float(rec["x"]), float(rec["y"])],
        "label": rec.get("label", ""),
        "color": rec.get("color", "#0066ff"),
        "visible": bool(rec.get("visible", True)),
        "t": int(rec.get("t", 0)),
        "z": int(rec.get("z", 0)),
        "created_at": rec.get("created_at") or _now_iso(),
        "metadata": dict(rec.get("metadata", {})),
    }


class AnnotationsMixin:
    """DataFrame-shaped views over the unified `_annotations` traitlet."""

    # ---- rect ----
    @property
    def rois_df(self) -> pd.DataFrame:
        rows = []
        for a in self._annotations:
            if a.get("kind") != "rect":
                continue
            x0, y0, x1, y1 = a["geometry"]
            rows.append({
                "id": a["id"], "x": x0, "y": y0,
                "width": x1 - x0, "height": y1 - y0,
            })
        if not rows:
            return pd.DataFrame(columns=["id", "x", "y", "width", "height"])
        return pd.DataFrame(rows)

    @rois_df.setter
    def rois_df(self, df: pd.DataFrame) -> None:
        others = [a for a in self._annotations if a.get("kind") != "rect"]
        new = [_rect_entry(r) for r in df.to_dict("records")]
        self._annotations = [*others, *new]

    # ---- polygon ----
    @property
    def polygons_df(self) -> pd.DataFrame:
        rows = []
        for a in self._annotations:
            if a.get("kind") != "polygon":
                continue
            pts = [{"x": x, "y": y} for x, y in a["geometry"]]
            rows.append({"id": a["id"], "points": pts, "num_vertices": len(pts)})
        if not rows:
            return pd.DataFrame(columns=["id", "points", "num_vertices"])
        return pd.DataFrame(rows)

    @polygons_df.setter
    def polygons_df(self, df: pd.DataFrame) -> None:
        others = [a for a in self._annotations if a.get("kind") != "polygon"]
        new = [_polygon_entry(r) for r in df.to_dict("records")]
        self._annotations = [*others, *new]

    # ---- point ----
    @property
    def points_df(self) -> pd.DataFrame:
        rows = []
        for a in self._annotations:
            if a.get("kind") != "point":
                continue
            x, y = a["geometry"]
            rows.append({"id": a["id"], "x": x, "y": y})
        if not rows:
            return pd.DataFrame(columns=["id", "x", "y"])
        return pd.DataFrame(rows)

    @points_df.setter
    def points_df(self, df: pd.DataFrame) -> None:
        others = [a for a in self._annotations if a.get("kind") != "point"]
        new = [_point_entry(r) for r in df.to_dict("records")]
        self._annotations = [*others, *new]

    # ---- bulk ops ----
    def clear_rois(self) -> None:
        self._annotations = [a for a in self._annotations if a.get("kind") != "rect"]

    def clear_polygons(self) -> None:
        self._annotations = [a for a in self._annotations if a.get("kind") != "polygon"]

    def clear_points(self) -> None:
        self._annotations = [a for a in self._annotations if a.get("kind") != "point"]

    def clear_all_annotations(self) -> None:
        self._annotations = []
        self.selected_annotation_id = ""
        self.selected_annotation_type = ""
