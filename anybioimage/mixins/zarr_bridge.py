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

import functools
import itertools
import logging
import queue
import threading
from collections import OrderedDict

import numpy as np

from .. import ngff
from .image_loading import _channel_settings_from_omero

logger = logging.getLogger(__name__)

DEFAULT_CACHE_BYTES = 256 * 1024 ** 2
_VIV_DTYPES = {"uint8", "uint16", "uint32", "float32"}
_SPATIAL = ("y", "x")

TileKey = tuple  # cache key: (gen, level, t, c, z, ty, tx); read_tile_block emits it without gen
TileValue = tuple  # (w, h, bytes)


BRIDGE_WORKERS = 4


def make_bridge_thread(target, name: str) -> threading.Thread:
    """A daemon thread that can talk to the frontend from wherever we are running.

    Under marimo the runtime context is a ``threading.local``: a widget message
    sent from a plain worker thread is dropped silently (``MarimoComm._broadcast``
    swallows ``ContextNotInitializedError``), so the browser never sees the tile.
    ``marimo.Thread`` clones the kernel's runtime context into the new thread, so
    replies get through — but it must be CONSTRUCTED on a thread that already has
    a context, i.e. the kernel thread handling the message.

    Falls back to a plain thread outside marimo (Jupyter's IOPub is thread-safe)
    and if marimo refuses to clone its context here.
    """
    try:
        import marimo
        from marimo._runtime.context.types import runtime_context_installed

        if runtime_context_installed():
            thread = marimo.Thread(target=target, name=name, daemon=True)
            logger.debug("bridge worker %s: marimo.Thread", name)
            return thread
    except Exception as e:  # marimo absent, or it declined to clone the context
        logger.debug("bridge worker %s: plain thread (%s)", name, e)
    return threading.Thread(target=target, name=name, daemon=True)


class _BridgeWorkers:
    """Lazily spawned pool of daemon workers draining a job queue.

    Workers are spawned by ``submit`` — which runs on the kernel thread, the only
    place ``make_bridge_thread`` can clone marimo's runtime context. A worker
    whose ``should_exit`` flips (marimo invalidates the cell that spawned it) is
    replaced on the next submit, and re-queues the job it was holding.
    """

    def __init__(self, n_workers: int = BRIDGE_WORKERS, thread_factory=make_bridge_thread):
        self._n = int(n_workers)
        self._factory = thread_factory
        self._queue: queue.Queue = queue.Queue()
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._closed = False

    def submit(self, fn) -> None:
        if self._closed:
            return
        self._queue.put(fn)
        self._ensure_workers()

    def _ensure_workers(self) -> None:
        """Prune dead/exiting workers and top the pool back up. Kernel thread only."""
        with self._lock:
            if self._closed:
                return
            self._threads = [
                t for t in self._threads
                if t.is_alive() and not getattr(t, "should_exit", False)
            ]
            missing = self._n - len(self._threads)
            new = [self._factory(self._run, f"zarr-bridge-{i}") for i in range(missing)]
            self._threads.extend(new)
        for t in new:
            t.start()

    def _run(self) -> None:
        me = threading.current_thread()
        while True:
            job = self._queue.get()
            if job is None:
                return
            if getattr(me, "should_exit", False):
                self._queue.put(job)  # a replacement worker will pick it up
                return
            try:
                job()
            except Exception:
                logger.exception("bridge worker job failed")

    def shutdown(self) -> None:
        with self._lock:
            self._closed = True
            n = len(self._threads)
        for _ in range(max(n, 1)):
            self._queue.put(None)

    @property
    def threads(self) -> list[threading.Thread]:
        return list(self._threads)


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
    for ax, pos in (("t", t), ("c", c), ("z", z)):
        if ax not in axes and int(pos) != 0:
            raise IndexError(f"{ax}={pos} but store has no {ax} axis")
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


_RANGE_SAMPLE_MAX_PIXELS = 4 * 1024 * 1024


