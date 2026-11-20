"""Shared fixtures: small OME-Zarr stores written with zarr-python 3."""
import numpy as np
import pytest
import zarr

AXES_TCZYX = [
    {"name": "t", "type": "time"},
    {"name": "c", "type": "channel"},
    {"name": "z", "type": "space"},
    {"name": "y", "type": "space"},
    {"name": "x", "type": "space"},
]


def _fill(shape):
    return (np.arange(int(np.prod(shape)), dtype=np.uint32) % 60000).astype(np.uint16).reshape(shape)


def _write_levels(group, shape, chunks, n_levels):
    """Write level 0 = arange data, each next level = ::2 in y/x. Returns dataset paths."""
    data = _fill(shape)
    paths = []
    for lvl in range(n_levels):
        name = str(lvl)
        arr = group.create_array(
            name, shape=data.shape, chunks=tuple(min(c, s) for c, s in zip(chunks, data.shape)),
            dtype="uint16",
        )
        arr[:] = data
        paths.append(name)
        data = data[..., ::2, ::2]
    return paths


def write_v04_image(path, shape=(2, 3, 2, 64, 96), chunks=(1, 1, 1, 32, 32),
                    axes=AXES_TCZYX, n_levels=2, omero=True, empty_transforms=False):
    """NGFF v0.4 image in a zarr v2 store (attrs at top level)."""
    g = zarr.create_group(str(path), zarr_format=2)
    paths = _write_levels(g, shape, chunks, n_levels)
    datasets = []
    for i, p in enumerate(paths):
        ds = {"path": p}
        if not empty_transforms:
            ds["coordinateTransformations"] = [{"type": "scale", "scale": [1.0] * len(shape)}]
        else:
            ds["coordinateTransformations"] = []
        datasets.append(ds)
    attrs = {"multiscales": [{"version": "0.4", "axes": list(axes), "datasets": datasets}]}
    if omero:
        n_c = shape[1] if len(shape) == 5 else 1
        attrs["omero"] = {"channels": [
            {"label": f"Ch{i}", "color": c, "window": {"min": 0, "max": 65535, "start": 10, "end": 5000}}
            for i, c in enumerate(["ff0000", "00ff00", "0000ff"][:n_c])
        ]}
    g.attrs.update(attrs)
    return str(path)


def write_v05_image(path, shape=(2, 3, 2, 64, 96), chunks=(1, 1, 1, 32, 32), n_levels=2):
    """NGFF v0.5 image in a zarr v3 store (attrs under `ome`)."""
    g = zarr.create_group(str(path), zarr_format=3)
    paths = _write_levels(g, shape, chunks, n_levels)
    g.attrs.update({"ome": {
        "version": "0.5",
        "multiscales": [{
            "axes": AXES_TCZYX,
            "datasets": [{"path": p, "coordinateTransformations": [{"type": "scale", "scale": [1.0] * 5}]}
                         for p in paths],
        }],
        "omero": {"channels": [{"label": f"C{i}", "color": "ffffff",
                                "window": {"min": 0, "max": 65535, "start": 0, "end": 1000}}
                               for i in range(shape[1])]},
    }})
    return str(path)


def write_v04_plate(path, wells=("A/1", "B/2"), fovs=("0", "1")):
    """NGFF v0.4 HCS plate with `wells × fovs` small images."""
    g = zarr.create_group(str(path), zarr_format=2)
    rows = sorted({w.split("/")[0] for w in wells})
    cols = sorted({w.split("/")[1] for w in wells})
    g.attrs.update({"plate": {
        "version": "0.4",
        "rows": [{"name": r} for r in rows],
        "columns": [{"name": c} for c in cols],
        "wells": [{"path": w, "rowIndex": rows.index(w.split("/")[0]),
                   "columnIndex": cols.index(w.split("/")[1])} for w in wells],
    }})
    for w in wells:
        wg = g.create_group(w)
        wg.attrs.update({"well": {"images": [{"path": f} for f in fovs]}})
        for f in fovs:
            ig = wg.create_group(f)
            paths = _write_levels(ig, (1, 1, 1, 32, 32), (1, 1, 1, 16, 16), 1)
            ig.attrs.update({"multiscales": [{"version": "0.4", "axes": AXES_TCZYX,
                                              "datasets": [{"path": p} for p in paths]}]})
    return str(path)


@pytest.fixture
def v04_store(tmp_path):
    return write_v04_image(tmp_path / "img.ome.zarr")


@pytest.fixture
def v04_sloppy_store(tmp_path):
    """Mirrors examples/image.zarr: no `c` axis, empty transforms."""
    axes = [a for a in AXES_TCZYX if a["name"] != "c"]
    return write_v04_image(tmp_path / "sloppy.zarr", shape=(2, 2, 64, 96), chunks=(2, 2, 32, 32),
                           axes=axes, omero=False, empty_transforms=True)


@pytest.fixture
def v05_store(tmp_path):
    return write_v05_image(tmp_path / "img5.ome.zarr")


@pytest.fixture
def plate_store(tmp_path):
    return write_v04_plate(tmp_path / "plate.zarr")
