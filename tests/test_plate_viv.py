"""Viv backend: remote-plate FOV switches update _zarr_source (no Python reload)."""
import pytest

from anybioimage import BioImageViewer


@pytest.fixture
def _fake_viv_esm(monkeypatch):
    import anybioimage.viewer as viewer_mod
    monkeypatch.setattr(viewer_mod, "get_backend_esm", lambda name: "export default {}")


def _prime_plate(v, plate_path):
    # Simulate state normally established by set_plate()/_load_well_fovs()
    v._plate_path = plate_path
    v._current_well_path = "A/1"


def test_remote_plate_fov_sets_zarr_source(monkeypatch, _fake_viv_esm):
    v = BioImageViewer(render_backend="viv")
    _prime_plate(v, "https://example.org/plate.zarr")
    seen = {}
    monkeypatch.setattr(v, "_set_zarr_url", lambda url, headers: seen.setdefault("url", url))
    v._load_plate_image("0")
    assert seen["url"] == "https://example.org/plate.zarr/A/1/0"


def test_local_plate_on_viv_uses_bioio(monkeypatch, _fake_viv_esm):
    v = BioImageViewer(render_backend="viv")
    _prime_plate(v, "/data/plate.zarr")  # not a URL → bioio path
    called = {}
    monkeypatch.setattr(v, "_set_zarr_url", lambda *a: called.setdefault("viv", True))

    def fake_bioio(image_path):
        called["bioio"] = image_path
    monkeypatch.setattr(v, "_load_plate_image_bioio", fake_bioio)
    v._load_plate_image("0")
    assert "viv" not in called
    assert called["bioio"] == "/data/plate.zarr/A/1/0"


def test_canvas2d_plate_unchanged(monkeypatch):
    v = BioImageViewer()  # default backend
    _prime_plate(v, "https://example.org/plate.zarr")
    called = {}
    monkeypatch.setattr(v, "_load_plate_image_bioio", lambda p: called.setdefault("path", p))
    v._load_plate_image("0")
    assert called["path"] == "https://example.org/plate.zarr/A/1/0"


def test_viv_plate_metadata_failure_falls_back(monkeypatch, _fake_viv_esm):
    v = BioImageViewer(render_backend="viv")
    _prime_plate(v, "https://example.org/plate.zarr")

    def boom(url, headers):
        raise OSError("403")
    monkeypatch.setattr(v, "_set_zarr_url", boom)
    called = {}
    monkeypatch.setattr(v, "_load_plate_image_bioio", lambda p: called.setdefault("path", p))
    v._load_plate_image("0")
    assert called["path"] == "https://example.org/plate.zarr/A/1/0"
