"""Viv zarr-URL load path: metadata-only, no precompute, silent fallbacks."""
import logging

import numpy as np
import pytest

import anybioimage.mixins.image_loading as il
from anybioimage import BioImageViewer

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
    assert viv_viewer._zarr_source == {"url": "https://example.org/img.ome.zarr", "headers": {}}
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
