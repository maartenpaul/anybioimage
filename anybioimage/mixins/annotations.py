"""Annotations mixin for BioImageViewer."""

import pandas as pd


class AnnotationsMixin:
    """Mixin class providing annotation management for BioImageViewer.

    Attributes expected to be defined by the main class:
        - _rois_data: List of ROI dicts (traitlet)
        - _polygons_data: List of polygon dicts (traitlet)
        - _points_data: List of point dicts (traitlet)
        - selected_annotation_id: Selected annotation ID (traitlet)
        - selected_annotation_type: Selected annotation type (traitlet)
    """

    @property
    def rois_df(self) -> pd.DataFrame:
        if not self._rois_data:
            return pd.DataFrame(columns=["id", "x", "y", "width", "height", "t", "z"])
        return pd.DataFrame(self._rois_data)

    @rois_df.setter
    def rois_df(self, df: pd.DataFrame):
        records = df.to_dict("records")
        for r in records:
            r.setdefault("t", 0)
            r.setdefault("z", 0)
        self._rois_data = records

    @property
    def polygons_df(self) -> pd.DataFrame:
        if not self._polygons_data:
            return pd.DataFrame(columns=["id", "points", "num_vertices", "t", "z"])
        data = []
        for poly in self._polygons_data:
            data.append({
                "id": poly["id"],
                "points": poly["points"],
                "num_vertices": len(poly["points"]),
                "t": poly.get("t", 0),
                "z": poly.get("z", 0),
            })
        return pd.DataFrame(data)

    @polygons_df.setter
    def polygons_df(self, df: pd.DataFrame):
        records = df.to_dict("records")
        self._polygons_data = [
            {
                "id": r["id"],
                "points": r["points"],
                "t": r.get("t", 0),
                "z": r.get("z", 0),
            }
            for r in records
        ]

    @property
    def points_df(self) -> pd.DataFrame:
        if not self._points_data:
            return pd.DataFrame(columns=["id", "x", "y", "t", "z"])
        return pd.DataFrame(self._points_data)

    @points_df.setter
    def points_df(self, df: pd.DataFrame):
        records = df.to_dict("records")
        for r in records:
            r.setdefault("t", 0)
            r.setdefault("z", 0)
        self._points_data = records

    def clear_rois(self):
        self._rois_data = []

    def clear_polygons(self):
        self._polygons_data = []

    def clear_points(self):
        self._points_data = []

    def clear_all_annotations(self):
        self.clear_rois()
        self.clear_polygons()
        self.clear_points()
        self.selected_annotation_id = ""
        self.selected_annotation_type = ""
