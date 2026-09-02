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


# --- ZarrBridgeMixin: attach/detach, message handling, dedupe ----------------

import time  # noqa: E402

from anybioimage import BioImageViewer  # noqa: E402


@pytest.fixture
def _fake_viv_esm(monkeypatch):
    import anybioimage.viewer as viewer_mod
    monkeypatch.setattr(viewer_mod, "get_backend_esm", lambda name: "export default {}")


@pytest.fixture
def viv(_fake_viv_esm):
    v = BioImageViewer(render_backend="viv")
    v._sent = []
    v.send = lambda content, buffers=None: v._sent.append((content, buffers or []))
    yield v
    v.close()


def _wait_sent(v, n, timeout=5.0):
    deadline = time.time() + timeout
    while len(v._sent) < n and time.time() < deadline:
        time.sleep(0.01)
    assert len(v._sent) >= n, f"only {len(v._sent)} replies"


def test_attach_bridge_populates_traitlets(viv, v04_store):
    viv._attach_bridge(ngff.open_image(v04_store))
    assert viv._zarr_source["mode"] == "bridge"
    assert viv._zarr_source["labels"] == ["t", "c", "z", "y", "x"]
    assert viv._zarr_source["dtype"] == "uint16"
    assert [lvl["shape"] for lvl in viv._zarr_source["levels"]] == [[2, 3, 2, 64, 96], [2, 3, 2, 32, 48]]
    assert viv._zarr_source["levels"][0]["chunks"] == [1, 1, 1, 32, 32]
    assert (viv.dim_t, viv.dim_c, viv.dim_z, viv.height, viv.width) == (2, 3, 2, 64, 96)
    assert [c["name"] for c in viv._channel_settings] == ["Ch0", "Ch1", "Ch2"]
    assert viv._channel_settings[0]["color"] == "#ff0000"
    assert viv.image_data == "" and viv._full_array is None and viv._bioimage is None
    assert viv._render_ready is False


def test_attach_bridge_without_omero_samples_lowest_level(viv, v04_sloppy_store):
    viv._attach_bridge(ngff.open_image(v04_sloppy_store))
    ch = viv._channel_settings[0]
    assert 0.0 <= ch["data_min"] < ch["data_max"] <= 65535.0
    assert ch["name"] == "Ch 0"


def test_chunk_request_replies_with_bytes(viv, v04_store):
    viv._attach_bridge(ngff.open_image(v04_store))
    viv._handle_custom_msg({"kind": "chunk", "requestId": 7, "level": 1, "t": 1, "c": 2, "z": 0,
                            "tx": 1, "ty": 0, "tileSize": 32}, [])
    _wait_sent(viv, 1)
    content, buffers = viv._sent[0]
    assert content == {"kind": "chunk", "requestId": 7, "ok": True, "w": 16, "h": 32, "dtype": "uint16"}
    expect = np.asarray(ngff.open_image(v04_store).levels[1][1, 2, 0, 0:32, 32:48])
    assert buffers[0] == np.ascontiguousarray(expect.astype("<u2")).tobytes()


def test_chunk_request_error_reply(viv, v04_store):
    viv._attach_bridge(ngff.open_image(v04_store))
    viv._handle_custom_msg({"kind": "chunk", "requestId": 8, "level": 0, "t": 0, "c": 0, "z": 0,
                            "tx": 99, "ty": 0, "tileSize": 32}, [])
    _wait_sent(viv, 1)
    content, buffers = viv._sent[0]
    assert content["ok"] is False and content["requestId"] == 8 and "outside" in content["error"]
    assert buffers == []


def test_chunk_request_without_image_errors(viv):
    viv._handle_custom_msg({"kind": "chunk", "requestId": 1, "level": 0, "tx": 0, "ty": 0}, [])
    _wait_sent(viv, 1)
    assert viv._sent[0][0]["ok"] is False


def test_non_chunk_messages_ignored(viv):
    viv._handle_custom_msg({"kind": "something-else"}, [])
    viv._handle_custom_msg("not a dict", [])
    time.sleep(0.05)
    assert viv._sent == []


def test_sibling_tile_is_cache_hit(viv, v04_store):
    img = ngff.open_image(v04_store)
    # chunks (1,1,1,32,32): make t span the whole chunk so t=0 and t=1 share a block
    img.levels[0] = FakeArray(np.asarray(img.levels[0][:]), chunks=(2, 1, 1, 32, 32))
    viv._attach_bridge(img)
    req = {"kind": "chunk", "level": 0, "c": 0, "z": 0, "tx": 0, "ty": 0, "tileSize": 32}
    viv._handle_custom_msg({**req, "requestId": 1, "t": 0}, [])
    _wait_sent(viv, 1)
    viv._handle_custom_msg({**req, "requestId": 2, "t": 1}, [])
    _wait_sent(viv, 2)
    assert img.levels[0].reads == 1
    assert len(viv._bridge_cache) == 2


def test_concurrent_siblings_read_block_once(viv, v04_store):
    img = ngff.open_image(v04_store)
    img.levels[0] = FakeArray(np.asarray(img.levels[0][:]), chunks=(2, 3, 2, 32, 32))
    viv._attach_bridge(img)
    req = {"kind": "chunk", "level": 0, "tx": 0, "ty": 0, "tileSize": 32}
    n = 0
    for t in range(2):
        for c in range(3):
            for z in range(2):
                n += 1
                viv._handle_custom_msg({**req, "requestId": n, "t": t, "c": c, "z": z}, [])
    _wait_sent(viv, 12)
    assert all(content["ok"] for content, _ in viv._sent)
    assert img.levels[0].reads == 1          # in-flight dedupe: one block read for the burst


def test_detach_on_numpy_load_clears_bridge(viv, v04_store):
    viv._attach_bridge(ngff.open_image(v04_store))
    viv.set_image(np.zeros((16, 16), dtype=np.uint8))
    assert viv._zarr_source == {} and viv._bridge_image is None and len(viv._bridge_cache) == 0


def test_bridge_cache_bytes_traitlet_resizes(viv):
    viv.bridge_cache_bytes = 1234
    assert viv._bridge_cache.max_bytes == 1234


def test_canvas2d_viewer_has_inert_bridge():
    v = BioImageViewer()
    v._sent = []
    v.send = lambda content, buffers=None: v._sent.append(content)
    v._handle_custom_msg({"kind": "chunk", "requestId": 1, "level": 0, "tx": 0, "ty": 0}, [])
    _wait_sent(v, 1)
    assert v._sent[0]["ok"] is False
    v.close()
