"""Lenient NGFF metadata reader."""
from pathlib import Path

import numpy as np
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


def test_open_image_v04(v04_store):
    img = ngff.open_image(v04_store)
    assert img.version == "0.4"
    assert img.axes == ["t", "c", "z", "y", "x"]
    assert [a.shape for a in img.levels] == [(2, 3, 2, 64, 96), (2, 3, 2, 32, 48)]
    assert img.dtype == np.dtype("uint16") and img.dtype.isnative
    assert [c["label"] for c in img.omero_channels] == ["Ch0", "Ch1", "Ch2"]
    assert img.shape == (2, 3, 2, 64, 96)
    assert (img.size("t"), img.size("c"), img.size("z"), img.size("y"), img.size("x")) == (2, 3, 2, 64, 96)


def test_open_image_v05(v05_store):
    img = ngff.open_image(v05_store)
    assert img.version == "0.5"
    assert len(img.levels) == 2 and img.levels[0].metadata.zarr_format == 3
    assert img.omero_channels[0]["label"] == "C0"


def test_open_image_sloppy_store_no_c_axis(v04_sloppy_store):
    img = ngff.open_image(v04_sloppy_store)
    assert img.axes == ["t", "z", "y", "x"]
    assert img.size("c") == 1            # absent axis reads as size 1
    assert img.omero_channels == []


def test_open_image_skips_missing_dataset(tmp_path, caplog):
    from tests.conftest import write_v04_image
    path = write_v04_image(tmp_path / "x.zarr", n_levels=1)
    g = zarr.open_group(path, mode="a")
    ms = dict(g.attrs)["multiscales"]
    ms[0]["datasets"].append({"path": "99"})
    g.attrs["multiscales"] = ms
    img = ngff.open_image(path)
    assert len(img.levels) == 1
    assert "99" in caplog.text


def test_open_image_rejects_plain_zarr(tmp_path):
    g = zarr.create_group(str(tmp_path / "plain.zarr"), zarr_format=2)
    g.create_array("0", shape=(4, 4), dtype="uint8")
    with pytest.raises(ValueError, match="multiscales"):
        ngff.open_image(str(tmp_path / "plain.zarr"))


def test_open_image_rejects_x_before_y(tmp_path):
    from tests.conftest import write_v04_image
    axes = [{"name": n} for n in ("t", "c", "z", "x", "y")]
    path = write_v04_image(tmp_path / "xy.zarr", axes=axes, n_levels=1)
    with pytest.raises(ValueError, match="y before x"):
        ngff.open_image(path)


def test_open_image_on_plate_raises_plate_error(plate_store):
    with pytest.raises(ngff.PlateError, match="set_plate"):
        ngff.open_image(plate_store)


def test_is_plate_and_layout(plate_store, v04_store):
    assert ngff.is_plate(ngff.open_group(plate_store)) is True
    assert ngff.is_plate(ngff.open_group(v04_store)) is False
    layout = ngff.plate_layout(ngff.open_group(plate_store))
    assert [w["path"] for w in layout["wells"]] == ["A/1", "B/2"]
    with pytest.raises(ValueError, match="plate"):
        ngff.plate_layout(ngff.open_group(v04_store))


def test_open_image_on_plate_subgroup(plate_store):
    g = ngff.open_group(plate_store)
    img = ngff.open_image(g["A/1/0"])
    assert img.shape == (1, 1, 1, 32, 32)
