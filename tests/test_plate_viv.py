"""Viv backend: remote-plate FOV switches update _zarr_source (no Python reload)."""
import pytest

from anybioimage import BioImageViewer, ngff


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


def test_local_plate_on_viv_uses_bridge(monkeypatch, _fake_viv_esm, plate_store):
    v = BioImageViewer(render_backend="viv")
    v.set_plate(plate_store)
    assert v.plate_wells == ["A1", "B2"] and v.plate_fovs == ["0", "1"]
    assert v._zarr_source["mode"] == "bridge"
    assert v._bridge_image.group.path.endswith("A/1/0")
    v.current_fov = "1"
    assert v._bridge_image.group.path.endswith("A/1/1")
    v.current_well = "B2"
    assert v._bridge_image.group.path.endswith("B/2/1")


def test_local_plate_on_viv_falls_back_when_bridge_fails(monkeypatch, _fake_viv_esm, plate_store):
    v = BioImageViewer(render_backend="viv")
    called = {}
    monkeypatch.setattr(ngff, "open_image", lambda group: (_ for _ in ()).throw(OSError("boom")))
    monkeypatch.setattr(v, "_load_plate_image_bioio", lambda p: called.setdefault("path", p))
    v.set_plate(plate_store)
    assert called["path"] == f"{plate_store}/A/1/0"


def test_local_plate_bridge_attach_bug_propagates(monkeypatch, _fake_viv_esm, plate_store):
    v = BioImageViewer(render_backend="viv")
    monkeypatch.setattr(v, "_attach_bridge", lambda img: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(OSError):
        v.set_plate(plate_store)


def test_canvas2d_local_plate_still_bioio(monkeypatch, plate_store):
    v = BioImageViewer()
    called = {}
    monkeypatch.setattr(v, "_load_plate_image_bioio", lambda p: called.setdefault("path", p))
    v.set_plate(plate_store)
    assert called["path"] == f"{plate_store}/A/1/0"
    assert v._zarr_source == {}


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


def test_set_plate_on_non_plate_raises(v04_store):
    v = BioImageViewer()
    with pytest.raises(ValueError, match="plate"):
        v.set_plate(v04_store)


def test_set_plate_passes_storage_options(monkeypatch, plate_store):
    v = BioImageViewer()
    captured = {}
    real_open_group = ngff.open_group

    def fake_open_group(src, storage_options=None):
        captured["storage_options"] = storage_options
        # Delegate without storage_options: plate_store is a local path, and
        # zarr rejects storage_options for non-fsspec stores. We only need to
        # confirm set_plate() forwards the argument, not that a local store
        # accepts it.
        return real_open_group(src)

    monkeypatch.setattr(ngff, "open_group", fake_open_group)
    v.set_plate(plate_store, storage_options={"anon": True})
    assert captured["storage_options"] == {"anon": True}


def test_local_plate_missing_fov_falls_back(monkeypatch, _fake_viv_esm, plate_store):
    v = BioImageViewer(render_backend="viv")
    v.set_plate(plate_store)
    called = {}
    monkeypatch.setattr(v, "_load_plate_image_bioio", lambda p: called.setdefault("path", p))
    v._load_plate_image("99")  # FOV not present in the well's zarr group
    assert called["path"] == f"{plate_store}/A/1/99"
