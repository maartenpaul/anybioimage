"""Chunk-bridge protocol tests for PixelSourceMixin."""
from __future__ import annotations

import numpy as np
import pytest

from anybioimage.mixins.pixel_source import PixelSourceMixin


class _Harness(PixelSourceMixin):
    """Minimal harness: no real traitlets, no anywidget."""

    def __init__(self, arr: np.ndarray) -> None:
        self._chunk_array = arr
        self._chunk_lru_cap = 8
        self._sent: list[tuple[dict, list]] = []
        super().__init__()

    def _send_chunk_response(self, msg: dict, buffers: list[bytes]) -> None:
        self._sent.append((msg, [bytes(b) for b in buffers]))


def test_chunk_ok_returns_raw_bytes_and_metadata() -> None:
    arr = np.arange(10 * 2 * 3 * 512 * 512, dtype=np.uint16).reshape(10, 2, 3, 512, 512)
    h = _Harness(arr)
    h.handle_chunk_request({
        "kind": "chunk", "requestId": 1, "t": 2, "c": 1, "z": 0, "level": 0,
        "tx": 0, "ty": 0, "tileSize": 512,
    })
    assert len(h._sent) == 1
    reply, bufs = h._sent[0]
    assert reply["kind"] == "chunk"
    assert reply["requestId"] == 1
    assert reply["ok"] is True
    assert reply["w"] == 512
    assert reply["h"] == 512
    assert reply["dtype"] == "uint16"
    # Raw bytes should equal the slice tobytes().
    expected = np.ascontiguousarray(arr[2, 1, 0, 0:512, 0:512]).tobytes()
    assert bufs[0] == expected


def test_chunk_edge_tile_clipped_to_array_bounds() -> None:
    arr = np.zeros((1, 1, 1, 600, 600), dtype=np.uint8)
    h = _Harness(arr)
    h.handle_chunk_request({
        "kind": "chunk", "requestId": 7, "t": 0, "c": 0, "z": 0, "level": 0,
        "tx": 1, "ty": 1, "tileSize": 512,
    })
    reply, bufs = h._sent[0]
    assert reply["ok"] is True
    assert reply["w"] == 600 - 512  # 88
    assert reply["h"] == 88
    assert len(bufs[0]) == 88 * 88


def test_chunk_out_of_bounds_returns_error() -> None:
    arr = np.zeros((1, 1, 1, 100, 100), dtype=np.uint8)
    h = _Harness(arr)
    h.handle_chunk_request({
        "kind": "chunk", "requestId": 3, "t": 0, "c": 0, "z": 0, "level": 0,
        "tx": 99, "ty": 99, "tileSize": 512,
    })
    reply, bufs = h._sent[0]
    assert reply["ok"] is False
    assert "out of bounds" in reply["error"].lower()
    assert bufs == []


def test_lru_cache_bounded_and_hits_on_repeat() -> None:
    arr = np.zeros((1, 1, 1, 2048, 2048), dtype=np.uint16)
    h = _Harness(arr)
    h._chunk_lru_cap = 4
    for i in range(6):
        h.handle_chunk_request({
            "kind": "chunk", "requestId": i, "t": 0, "c": 0, "z": 0, "level": 0,
            "tx": i, "ty": 0, "tileSize": 512,
        })
    assert len(h._chunk_cache) == 4  # bounded

    # Re-request an evicted one, cache should miss (length stays at cap).
    h.handle_chunk_request({
        "kind": "chunk", "requestId": 99, "t": 0, "c": 0, "z": 0, "level": 0,
        "tx": 0, "ty": 0, "tileSize": 512,
    })
    assert len(h._chunk_cache) == 4

    # Re-request a present one, should be served from cache (no shape change).
    before = dict(h._chunk_cache)
    h.handle_chunk_request({
        "kind": "chunk", "requestId": 100, "t": 0, "c": 0, "z": 0, "level": 0,
        "tx": 5, "ty": 0, "tileSize": 512,
    })
    assert h._chunk_cache is not before  # same object mutated, content differs
