"""Chunk-bridge handler — the Python side of AnywidgetPixelSource.

JS asks for (t, c, z, level, tx, ty, tileSize); we slice from an in-RAM numpy
array (or lazy bioio reader in a follow-up subclass) and reply with raw bytes
in anywidget buffers.

No PNG encoding, no base64. Dtype is preserved verbatim.

A bounded LRU (default 256 tiles) smooths repeat requests during Z/T scrubbing.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Any

import numpy as np

_CHUNK_LRU_DEFAULT = 256


class PixelSourceMixin:
    """Mixin — must be combined with something that can actually send messages.

    Consumers set `_chunk_array` (TCZYX numpy) or override `_read_tile_raw()`.
    `_send_chunk_response(msg, buffers)` is the one transport seam the mixin
    requires; BioImageViewer implements it as `self.send(msg, buffers)`.
    """

    _chunk_array: np.ndarray | None = None
    _chunk_lru_cap: int = _CHUNK_LRU_DEFAULT

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._chunk_cache: OrderedDict[tuple, bytes] = OrderedDict()

    # ---- transport seam ----
    def _send_chunk_response(self, msg: dict, buffers: list[bytes]) -> None:
        """Default: no transport — subclasses override. Tests use a harness override."""
        raise NotImplementedError

    # ---- tile read ----
    def _read_tile_raw(self, t: int, c: int, z: int, level: int,
                       tx: int, ty: int, tile: int) -> tuple[np.ndarray, str]:
        """Return (view, dtype_str) — partial edge tiles are NOT padded.

        Viv's MultiscaleImageLayer detects partial tiles via
        ``data.height < base.tileSize`` and adjusts sublayer bounds
        accordingly, so we return the raw clipped extent.

        Raises IndexError for tiles whose origin is past the image extent.
        """
        arr = self._chunk_array
        if arr is None:
            raise IndexError("no chunk array set")
        if level != 0:
            step = 2 ** level
            y0 = ty * tile * step
            x0 = tx * tile * step
            if y0 >= arr.shape[3] or x0 >= arr.shape[4]:
                raise IndexError("tile out of bounds")
            y1 = min(y0 + tile * step, arr.shape[3])
            x1 = min(x0 + tile * step, arr.shape[4])
            sub = arr[t, c, z, y0:y1:step, x0:x1:step]
        else:
            y0 = ty * tile
            x0 = tx * tile
            if y0 >= arr.shape[3] or x0 >= arr.shape[4]:
                raise IndexError("tile out of bounds")
            y1 = min(y0 + tile, arr.shape[3])
            x1 = min(x0 + tile, arr.shape[4])
            sub = arr[t, c, z, y0:y1, x0:x1]
        if not sub.flags["C_CONTIGUOUS"]:
            sub = np.ascontiguousarray(sub)
        return sub, str(sub.dtype)

    # ---- public entry point ----
    def handle_chunk_request(self, payload: dict) -> None:
        """Dispatch a `{kind:"chunk",...}` message from JS."""
        request_id = int(payload.get("requestId", -1))
        try:
            t = int(payload["t"])
            c = int(payload["c"])
            z = int(payload["z"])
            level = int(payload.get("level", 0))
            tx = int(payload["tx"])
            ty = int(payload["ty"])
            tile = int(payload.get("tileSize", 512))
        except (KeyError, TypeError, ValueError) as exc:
            self._send_chunk_response(
                {"kind": "chunk", "requestId": request_id, "ok": False,
                 "error": f"bad payload: {exc}"}, [])
            return

        key = (t, c, z, level, tx, ty, tile)
        cached = self._chunk_cache.get(key)
        if cached is not None:
            # LRU touch.
            self._chunk_cache.move_to_end(key)
            self._send_chunk_response(
                {"kind": "chunk", "requestId": request_id, "ok": True,
                 "w": cached[1], "h": cached[2], "dtype": cached[3]},
                [cached[0]])
            return

        try:
            arr, dtype_str = self._read_tile_raw(t, c, z, level, tx, ty, tile)
        except IndexError as exc:
            self._send_chunk_response(
                {"kind": "chunk", "requestId": request_id, "ok": False,
                 "error": f"tile out of bounds: {exc}"}, [])
            return
        except Exception as exc:  # pragma: no cover — defensive
            self._send_chunk_response(
                {"kind": "chunk", "requestId": request_id, "ok": False,
                 "error": f"{type(exc).__name__}: {exc}"}, [])
            return

        h, w = arr.shape[:2]
        raw = arr.tobytes()
        # Cache with (raw, w, h, dtype) tuple so the LRU entry is self-describing.
        self._chunk_cache[key] = (raw, w, h, dtype_str)
        while len(self._chunk_cache) > self._chunk_lru_cap:
            self._chunk_cache.popitem(last=False)

        self._send_chunk_response(
            {"kind": "chunk", "requestId": request_id, "ok": True,
             "w": w, "h": h, "dtype": dtype_str}, [raw])
