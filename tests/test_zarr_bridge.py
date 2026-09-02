"""Kernel-side chunk bridge: tile reads, chunk-block prefill, byte-budget LRU."""
import numpy as np
import pytest

from anybioimage import ngff
from anybioimage.mixins import zarr_bridge as zb


class FakeArray:
    """Minimal zarr.Array stand-in: shape/chunks/__getitem__ plus a read counter."""

    def __init__(self, data, chunks):
        self.data, self.chunks, self.reads = data, tuple(chunks), 0

    @property
    def shape(self):
        return self.data.shape

    @property
    def ndim(self):
        return self.data.ndim

    @property
    def dtype(self):
        return self.data.dtype

    def __getitem__(self, idx):
        self.reads += 1
        return self.data[idx]


def _img(data, chunks, axes):
    arr = FakeArray(data, chunks)
    return ngff.NgffImage(group=None, version="0.4", axes=list(axes), levels=[arr],
                          dtype=np.dtype(data.dtype).newbyteorder("="), omero_channels=[]), arr


def test_viv_dtype_mapping():
    assert zb.viv_dtype(">u2") == np.dtype("uint16") and zb.viv_dtype(">u2").isnative
    assert zb.viv_dtype("uint8") == np.dtype("uint8")
    assert zb.viv_dtype("float64") == np.dtype("float32")
    assert zb.viv_dtype("int16") == np.dtype("float32")


def test_read_tile_block_fills_all_siblings_in_chunk():
    data = (np.arange(4 * 2 * 3 * 64 * 64) % 1000).astype(">u2").reshape(4, 2, 3, 64, 64)
    img, arr = _img(data, chunks=(4, 1, 3, 32, 32), axes="tczyx")
    tiles = zb.read_tile_block(img, level=0, t=1, c=1, z=2, tx=1, ty=0, tile_size=32,
                               out_dtype=np.dtype("uint16"), max_block_bytes=1 << 30)
    assert arr.reads == 1
    # chunk spans all 4 t and all 3 z, but only c=1 → 12 tiles
    assert len(tiles) == 12
    assert set(k[1] for k in tiles) == {0, 1, 2, 3} and set(k[2] for k in tiles) == {1}
    w, h, raw = tiles[(0, 1, 1, 2, 0, 1)]
    assert (w, h) == (32, 32)
    expect = np.ascontiguousarray(data[1, 1, 2, 0:32, 32:64].astype("<u2"))
    assert raw == expect.tobytes()


def test_read_tile_block_edge_tile_is_partial():
    data = np.zeros((1, 1, 1, 40, 70), dtype=np.uint16)
    img, _ = _img(data, chunks=(1, 1, 1, 32, 32), axes="tczyx")
    tiles = zb.read_tile_block(img, 0, 0, 0, 0, tx=2, ty=1, tile_size=32,
                               out_dtype=np.dtype("uint16"), max_block_bytes=1 << 30)
    w, h, raw = tiles[(0, 0, 0, 0, 1, 2)]
    assert (w, h) == (6, 8) and len(raw) == 6 * 8 * 2


def test_read_tile_block_out_of_range_raises():
    data = np.zeros((1, 1, 1, 32, 32), dtype=np.uint16)
    img, _ = _img(data, chunks=(1, 1, 1, 32, 32), axes="tczyx")
    with pytest.raises(IndexError):
        zb.read_tile_block(img, 0, 0, 0, 0, tx=5, ty=0, tile_size=32,
                           out_dtype=np.dtype("uint16"), max_block_bytes=1 << 30)
    with pytest.raises(IndexError):
        zb.read_tile_block(img, 0, t=3, c=0, z=0, tx=0, ty=0, tile_size=32,
                           out_dtype=np.dtype("uint16"), max_block_bytes=1 << 30)


def test_read_tile_block_axes_without_t_and_c():
    data = np.arange(2 * 16 * 16, dtype=np.uint8).reshape(2, 16, 16)
    img, arr = _img(data, chunks=(2, 16, 16), axes="zyx")
    tiles = zb.read_tile_block(img, 0, t=0, c=0, z=1, tx=0, ty=0, tile_size=16,
                               out_dtype=np.dtype("uint8"), max_block_bytes=1 << 30)
    assert set(tiles) == {(0, 0, 0, 0, 0, 0), (0, 0, 0, 1, 0, 0)}
    assert tiles[(0, 0, 0, 1, 0, 0)][2] == data[1].tobytes()


