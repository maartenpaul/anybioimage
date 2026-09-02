"""Lenient NGFF metadata reader."""
from pathlib import Path

import pytest
import zarr

from anybioimage import ngff


def test_parse_v04_top_level():
    version, ome = ngff.parse_ome_attrs({"multiscales": [{"version": "0.4"}], "omero": {"channels": []}})
    assert version == "0.4"
    assert "multiscales" in ome and "omero" in ome


def test_parse_v05_nested_under_ome():
    version, ome = ngff.parse_ome_attrs({"ome": {"version": "0.5", "multiscales": [{}]}})
    assert version == "0.5"
    assert ome["multiscales"] == [{}]


def test_parse_missing_version_is_unknown():
    version, ome = ngff.parse_ome_attrs({"multiscales": [{}]})
    assert version == "unknown"
    version, ome = ngff.parse_ome_attrs({})
    assert version == "unknown" and ome == {}


def test_parse_tolerates_non_list_multiscales():
    assert ngff.parse_ome_attrs({"multiscales": {"version": "0.4"}}) == (
        "unknown",
        {"multiscales": {"version": "0.4"}},
    )


def test_open_group_accepts_path_str_and_group(v04_store):
    g1 = ngff.open_group(v04_store)
    g2 = ngff.open_group(Path(v04_store))
    g3 = ngff.open_group(g1)
    assert isinstance(g1, zarr.Group) and isinstance(g2, zarr.Group) and g3 is g1


def test_open_group_missing_fsspec_backend_hint(monkeypatch):
    def boom(*a, **k):
        raise ImportError("Install s3fs to access S3")
    monkeypatch.setattr(zarr, "open_group", boom)
    with pytest.raises(ImportError, match=r"anybioimage\[remote\]"):
        ngff.open_group("s3://bucket/x.zarr")


def test_open_group_local_import_error_not_relabelled(monkeypatch):
    def boom(*a, **k):
        raise ImportError("no module named numcodecs")
    monkeypatch.setattr(zarr, "open_group", boom)
    with pytest.raises(ImportError, match="numcodecs") as exc_info:
        ngff.open_group("/tmp/x.zarr")
    assert "anybioimage[remote]" not in str(exc_info.value)


def test_read_ome_attrs_v04_and_v05(v04_store, v05_store):
    v, ome = ngff.read_ome_attrs(ngff.open_group(v04_store))
    assert v == "0.4" and ome["multiscales"][0]["datasets"][0]["path"] == "0"
    v, ome = ngff.read_ome_attrs(ngff.open_group(v05_store))
    assert v == "0.5" and ome["omero"]["channels"][0]["label"] == "C0"


def test_axes_from_multiscale_defaults_to_trailing_tczyx():
    assert ngff.axes_from_multiscale({"axes": [{"name": "t"}, {"name": "z"}, {"name": "y"}, {"name": "x"}]}, 4) == ["t", "z", "y", "x"]
    assert ngff.axes_from_multiscale({"axes": ["y", "x"]}, 2) == ["y", "x"]      # v0.3 string axes
    assert ngff.axes_from_multiscale({}, 3) == ["z", "y", "x"]                     # missing
    assert ngff.axes_from_multiscale({"axes": [{"name": "y"}]}, 5) == ["t", "c", "z", "y", "x"]  # length mismatch
    assert ngff.axes_from_multiscale({}, 6) == ["dim0", "t", "c", "z", "y", "x"]  # ndim > 5
