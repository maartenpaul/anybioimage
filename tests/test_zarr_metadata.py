"""Viv zarr-URL load path: metadata-only, no precompute, silent fallbacks."""
import logging

import numpy as np
import pytest

import anybioimage.mixins.image_loading as il
from anybioimage import BioImageViewer

# Captured before the autouse _no_plate fixture stubs the module attribute, so
# the direct unit tests below exercise the real implementation.
_real_is_plate = il._zarr_url_is_plate
_real_fetch = il._fetch_zarr_ome_metadata

FAKE_ZATTRS = {
    "multiscales": [{
        "axes": [{"name": n} for n in ("t", "c", "z", "y", "x")],
        "datasets": [{"path": "0"}],
    }],
    "omero": {"channels": [
        {"label": "DAPI", "color": "0000ff",
         "window": {"min": 0, "max": 65535, "start": 100, "end": 2000}},
        {"label": "GFP", "color": "00ff00",
         "window": {"min": 0, "max": 65535, "start": 0, "end": 5000}},
    ]},
}


def _fake_fetch(url, headers):
    return FAKE_ZATTRS, ["t", "c", "z", "y", "x"], [10, 2, 3, 2048, 1024], "uint16"


@pytest.fixture(autouse=True)
def _no_plate(monkeypatch):
    # By default treat zarr URLs as single images. The plate guard otherwise does
    # a real .zattrs network fetch; the dedicated plate test overrides this.
    monkeypatch.setattr(il, "_zarr_url_is_plate", lambda url, headers: False)


@pytest.fixture
def _fake_viv_esm(monkeypatch):
    import anybioimage.viewer as viewer_mod
    monkeypatch.setattr(viewer_mod, "get_backend_esm", lambda name: "export default {}")


@pytest.fixture
def viv_viewer(monkeypatch, _fake_viv_esm):
    monkeypatch.setattr(il, "_fetch_zarr_ome_metadata", _fake_fetch)
    return BioImageViewer(render_backend="viv")


def test_zarr_url_populates_dims_and_source(viv_viewer):
    viv_viewer.set_image("https://example.org/img.ome.zarr")
    assert viv_viewer._zarr_source == {
        "mode": "url", "url": "https://example.org/img.ome.zarr", "headers": {},
    }
    assert (viv_viewer.dim_t, viv_viewer.dim_c, viv_viewer.dim_z) == (10, 2, 3)
    assert (viv_viewer.height, viv_viewer.width) == (2048, 1024)


def test_zarr_url_builds_channel_settings(viv_viewer):
    viv_viewer.set_image("https://example.org/img.ome.zarr")
    chs = viv_viewer._channel_settings
    assert len(chs) == 2
    assert chs[0]["name"] == "DAPI"
    assert chs[0]["color"] == "#0000ff"
    assert 0.0 <= chs[0]["min"] < chs[0]["max"] <= 1.0
    assert chs[0]["data_min"] == 0.0 and chs[0]["data_max"] == 65535.0


def test_zarr_url_skips_canvas2d_pipeline(viv_viewer):
    viv_viewer.set_image("https://example.org/img.ome.zarr")
    assert viv_viewer.image_data == ""
    assert viv_viewer._full_array is None
    assert getattr(viv_viewer, "_precompute_future", None) is None
    # T navigation must not start Python-side work
    viv_viewer.current_t = 3
    assert viv_viewer.image_data == ""


def test_canvas2d_backend_routes_zarr_url_to_bioio(monkeypatch):
    v = BioImageViewer()  # default backend
    called = {}
    monkeypatch.setattr(v, "_set_zarr_url_canvas2d", lambda url: called.setdefault("url", url))
    v.set_image("https://example.org/img.ome.zarr")
    assert called["url"] == "https://example.org/img.ome.zarr"
    assert v._zarr_source == {}


def test_metadata_failure_falls_back_to_bioio(monkeypatch, caplog, _fake_viv_esm):
    def boom(url, headers):
        raise OSError("connection refused")
    monkeypatch.setattr(il, "_fetch_zarr_ome_metadata", boom)
    v = BioImageViewer(render_backend="viv")
    called = {}
    monkeypatch.setattr(v, "_set_zarr_url_canvas2d", lambda url: called.setdefault("url", url))
    with caplog.at_level(logging.INFO):
        v.set_image("https://example.org/img.ome.zarr")
    assert called["url"] == "https://example.org/img.ome.zarr"
    assert v._zarr_source == {}


def test_numpy_on_viv_falls_back_to_canvas2d(caplog, _fake_viv_esm):
    v = BioImageViewer(render_backend="viv")
    with caplog.at_level(logging.INFO):
        v.set_image(np.zeros((64, 64), dtype=np.uint16))
    assert v._zarr_source == {}
    assert v.image_data != ""  # Canvas2D pipeline produced a thumbnail/PNG