def test_read_tile_block_respects_max_block_bytes():
    data = np.zeros((8, 1, 1, 32, 32), dtype=np.uint16)          # one chunk = 8×32×32×2 = 16 KB
    img, _ = _img(data, chunks=(8, 1, 1, 32, 32), axes="tczyx")
    tiles = zb.read_tile_block(img, 0, t=3, c=0, z=0, tx=0, ty=0, tile_size=32,
                               out_dtype=np.dtype("uint16"), max_block_bytes=4096)
    assert list(tiles) == [(0, 3, 0, 0, 0, 0)]                     # only the requested tile


def test_bridge_cache_lru_by_bytes():
    cache = zb.BridgeCache(max_bytes=100)
    cache.put_many([(("a",), (1, 1, b"x" * 40)), (("b",), (1, 1, b"y" * 40))])
    assert cache.get(("a",)) is not None                            # touch a → b is now oldest
    cache.put_many([(("c",), (1, 1, b"z" * 40))])
    assert cache.get(("b",)) is None and cache.get(("a",)) is not None and cache.get(("c",)) is not None
    assert cache.nbytes == 80
    cache.clear()
    assert len(cache) == 0 and cache.nbytes == 0


def test_bridge_cache_keeps_newest_even_if_over_budget():
    cache = zb.BridgeCache(max_bytes=10)
    cache.put_many([(("big",), (1, 1, b"x" * 50))])
    assert cache.get(("big",)) is not None


def test_read_tile_block_unknown_axis_pinned_to_zero():
    data = np.zeros((3, 2, 1, 1, 32, 32), dtype=np.uint16)
    for k in range(3):
        data[k] = k
    arr = FakeArray(data, chunks=(3, 2, 1, 1, 32, 32))
    img = ngff.NgffImage(group=None, version="0.4", axes=["dim0", "t", "c", "z", "y", "x"],
                         levels=[arr], dtype=np.dtype("uint16"), omero_channels=[])
    tiles = zb.read_tile_block(img, 0, t=1, c=0, z=0, tx=0, ty=0, tile_size=32,
                               out_dtype=np.dtype("uint16"), max_block_bytes=1 << 30)
    assert arr.reads == 1
    assert set(k[1] for k in tiles) == {0, 1}
    w, h, raw = tiles[(0, 1, 0, 0, 0, 0)]
    expect = data[0, 1, 0, 0].astype("<u2")
    assert raw == expect.tobytes()


def test_read_tile_block_tile_spanning_two_chunks():
    data = (np.arange(64 * 64) % 500).astype(np.uint16).reshape(1, 1, 1, 64, 64)
    img, arr = _img(data, chunks=(1, 1, 1, 32, 32), axes="tczyx")
    tiles = zb.read_tile_block(img, 0, t=0, c=0, z=0, tx=0, ty=0, tile_size=64,
                               out_dtype=np.dtype("uint16"), max_block_bytes=1 << 30)
    assert arr.reads == 1
    assert len(tiles) == 1
    w, h, raw = tiles[(0, 0, 0, 0, 0, 0)]
    assert (w, h) == (64, 64)
    assert raw == data[0, 0, 0].astype("<u2").tobytes()


def test_read_tile_block_guard_counts_source_itemsize():
    data = np.zeros((4, 1, 1, 32, 32), dtype=np.float64)
    img, _ = _img(data, chunks=(4, 1, 1, 32, 32), axes="tczyx")
    max_block_bytes = 4 * 32 * 32 * 4 + 1  # above float32 size, below float64 size
    tiles = zb.read_tile_block(img, 0, t=2, c=0, z=0, tx=0, ty=0, tile_size=32,
                               out_dtype=np.dtype("float32"), max_block_bytes=max_block_bytes)
    assert list(tiles) == [(0, 2, 0, 0, 0, 0)]


def test_read_tile_block_rejects_bad_tile_size():
    data = np.zeros((1, 1, 1, 32, 32), dtype=np.uint16)
    img, _ = _img(data, chunks=(1, 1, 1, 32, 32), axes="tczyx")
    with pytest.raises(ValueError):
        zb.read_tile_block(img, 0, t=0, c=0, z=0, tx=0, ty=0, tile_size=0,
                           out_dtype=np.dtype("uint16"), max_block_bytes=1 << 30)


def test_bridge_cache_set_max_bytes_evicts():
    cache = zb.BridgeCache(max_bytes=1000)
    cache.put_many([(("a",), (1, 1, b"x" * 40)), (("b",), (1, 1, b"y" * 40))])
    cache.set_max_bytes(50)
    assert len(cache) == 1
    assert cache.get(("b",)) is not None and cache.get(("a",)) is None
