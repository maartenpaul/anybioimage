"""Kernel-side chunk bridge: serves per-level tiles of an ``NgffImage`` to Viv.

Protocol (anywidget custom messages):
  JS → Py  {"kind": "chunk", "requestId": int, "level": int, "t": int, "c": int, "z": int,
            "tx": int, "ty": int, "tileSize": int}
  Py → JS  {"kind": "chunk", "requestId": int, "ok": true, "w": int, "h": int, "dtype": str}
           + buffers=[raw native-endian C-order bytes (little-endian on all supported platforms), h*w elements]
        or {"kind": "chunk", "requestId": int, "ok": false, "error": str}

Performance rule: zarr decodes whole chunks, so a tile read costs the same as
reading every T/C/Z plane inside that chunk. ``read_tile_block`` therefore
reads the enclosing chunk block once and returns one tile per plane it covers;
the byte-budgeted ``BridgeCache`` keeps them for the next requests.
"""
from __future__ import annotations

import itertools
import logging
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from .. import ngff
from .image_loading import _channel_settings_from_omero

logger = logging.getLogger(__name__)

DEFAULT_CACHE_BYTES = 256 * 1024 ** 2
_VIV_DTYPES = {"uint8", "uint16", "uint32", "float32"}
_SPATIAL = ("y", "x")

TileKey = tuple  # (level, t, c, z, ty, tx)
TileValue = tuple  # (w, h, bytes)


def viv_dtype(dtype) -> np.dtype:
    """Native-endian dtype Viv can upload: uint8/16/32 or float32; others → float32."""
    dt = np.dtype(dtype).newbyteorder("=")
    return dt if dt.name in _VIV_DTYPES else np.dtype("float32")


class BridgeCache:
    """Thread-safe LRU of tiles bounded by total payload bytes.

    Eviction never removes the most recently inserted entry, so a block larger
    than the budget still serves the tile that triggered it.
    """

    def __init__(self, max_bytes: int = DEFAULT_CACHE_BYTES):
        self.max_bytes = int(max_bytes)
        self._d: OrderedDict[TileKey, TileValue] = OrderedDict()
        self.nbytes = 0
        self._lock = threading.Lock()

    def get(self, key: TileKey) -> TileValue | None:
        with self._lock:
            val = self._d.get(key)
            if val is not None:
                self._d.move_to_end(key)
            return val

    def put_many(self, items) -> None:
        with self._lock:
            for key, val in items:
                old = self._d.pop(key, None)
                if old is not None:
                    self.nbytes -= len(old[2])
                self._d[key] = val
                self.nbytes += len(val[2])
            self._evict_locked()

    def set_max_bytes(self, max_bytes: int) -> None:
        with self._lock:
            self.max_bytes = int(max_bytes)
            self._evict_locked()

    def _evict_locked(self) -> None:
        while self.nbytes > self.max_bytes and len(self._d) > 1:
            _, old = self._d.popitem(last=False)
            self.nbytes -= len(old[2])

    def clear(self) -> None:
        with self._lock:
            self._d.clear()
            self.nbytes = 0

    def __len__(self) -> int:
        return len(self._d)


def read_tile_block(img: ngff.NgffImage, level: int, t: int, c: int, z: int,
                    tx: int, ty: int, tile_size: int, out_dtype: np.dtype,
                    max_block_bytes: int) -> dict[TileKey, TileValue]:
    """Read tile ``(tx, ty)`` of ``level`` plus every sibling plane sharing its zarr chunk.

    Returns ``{(level, t, c, z, ty, tx): (w, h, bytes)}``. Absent axes index as
    0. Raises ``IndexError`` when the tile or the t/c/z position is out of
    range. If the enclosing block would exceed ``max_block_bytes`` only the
    requested plane is read.
    """
    if tile_size <= 0:
        raise ValueError(f"tile_size must be positive, got {tile_size}")
    if level < 0 or level >= len(img.levels):
        raise IndexError(f"level {level} out of range")
    arr = img.levels[level]
    axes, shape, chunks = img.axes, tuple(int(s) for s in arr.shape), tuple(int(k) for k in arr.chunks)
    yi, xi = axes.index("y"), axes.index("x")
    y0, x0 = ty * tile_size, tx * tile_size
    if y0 >= shape[yi] or x0 >= shape[xi] or tx < 0 or ty < 0:
        raise IndexError(f"tile ({tx},{ty}) outside level {level} ({shape[xi]}x{shape[yi]})")
    y1, x1 = min(y0 + tile_size, shape[yi]), min(x0 + tile_size, shape[xi])
    wanted = {"t": t, "c": c, "z": z}

    # Non-spatial axes: read the full chunk span so siblings come for free.
    ranges: list[tuple[int, int]] = []          # (start, stop) per axis, spatial = tile extent
    block_elems = (y1 - y0) * (x1 - x0)
    for i, ax in enumerate(axes):
        if ax == "y":
            ranges.append((y0, y1))
        elif ax == "x":
            ranges.append((x0, x1))
        elif ax in wanted:
            pos = int(wanted[ax])
            if pos < 0 or pos >= shape[i]:
                raise IndexError(f"{ax}={pos} outside level {level} extent {shape[i]}")
            start = (pos // chunks[i]) * chunks[i]
            stop = min(start + chunks[i], shape[i])
            ranges.append((start, stop))
            block_elems *= stop - start
        else:
            # Unknown non-spatial axis (e.g. ndim>5 leading dims): pin to 0, no span.
            ranges.append((0, 1))
    src_itemsize = max(np.dtype(arr.dtype).itemsize, out_dtype.itemsize)
    if block_elems * src_itemsize > max_block_bytes:
        ranges = [(int(wanted.get(ax, 0)), int(wanted.get(ax, 0)) + 1) if ax not in _SPATIAL else r
                  for ax, r in zip(axes, ranges)]

    block = np.asarray(arr[tuple(slice(a, b) for a, b in ranges)])
    block = block.astype(out_dtype, copy=False)

    non_spatial = [i for i, ax in enumerate(axes) if ax not in _SPATIAL]
    out: dict[TileKey, TileValue] = {}
    w, h = x1 - x0, y1 - y0
    for combo in itertools.product(*[range(ranges[i][0], ranges[i][1]) for i in non_spatial]):
        idx: list = [slice(None)] * len(axes)
        pos = {"t": 0, "c": 0, "z": 0}
        for i, val in zip(non_spatial, combo):
            idx[i] = val - ranges[i][0]
            pos[axes[i]] = val
        plane = block[tuple(idx)]
        out[(level, pos["t"], pos["c"], pos["z"], ty, tx)] = (w, h, plane.tobytes())
    return out
