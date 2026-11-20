"""zarr is an optional extra: the base install must work without it and
point at ``anybioimage[zarr]`` when a zarr store is opened."""
import sys
import urllib.error

import numpy as np
import pytest

from anybioimage import BioImageViewer, ngff

URL = "https://example.org/data.zarr"


@pytest.fixture
def no_zarr(monkeypatch):
    """Simulate a base install: importing zarr / bioio / bioio_ome_zarr fails."""
    for name in ("zarr", "bioio", "bioio_ome_zarr"):
        monkeypatch.setitem(sys.modules, name, None)


def test_numpy_image_does_not_need_zarr(no_zarr):
    viewer = BioImageViewer()
    viewer.set_image(np.zeros((3, 2, 2, 32, 32), dtype=np.uint16))
    assert (viewer.dim_t, viewer.dim_c, viewer.dim_z) == (3, 2, 2)


@pytest.mark.parametrize("backend", ["canvas2d", "viv"])
def test_local_zarr_path_names_the_extra(no_zarr, backend, tmp_path):
    store = tmp_path / "img.zarr"
    store.mkdir()
    with pytest.raises(ImportError, match=r"anybioimage\[zarr\]"):
        BioImageViewer(render_backend=backend).set_image(str(store))


def test_canvas2d_zarr_url_names_the_extra(no_zarr, monkeypatch):
    monkeypatch.setattr(ngff, "fetch_http_attrs", lambda url, headers: {"multiscales": [{}]})
    with pytest.raises(ImportError, match=r"anybioimage\[zarr\]"):
        BioImageViewer().set_image(URL)


def test_viv_url_failure_reports_viv_error_not_missing_extra(no_zarr, monkeypatch):
    """A store the viv probe cannot use must not be reported as a missing extra:
    installing it would not help."""
    monkeypatch.setattr(ngff, "fetch_http_attrs", lambda url, headers: {})
    with pytest.raises(ValueError, match="viv backend"):
        BioImageViewer(render_backend="viv").set_image(URL)


@pytest.mark.parametrize("backend", ["canvas2d", "viv"])
def test_unreachable_host_raises_connection_error(monkeypatch, backend):
    def refuse(url, headers):
        raise urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))

    monkeypatch.setattr(ngff, "_http_json", refuse)
    with pytest.raises(ConnectionError, match="Could not reach https://example.org/data.zarr"):
        BioImageViewer(render_backend=backend).set_image(URL)


def test_http_404_is_not_reported_as_unreachable(monkeypatch):
    def not_found(url, headers):
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

    monkeypatch.setattr(ngff, "_http_json", not_found)
    with pytest.raises(OSError) as excinfo:
        ngff.fetch_http_attrs(URL, {})
    assert not isinstance(excinfo.value, ConnectionError)