def test_switching_zarr_to_numpy_clears_source(viv_viewer):
    viv_viewer.set_image("https://example.org/img.ome.zarr")
    assert viv_viewer._zarr_source.get("url")
    viv_viewer.set_image(np.zeros((32, 32), dtype=np.uint8))
    assert viv_viewer._zarr_source == {}


def test_omero_window_narrower_than_dtype_normalizes_against_data_range(monkeypatch, _fake_viv_esm):
    # 12-bit data in uint16: window 0..4095, start/end 100..2000.
    zattrs = {
        "multiscales": FAKE_ZATTRS["multiscales"],
        "omero": {"channels": [
            {"label": "Ch", "color": "ff0000",
             "window": {"min": 0, "max": 4095, "start": 100, "end": 2000}},
        ]},
    }

    def fetch(url, headers):
        return zattrs, ["t", "c", "z", "y", "x"], [1, 1, 1, 64, 64], "uint16"

    monkeypatch.setattr(il, "_fetch_zarr_ome_metadata", fetch)
    v = BioImageViewer(render_backend="viv")
    v.set_image("https://example.org/img.ome.zarr")
    ch = v._channel_settings[0]
    # Reconstructing with the stored data range must land on the OMERO start/end.
    assert ch["data_min"] == 0.0 and ch["data_max"] == 65535.0
    assert ch["data_min"] + ch["min"] * (ch["data_max"] - ch["data_min"]) == pytest.approx(100.0)
    assert ch["data_min"] + ch["max"] * (ch["data_max"] - ch["data_min"]) == pytest.approx(2000.0)


def test_unusable_metadata_falls_back_to_bioio(monkeypatch, _fake_viv_esm):
    # Plain zarr with no multiscales: fetcher returns empty axes/shape.
    def fetch(url, headers):
        return {}, [], [], "uint16"

    monkeypatch.setattr(il, "_fetch_zarr_ome_metadata", fetch)
    v = BioImageViewer(render_backend="viv")
    called = {}
    monkeypatch.setattr(v, "_set_zarr_url_canvas2d", lambda url: called.setdefault("url", url))
    v.set_image("https://example.org/plain.zarr")
    assert called["url"] == "https://example.org/plain.zarr"
    assert v._zarr_source == {}
    assert v.dim_t == 1  # untouched defaults, not a half-populated viewer


def test_plate_url_raises_pointing_to_set_plate(monkeypatch, _fake_viv_esm):
    # An HCS plate handed to set_image() must fail loudly with a pointer to
    # set_plate(), not the cryptic bioio "multiscales" crash or a silent fallback.
    monkeypatch.setattr(il, "_zarr_url_is_plate", lambda url, headers: True)
    v = BioImageViewer(render_backend="viv")
    fell_back = {}
    monkeypatch.setattr(v, "_set_zarr_url_canvas2d", lambda url: fell_back.setdefault("url", url))
    with pytest.raises(ValueError, match="set_plate"):
        v.set_image("https://example.org/plate.zarr")
    assert fell_back == {}  # did not silently route to the bioio path
    assert v._zarr_source == {}


