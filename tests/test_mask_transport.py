"""Mask-bytes transport — Python side sends raw RGBA via anywidget buffers."""
from __future__ import annotations

import numpy as np
import pytest

from anybioimage import BioImageViewer


class RecordingViewer(BioImageViewer):
    """Captures `send()` calls into a buffer-aware recorder."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.sent_messages = []

    def send(self, msg, buffers=None):  # type: ignore[override]
        self.sent_messages.append((dict(msg), list(buffers or [])))


def test_add_mask_populates_metadata_only():
    v = RecordingViewer()
    labels = np.zeros((64, 64), dtype=np.uint16)
    labels[16:32, 16:32] = 1
    mid = v.add_mask(labels, name="m1", opacity=0.7)
    entry = v._masks_data[-1]
    assert entry["id"] == mid
    assert entry["name"] == "m1"
    assert entry["visible"] is True
    assert entry["opacity"] == 0.7
    assert entry["width"] == 64
    assert entry["height"] == 64
    assert "data" not in entry                 # raw bytes no longer inline
    # Bytes are stored in a dict on the Python side.
    assert v._mask_bytes[mid]
    assert len(v._mask_bytes[mid]) == 64 * 64 * 4


def test_mask_request_dispatches_bytes():
    v = RecordingViewer()
    labels = np.zeros((10, 10), dtype=np.uint16)
    labels[0, 0] = 1
    mid = v.add_mask(labels)
    v.sent_messages.clear()
    v._route_message(v, {"kind": "mask_request", "id": mid}, [])
    assert v.sent_messages, "expected a send() call"
    msg, buffers = v.sent_messages[0]
    assert msg["kind"] == "mask"
    assert msg["id"] == mid
    assert msg["width"] == 10
    assert msg["height"] == 10
    assert msg["dtype"] == "uint8"
    assert len(buffers) == 1
    assert len(buffers[0]) == 10 * 10 * 4


def test_update_contours_regenerates_bytes():
    v = RecordingViewer()
    labels = np.zeros((20, 20), dtype=np.uint16)
    labels[5:15, 5:15] = 1
    mid = v.add_mask(labels)
    v.sent_messages.clear()
    before_bytes = v._mask_bytes[mid]
    v.update_mask_settings(mid, contours=True, contour_width=2)
    after_bytes = v._mask_bytes[mid]
    assert before_bytes != after_bytes
    # A `mask` message is automatically pushed so the frontend does not need to re-request.
    kinds = [m[0]["kind"] for m in v.sent_messages]
    assert "mask" in kinds


def test_remove_mask_clears_bytes():
    v = RecordingViewer()
    labels = np.zeros((8, 8), dtype=np.uint16)
    mid = v.add_mask(labels)
    assert mid in v._mask_bytes
    v.remove_mask(mid)
    assert mid not in v._mask_bytes
    assert mid not in [m["id"] for m in v._masks_data]
