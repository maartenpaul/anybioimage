"""SAM integration protocol — Phase 2 [spec §5].

Covers the JS → Py routing for sam_rect / sam_point without requiring an
actual SAM model. We monkey-patch the per-kind handlers to assert they are
called with the right shape; the SAM model itself is exercised separately.
"""
from __future__ import annotations

from anybioimage import BioImageViewer


class _Probe(BioImageViewer):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.rect_calls = []
        self.point_calls = []
        # Pretend SAM is enabled without loading the model.
        self._sam_enabled = True
        self.sam_enabled = True

    def _on_rois_changed(self, change):
        self.rect_calls.append(change["new"])

    def _on_points_changed(self, change):
        self.point_calls.append(change["new"])


def test_sam_rect_is_routed():
    v = _Probe()
    v._route_message(v, {"kind": "sam_rect", "id": "ab", "x": 1, "y": 2,
                          "width": 3, "height": 4, "t": 0, "z": 0}, [])
    assert v.rect_calls == [[{"id": "ab", "x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0}]]


def test_sam_point_is_routed():
    v = _Probe()
    v._route_message(v, {"kind": "sam_point", "id": "pp", "x": 5, "y": 6, "t": 0, "z": 0}, [])
    assert v.point_calls == [[{"id": "pp", "x": 5.0, "y": 6.0}]]


def test_sam_disabled_does_not_route():
    v = _Probe()
    v._sam_enabled = False
    v.sam_enabled = False
    v._route_message(v, {"kind": "sam_rect", "id": "ab", "x": 1, "y": 2,
                          "width": 3, "height": 4, "t": 0, "z": 0}, [])
    assert v.rect_calls == []