def test_zarr_url_is_plate_detects_v04_and_v05(monkeypatch):
    import json
    import urllib.request
    from io import BytesIO

    samples = {
        "https://x/plate.zarr/.zattrs": {"plate": {"wells": []}},        # v0.4
        "https://x/plate5.zarr/.zattrs": {"ome": {"plate": {"wells": []}}},  # v0.5
        "https://x/img.zarr/.zattrs": {"multiscales": [{}]},             # single image
    }

    class _Resp(BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): self.close()

    def fake_urlopen(req, timeout=30):
        if req.full_url not in samples:
            raise OSError("404")
        return _Resp(json.dumps(samples[req.full_url]).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert _real_is_plate("https://x/plate.zarr", {}) is True
    assert _real_is_plate("https://x/plate5.zarr", {}) is True
    assert _real_is_plate("https://x/img.zarr", {}) is False


def test_zarr_url_is_plate_swallows_network_errors(monkeypatch):
    import urllib.request

    def boom(req, timeout=30):
        raise OSError("connection refused")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert _real_is_plate("https://x/whatever.zarr", {}) is False


def test_real_probe_reads_v05_ome_block(monkeypatch):
    import json
    import urllib.request
    from io import BytesIO
    samples = {
        "https://x/v5.zarr/zarr.json": {"zarr_format": 3, "node_type": "group", "attributes": {"ome": {
            "version": "0.5",
            "multiscales": [{"axes": [{"name": n} for n in ("c", "z", "y", "x")], "datasets": [{"path": "0"}]}],
            "omero": {"channels": [{"label": "Nuc", "color": "0000ff", "window": {"min": 0, "max": 4095, "start": 5, "end": 900}}]},
        }}},
        "https://x/v5.zarr/0/zarr.json": {"shape": [1, 3, 64, 32], "data_type": "uint16"},
    }
    class _Resp(BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): self.close()
    def fake_urlopen(req, timeout=30):
        if req.full_url not in samples:
            raise OSError("404")
        return _Resp(json.dumps(samples[req.full_url]).encode())
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    ome, axes, shape, dtype = _real_fetch("https://x/v5.zarr", {})
    assert ome["omero"]["channels"][0]["label"] == "Nuc"
    assert axes == ["c", "z", "y", "x"] and shape == [1, 3, 64, 32] and dtype == "uint16"
    chs = il._channel_settings_from_omero(ome, 1, dtype)
    assert chs[0]["name"] == "Nuc" and chs[0]["color"] == "#0000ff"


def test_render_ready_rearms_on_each_new_zarr_source(viv_viewer):
    # The frontend flips _render_ready True once a frame paints; loading a new
    # image must reset it so fixtures block on the NEW image, not a stale True.
    viv_viewer.set_image("https://example.org/a.ome.zarr")
    viv_viewer._render_ready = True  # simulate the frontend having painted A
    viv_viewer.set_image("https://example.org/b.ome.zarr")
    assert viv_viewer._render_ready is False
    assert viv_viewer._zarr_source["url"] == "https://example.org/b.ome.zarr"


def test_numpy_then_zarr_restores_zarr_source(viv_viewer):
    # Reverse of test_switching_zarr_to_numpy_clears_source: a numpy load clears
    # _zarr_source, and a subsequent zarr load must repopulate it.
    viv_viewer.set_image(np.zeros((16, 16), dtype=np.uint8))
    assert viv_viewer._zarr_source == {}
    viv_viewer.set_image("https://example.org/img.ome.zarr")
    assert viv_viewer._zarr_source["url"] == "https://example.org/img.ome.zarr"
    assert viv_viewer.dim_t == 10  # dims repopulated from metadata


def test_local_zarr_on_viv_attaches_bridge(_fake_viv_esm, v04_store):
    v = BioImageViewer(render_backend="viv")
    v.set_image(v04_store)
    assert v._zarr_source["mode"] == "bridge"
    assert (v.dim_t, v.dim_c, v.dim_z) == (2, 3, 2)
    assert v._precompute_future is None and v.image_data == ""


def test_local_zarr_group_on_viv(_fake_viv_esm, v04_store):
    import zarr
    v = BioImageViewer(render_backend="viv")
    v.set_image(zarr.open_group(v04_store, mode="r"))
    assert v._zarr_source["mode"] == "bridge"


def test_local_zarr_on_canvas2d_uses_bioio(monkeypatch, v04_store):
    v = BioImageViewer()
    called = {}
    monkeypatch.setattr(v, "_set_zarr_url_canvas2d", lambda p: called.setdefault("path", p))
    v.set_image(v04_store)
    assert called["path"] == v04_store and v._zarr_source == {}


def test_local_plate_to_set_image_raises(_fake_viv_esm, plate_store):
    v = BioImageViewer(render_backend="viv")
    with pytest.raises(ValueError, match="set_plate"):
        v.set_image(plate_store)
    assert v._zarr_source == {}


def test_local_zarr_open_failure_on_viv_falls_back(monkeypatch, caplog, _fake_viv_esm, tmp_path):
    v = BioImageViewer(render_backend="viv")
    called = {}
    monkeypatch.setattr(v, "_set_zarr_url_canvas2d", lambda p: called.setdefault("path", p))
    with caplog.at_level(logging.INFO):
        v.set_image(str(tmp_path / "missing.zarr"))
    assert called["path"] == str(tmp_path / "missing.zarr")
    assert v._zarr_source == {}


def test_zarr_group_on_canvas2d_is_type_error(v04_store):
    import zarr
    v = BioImageViewer()
    with pytest.raises(TypeError, match="viv"):
        v.set_image(zarr.open_group(v04_store, mode="r"))


def test_bridge_then_url_switches_mode(viv_viewer, v04_store):
    viv_viewer.set_image(v04_store)
    assert viv_viewer._zarr_source["mode"] == "bridge"
    viv_viewer.set_image("https://example.org/img.ome.zarr")
    assert viv_viewer._zarr_source["mode"] == "url" and viv_viewer._bridge_image is None