def _default_channel_ranges(img: ngff.NgffImage, dim_c: int) -> list[tuple[float, float]]:
    """Per-channel (min, max) from the lowest pyramid level at t=0, z=middle.

    Only used when the store has no ``omero`` block. Returns [] (caller keeps
    the dtype range) when the lowest level is still bigger than 4 MP.
    """
    arr = img.levels[-1]
    axes = img.axes
    shape = tuple(int(s) for s in arr.shape)
    if shape[axes.index("y")] * shape[axes.index("x")] > _RANGE_SAMPLE_MAX_PIXELS:
        return []
    idx: list = []
    for i, ax in enumerate(axes):
        if ax in _SPATIAL or ax == "c":
            idx.append(slice(None))
        elif ax == "z":
            idx.append(shape[i] // 2)
        else:
            idx.append(0)
    data = np.asarray(arr[tuple(idx)])
    if "c" in axes:
        c_axis = [ax for ax in axes if ax in ("c", "y", "x")].index("c")
        data = np.moveaxis(data, c_axis, 0)
    else:
        data = data[None]
    out = []
    for ci in range(dim_c):
        plane = data[min(ci, data.shape[0] - 1)]
        out.append((float(plane.min()), float(plane.max())))
    return out


def _block_key(img: ngff.NgffImage, level: int, t: int, c: int, z: int, tx: int, ty: int) -> tuple:
    """Identity of the zarr chunk block a tile request will read (for in-flight dedupe)."""
    arr = img.levels[level]
    chunks = tuple(int(k) for k in arr.chunks)
    wanted = {"t": t, "c": c, "z": z}
    parts = [level, tx, ty]
    for i, ax in enumerate(img.axes):
        if ax in _SPATIAL:
            continue
        pos = int(wanted.get(ax, 0))
        parts.append(pos // chunks[i] if ax in wanted else 0)
    return tuple(parts)


class ZarrBridgeMixin:
    """Serve tiles of an ``NgffImage`` to the Viv frontend over ``model.send``.

    Attributes expected from the host widget: ``_zarr_source``, ``dim_*``,
    ``height``, ``width``, ``current_t``, ``current_z``, ``_channel_settings``,
    ``image_data``, ``_render_ready``, ``bridge_cache_bytes``, ``_precompute_event``,
    ``_precompute_future``, ``_full_array``, ``_bioimage``, ``send``, ``on_msg``.
    """

    def _init_bridge(self) -> None:
        self._bridge_image: ngff.NgffImage | None = None
        self._bridge_dtype = np.dtype("uint16")
        # Bumped on every attach/detach; part of every cache and in-flight key so
        # a worker still reading the previous image can never publish its tiles
        # into the new image's cache.
        self._bridge_gen = 0
        self._bridge_cache = BridgeCache(int(getattr(self, "bridge_cache_bytes", DEFAULT_CACHE_BYTES)))
        self._bridge_workers = _BridgeWorkers()
        self._bridge_send_lock = threading.Lock()
        self._bridge_inflight: dict[tuple, threading.Event] = {}
        self._bridge_inflight_lock = threading.Lock()
        self.on_msg(self._on_bridge_msg)
        self.observe(self._on_bridge_cache_bytes, names=["bridge_cache_bytes"])

    def _close_bridge(self) -> None:
        workers = getattr(self, "_bridge_workers", None)
        if workers is not None:
            workers.shutdown()
        self._detach_bridge()

    def _on_bridge_cache_bytes(self, change) -> None:
        self._bridge_cache.set_max_bytes(int(change["new"]))

    # ---- attach / detach -------------------------------------------------

    def _attach_bridge(self, img: ngff.NgffImage) -> None:
        """Point the viv frontend at ``img`` via the chunk bridge."""
        out_dtype = viv_dtype(img.dtype)
        if out_dtype != img.dtype:
            logger.warning("dtype %s not GPU-uploadable; serving as float32", img.dtype)

        if getattr(self, "_precompute_event", None) is not None:
            self._precompute_event.set()
        self._precompute_future = None
        self._full_array = None
        self._bioimage = None
        self._swap_bridge_image(img, out_dtype)

        dim_c = img.size("c")
        channels = _channel_settings_from_omero({"omero": {"channels": img.omero_channels}}, dim_c, out_dtype)
        if not img.omero_channels:
            for ch, (lo, hi) in zip(channels, _default_channel_ranges(img, dim_c)):
                if hi > lo:
                    ch["data_min"], ch["data_max"] = lo, hi
                    ch["min"], ch["max"] = 0.0, 1.0

        with self.hold_trait_notifications():
            self.dim_t = img.size("t")
            self.dim_c = dim_c
            self.dim_z = img.size("z")
            self.height = img.size("y")
            self.width = img.size("x")
            self.current_t = 0
            self.current_z = 0
            self._channel_settings = channels
            self.image_data = ""
            self._render_ready = False
        self._zarr_source = {
            "mode": "bridge",
            "levels": [{"shape": [int(s) for s in a.shape], "chunks": [int(k) for k in a.chunks]}
                       for a in img.levels],
            "labels": list(img.axes),
            "dtype": out_dtype.name,
        }
        logger.info("Viv backend: kernel chunk bridge attached (%d levels, %s)", len(img.levels), out_dtype.name)

    def _swap_bridge_image(self, img: ngff.NgffImage | None, dtype: np.dtype) -> None:
        """Atomically retire the current image: bump the generation, install
        ``img``, drop the cache and wake every in-flight waiter.

        Waiters wake to a cache miss and re-read for themselves; their leader's
        ``put_many`` is dropped because its generation no longer matches.
        """
        with self._bridge_inflight_lock:
            self._bridge_gen += 1
            self._bridge_image = img
            self._bridge_dtype = dtype
            self._bridge_cache.clear()
            stale = list(self._bridge_inflight.values())
            self._bridge_inflight.clear()
        for ev in stale:
            ev.set()

    def _detach_bridge(self) -> None:
        """Forget the bridged image (called when a non-bridge image is loaded)."""
        if getattr(self, "_bridge_cache", None) is None:
            return
        self._swap_bridge_image(None, self._bridge_dtype)

    # ---- message handling ------------------------------------------------

    def _on_bridge_msg(self, widget, content, buffers) -> None:
        if not isinstance(content, dict) or content.get("kind") != "chunk":
            return
        if self._bridge_image is None:
            with self._bridge_send_lock:
                self.send({"kind": "chunk", "requestId": content.get("requestId"),
                           "ok": False, "error": "no bridged image attached"})
            return
        self._bridge_workers.submit(functools.partial(self._serve_chunk, content))

    def _serve_chunk(self, req: dict) -> None:
        rid = req.get("requestId")
        try:
            with self._bridge_inflight_lock:
                img, gen, dtype = self._bridge_image, self._bridge_gen, self._bridge_dtype
            if img is None:
                raise RuntimeError("no bridged image attached")
            key = (int(req.get("level", 0)), int(req.get("t", 0)), int(req.get("c", 0)),
                   int(req.get("z", 0)), int(req["ty"]), int(req["tx"]))
            w, h, data = self._bridge_tile(img, gen, key, int(req.get("tileSize", 512)), dtype)
            reply = {"kind": "chunk", "requestId": rid, "ok": True, "w": w, "h": h,
                     "dtype": dtype.name}
            with self._bridge_send_lock:
                self.send(reply, buffers=[data])
        except Exception as e:
            logger.debug("chunk request %r failed: %s", req, e)
            with self._bridge_send_lock:
                self.send({"kind": "chunk", "requestId": rid, "ok": False, "error": f"{type(e).__name__}: {e}"})

    def _bridge_tile(self, img: ngff.NgffImage, gen: int, key: tuple, tile_size: int,
                     dtype: np.dtype) -> TileValue:
        """Serve ``(level, t, c, z, ty, tx)`` of ``img``, whose generation is ``gen``."""
        ckey = (gen,) + key
        hit = self._bridge_cache.get(ckey)
        if hit is not None:
            return hit
        level, t, c, z, ty, tx = key
        if level < 0 or level >= len(img.levels):
            raise IndexError(f"level {level} out of range")
        # In-flight dedupe: a burst of sibling requests (Viv asks for many
        # planes of one chunk per frame) must decode the block only once.
        bkey = (gen,) + _block_key(img, level, t, c, z, tx, ty)
        with self._bridge_inflight_lock:
            ev = self._bridge_inflight.get(bkey)
            leader = ev is None
            if leader:
                ev = self._bridge_inflight[bkey] = threading.Event()
        if not leader:
            ev.wait()
            hit = self._bridge_cache.get(ckey)
            if hit is not None:
                return hit
            # Leader failed, the image was swapped, or the block was evicted /
            # too big to cache — read ourselves.
        try:
            tiles = read_tile_block(img, level, t, c, z, tx, ty, tile_size, dtype,
                                    max_block_bytes=self._bridge_cache.max_bytes)
            # Publish only while this generation is still current, under the same
            # lock _swap_bridge_image clears the cache with.
            with self._bridge_inflight_lock:
                if self._bridge_gen == gen:
                    self._bridge_cache.put_many(((gen,) + k, v) for k, v in tiles.items())
            return tiles[key]
        finally:
            if leader:
                with self._bridge_inflight_lock:
                    self._bridge_inflight.pop(bkey, None)
                ev.set()
