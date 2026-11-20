# Zarr Chunk Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the `viv` backend, render local / `s3://` / `gs://` OME-Zarr stores of any size by serving per-level tiles from the kernel to Viv over the anywidget message channel.

**Architecture:** A lenient NGFF metadata module (`anybioimage/ngff.py`) on top of zarr-python 3 replaces the hand-rolled urllib probe. A `ZarrBridgeMixin` answers `{kind:"chunk"}` messages with raw tile bytes, reading whole zarr chunk blocks once and caching every tile they contain (byte-budgeted LRU). The JS side reuses `AnywidgetPixelSource` (ported from `feature/viv-backend`) — one per pyramid level — feeding Viv's `MultiscaleImageLayer`. `_zarr_source.mode` selects `"url"` (browser-direct, unchanged) or `"bridge"`.

**Tech Stack:** Python 3.12, zarr-python 3.2, numpy, anywidget 0.11 / ipywidgets 8, pytest; JS: Viv 0.17.3, deck.gl 9, React 18, esbuild, vitest.

**Spec:** `docs/superpowers/specs/2026-09-02-zarr-chunk-bridge-design.md`

**Worktree:** all paths relative to `/var/home/maartenpaul/Documents/GitHub/anyimage/.worktrees/viv-reader` (branch `feature/viv-reader`). Run Python with `uv run …`. JS commands run inside `anybioimage/frontend/viewer/`.

**Test data:** `../../examples/image.zarr` (10T×3Z×2048², axes `t,z,y,x`, chunks `(10,16,512,512)`, big-endian, three levels `s0/s1/s2`). It lives in the main checkout, is gitignored, and is only used for the browser validation in Task 13.

---

## File map

| Path | Responsibility |
|---|---|
| `anybioimage/ngff.py` (new) | Lenient NGFF metadata: `parse_ome_attrs`, `open_group`, `read_ome_attrs`, `axes_from_multiscale`, `open_image` → `NgffImage`, `is_plate`, `plate_layout`, `fetch_http_attrs`, `fetch_http_array_meta`, `PlateError` |
| `anybioimage/mixins/zarr_bridge.py` (new) | `viv_dtype`, `BridgeCache`, `read_tile_block`, `ZarrBridgeMixin` (attach/detach, message handler) |
| `anybioimage/mixins/image_loading.py` | `set_image` dispatch; http probe rewired onto `ngff`; `mode` key on `_zarr_source`; `_looks_like_zarr_path` |
| `anybioimage/mixins/plate_loading.py` | `set_plate` via `ngff`; bridge branch in `_load_plate_image` |
| `anybioimage/mixins/__init__.py`, `anybioimage/viewer.py` | Register mixin, init/close bridge, `bridge_cache_bytes` traitlet |
| `pyproject.toml` | `zarr>=3.0` core dep; `remote` extra |
| `frontend/viewer/src/render/pixel-sources/anywidget-source.js` (+test) | Viv `PixelSource` over `model.send` (ported) |
| `frontend/viewer/src/render/pixel-sources/bridge-source.js` (+test) | `pickTileSize`, `openBridge` |
| `frontend/viewer/src/render/VivCanvas.jsx`, `src/entry.js`, `src/canvas2d-chrome.js` | Mode switch `url` / `bridge` |
| `tests/conftest.py` (new) | zarr store fixture builders (v0.4/zarr-v2, v0.5/zarr-v3, plate) |
| `tests/test_ngff.py`, `tests/test_zarr_bridge.py` (new); `tests/test_zarr_metadata.py`, `tests/test_zarr_detection.py`, `tests/test_plate_viv.py` (modified) | Tests |
| `examples/viv_local_zarr_demo.py` (new) | marimo demo for browser validation |
| `CLAUDE.md`, `README.md`, `CHANGELOG.md` | Docs |

---

### Task 0: Commit the in-flight WIP and fix its broken test

The worktree has uncommitted work (plate guard in `set_image`, `bioio-ome-zarr` dep, tests, `uv.lock`, showcase notebook). One test calls the autouse-stubbed function instead of the captured real one.

**Files:**
- Modify: `tests/test_zarr_metadata.py:185-187`

- [ ] **Step 1: Fix the test to use the real implementation**

In `tests/test_zarr_metadata.py`, inside `test_zarr_url_is_plate_detects_v04_and_v05`, replace the three `il._zarr_url_is_plate(` calls with `_real_is_plate(`:

```python
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert _real_is_plate("https://x/plate.zarr", {}) is True
    assert _real_is_plate("https://x/plate5.zarr", {}) is True
    assert _real_is_plate("https://x/img.zarr", {}) is False
```

And in `test_zarr_url_is_plate_swallows_network_errors` replace `il._zarr_url_is_plate(` with `_real_is_plate(`.

- [ ] **Step 2: Run the full suite**

Run: `uv run pytest tests/ -q`
Expected: `195 passed`

- [ ] **Step 3: Commit**

```bash
git add anybioimage/mixins/image_loading.py pyproject.toml tests/test_zarr_metadata.py uv.lock examples/viv_backend_showcase.py
git commit -m "feat(zarr): guard set_image against HCS plates; add bioio-ome-zarr dep; showcase notebook"
```

---

### Task 1: `ngff.py` — attrs parsing, group opening

**Files:**
- Create: `anybioimage/ngff.py`
- Create: `tests/conftest.py`
- Create: `tests/test_ngff.py`

- [ ] **Step 1: Write store fixture builders**

`tests/conftest.py`:

```python
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


def _write_levels(group, shape, chunks, n_levels, zarr_format):
    """Write level 0 = arange data, each next level = ::2 in y/x. Returns dataset paths."""
    data = _fill(shape)
    paths = []
    for lvl in range(n_levels):
        name = str(lvl)
        arr = group.create_array(
            name, shape=data.shape, chunks=tuple(min(c, s) for c, s in zip(chunks, data.shape)),
            dtype="uint16", zarr_format=zarr_format,
        )
        arr[:] = data
        paths.append(name)
        data = data[..., ::2, ::2]
    return paths


def write_v04_image(path, shape=(2, 3, 2, 64, 96), chunks=(1, 1, 1, 32, 32),
                    axes=AXES_TCZYX, n_levels=2, omero=True, empty_transforms=False):
    """NGFF v0.4 image in a zarr v2 store (attrs at top level)."""
    g = zarr.create_group(str(path), zarr_format=2)
    paths = _write_levels(g, shape, chunks, n_levels, 2)
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
        attrs["omero"] = {"channels": [
            {"label": f"Ch{i}", "color": c, "window": {"min": 0, "max": 65535, "start": 10, "end": 5000}}
            for i, c in enumerate(["ff0000", "00ff00", "0000ff"][: shape[1] if len(shape) == 5 else 1])
        ]}
    g.attrs.update(attrs)
    return str(path)


def write_v05_image(path, shape=(2, 3, 2, 64, 96), chunks=(1, 1, 1, 32, 32), n_levels=2):
    """NGFF v0.5 image in a zarr v3 store (attrs under `ome`)."""
    g = zarr.create_group(str(path), zarr_format=3)
    paths = _write_levels(g, shape, chunks, n_levels, 3)
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
            paths = _write_levels(ig, (1, 1, 1, 32, 32), (1, 1, 1, 16, 16), 1, 2)
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
```

- [ ] **Step 2: Write failing tests for parsing/opening**

`tests/test_ngff.py`:

```python
"""Lenient NGFF metadata reader."""
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


def test_open_group_accepts_path_str_and_group(v04_store):
    g1 = ngff.open_group(v04_store)
    g2 = ngff.open_group(__import__("pathlib").Path(v04_store))
    g3 = ngff.open_group(g1)
    assert isinstance(g1, zarr.Group) and isinstance(g2, zarr.Group) and g3 is g1


def test_open_group_missing_fsspec_backend_hint(monkeypatch):
    def boom(*a, **k):
        raise ImportError("Install s3fs to access S3")
    monkeypatch.setattr(zarr, "open_group", boom)
    with pytest.raises(ImportError, match=r"anybioimage\[remote\]"):
        ngff.open_group("s3://bucket/x.zarr")


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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_ngff.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'anybioimage.ngff'`

- [ ] **Step 4: Implement `ngff.py` (part 1)**

`anybioimage/ngff.py`:

```python
"""Lenient OME-NGFF metadata reader on top of zarr-python 3.

This is the ONE place that knows the NGFF attrs layout:
  * v0.4 and earlier keep ``multiscales`` / ``omero`` / ``plate`` / ``well`` at
    the top level of the group attrs (zarr v2 ``.zattrs``).
  * v0.5 and later nest them under an ``ome`` key (zarr v3 ``zarr.json``).

Store formats and remote filesystems are zarr-python's job. Parsing is
deliberately lenient: real-world writers omit axes, leave transforms empty, or
list datasets that do not exist. A viewer must still open those files.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import zarr

logger = logging.getLogger(__name__)

_DEFAULT_AXES = ["t", "c", "z", "y", "x"]


class PlateError(ValueError):
    """Raised when an HCS plate is opened where a single image was expected."""


def parse_ome_attrs(attrs: dict) -> tuple[str, dict]:
    """Return ``(version, ome_block)`` from raw group attrs.

    ``ome_block`` is the dict holding ``multiscales`` / ``omero`` / ``plate`` /
    ``well`` — the attrs themselves for v0.4, ``attrs["ome"]`` for v0.5+.
    ``version`` is ``"unknown"`` when no block declares one.
    """
    attrs = dict(attrs or {})
    ome = attrs.get("ome")
    if isinstance(ome, dict) and ome:
        return str(ome.get("version") or "0.5"), ome
    multiscales = attrs.get("multiscales") or []
    if multiscales and isinstance(multiscales[0], dict) and multiscales[0].get("version"):
        return str(multiscales[0]["version"]), attrs
    plate = attrs.get("plate")
    if isinstance(plate, dict) and plate.get("version"):
        return str(plate["version"]), attrs
    return "unknown", attrs


def open_group(src, storage_options: dict | None = None) -> zarr.Group:
    """Open ``src`` read-only: a ``zarr.Group``, local path, ``file://``,
    ``s3://``, ``gs://`` or ``http(s)://`` (the latter need fsspec backends)."""
    if isinstance(src, zarr.Group):
        return src
    src = str(src)
    kwargs = {"mode": "r"}
    if storage_options:
        kwargs["storage_options"] = storage_options
    try:
        return zarr.open_group(src, **kwargs)
    except ImportError as e:  # fsspec backend (s3fs / gcsfs / aiohttp) missing
        raise ImportError(
            f"Opening {src!r} needs an fsspec backend: pip install 'anybioimage[remote]' ({e})"
        ) from e


def read_ome_attrs(group: zarr.Group) -> tuple[str, dict]:
    """``parse_ome_attrs`` applied to a zarr group."""
    return parse_ome_attrs(dict(group.attrs))


def axes_from_multiscale(multiscale: dict, ndim: int) -> list[str]:
    """Axis names for a multiscale block, falling back to trailing TCZYX.

    Accepts v0.4 ``[{"name": "t", ...}]`` and v0.3 ``["t", ...]`` forms.
    Any mismatch with ``ndim`` uses the default so indexing stays sane.
    """
    raw = multiscale.get("axes") or []
    names = []
    for a in raw:
        name = a.get("name") if isinstance(a, dict) else a
        if name:
            names.append(str(name).lower())
    if len(names) != ndim:
        return _DEFAULT_AXES[-ndim:]
    return names
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_ngff.py -q`
Expected: `7 passed`

- [ ] **Step 6: Commit**

```bash
git add anybioimage/ngff.py tests/conftest.py tests/test_ngff.py
git commit -m "feat(ngff): lenient OME-NGFF attrs parser and group opener"
```

---

### Task 2: `ngff.open_image`, `NgffImage`, plate helpers

**Files:**
- Modify: `anybioimage/ngff.py`
- Modify: `tests/test_ngff.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_ngff.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ngff.py -q`
Expected: 9 new failures, `AttributeError: module 'anybioimage.ngff' has no attribute 'open_image'`

- [ ] **Step 3: Implement**

Append to `anybioimage/ngff.py`:

```python
@dataclass
class NgffImage:
    """One multiscale image: native pyramid levels plus the metadata a viewer needs."""

    group: zarr.Group
    version: str
    axes: list[str]                       # e.g. ["t", "c", "z", "y", "x"]; y always precedes x
    levels: list[zarr.Array]              # level 0 first (full resolution)
    dtype: np.dtype                       # level-0 dtype, native byte order
    omero_channels: list[dict] = field(default_factory=list)

    @property
    def shape(self) -> tuple[int, ...]:
        return tuple(int(s) for s in self.levels[0].shape)

    def size(self, axis: str) -> int:
        """Extent along ``axis``; 1 when the store has no such axis."""
        return self.shape[self.axes.index(axis)] if axis in self.axes else 1


def is_plate_attrs(ome: dict) -> bool:
    return isinstance(ome.get("plate"), dict)


def is_plate(group: zarr.Group) -> bool:
    return is_plate_attrs(read_ome_attrs(group)[1])


def plate_layout(group: zarr.Group) -> dict:
    """The raw ``plate`` block (rows / columns / wells) of an HCS plate group."""
    _, ome = read_ome_attrs(group)
    if not is_plate_attrs(ome):
        raise ValueError("No HCS plate metadata in group")
    return ome["plate"]


def open_image(src, storage_options: dict | None = None) -> NgffImage:
    """Open a multiscale image group leniently.

    Raises ``PlateError`` for HCS plate roots and ``ValueError`` when no usable
    multiscale arrays exist.
    """
    group = open_group(src, storage_options)
    version, ome = read_ome_attrs(group)
    if is_plate_attrs(ome):
        raise PlateError(f"{src!r} is an HCS plate, not a single image; use viewer.set_plate()")
    multiscales = ome.get("multiscales") or []
    if not multiscales or not isinstance(multiscales[0], dict):
        raise ValueError(f"No multiscales metadata in {src!r}")
    ms = multiscales[0]

    levels: list[zarr.Array] = []
    for ds in ms.get("datasets") or []:
        path = ds.get("path") if isinstance(ds, dict) else ds
        if path is None:
            continue
        try:
            node = group[str(path)]
        except KeyError:
            logger.warning("multiscales dataset %r missing in store; skipped", path)
            continue
        if isinstance(node, zarr.Array):
            levels.append(node)
    if not levels:
        raise ValueError(f"multiscales in {src!r} lists no readable arrays")

    axes = axes_from_multiscale(ms, levels[0].ndim)
    if "y" not in axes or "x" not in axes or axes.index("y") > axes.index("x"):
        raise ValueError(f"Unsupported axes order {axes}: need y before x")
    omero = ome.get("omero") or {}
    channels = [c for c in (omero.get("channels") or []) if isinstance(c, dict)]
    dtype = np.dtype(levels[0].dtype).newbyteorder("=")
    return NgffImage(group, version, axes, levels, dtype, channels)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ngff.py -q`
Expected: `16 passed`

- [ ] **Step 5: Commit**

```bash
git add anybioimage/ngff.py tests/test_ngff.py
git commit -m "feat(ngff): open_image -> NgffImage, plate detection"
```

---

### Task 3: Rewire the http probe onto `ngff`; add `mode` to `_zarr_source`

Replaces `_fetch_zarr_ome_metadata` / `_zarr_url_is_plate` internals with `ngff` helpers (same function names kept so existing monkeypatches still work). `_zarr_source` gains `"mode": "url"`.

**Files:**
- Modify: `anybioimage/ngff.py`
- Modify: `anybioimage/mixins/image_loading.py:107-168, 245-288`
- Modify: `tests/test_ngff.py`, `tests/test_zarr_metadata.py`

- [ ] **Step 1: Write failing tests for the http helpers**

Append to `tests/test_ngff.py`:

```python
def _fake_http(monkeypatch, samples: dict):
    """Patch urllib so `fetch_http_*` see `samples[url]` (dict → JSON, Exception → raised)."""
    import urllib.request
    from io import BytesIO

    class _Resp(BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): self.close()

    def fake_urlopen(req, timeout=30):
        body = samples.get(req.full_url)
        if body is None:
            raise OSError(f"404 {req.full_url}")
        return _Resp(json.dumps(body).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


import json  # noqa: E402  (used by _fake_http)


def test_fetch_http_attrs_v2(monkeypatch):
    _fake_http(monkeypatch, {"https://x/a.zarr/.zattrs": {"multiscales": [{"version": "0.4"}]}})
    assert ngff.fetch_http_attrs("https://x/a.zarr/", {}) == {"multiscales": [{"version": "0.4"}]}


def test_fetch_http_attrs_v3_zarr_json(monkeypatch):
    _fake_http(monkeypatch, {"https://x/b.zarr/zarr.json": {"zarr_format": 3, "node_type": "group",
                                                             "attributes": {"ome": {"version": "0.5"}}}})
    assert ngff.fetch_http_attrs("https://x/b.zarr", {}) == {"ome": {"version": "0.5"}}


def test_fetch_http_attrs_raises_when_neither(monkeypatch):
    _fake_http(monkeypatch, {})
    with pytest.raises(OSError):
        ngff.fetch_http_attrs("https://x/none.zarr", {})


def test_fetch_http_array_meta_v2_and_v3(monkeypatch):
    _fake_http(monkeypatch, {
        "https://x/a.zarr/0/.zarray": {"shape": [1, 2, 3, 4, 5], "dtype": ">u2"},
        "https://x/b.zarr/0/zarr.json": {"shape": [6, 7], "data_type": "float32"},
    })
    assert ngff.fetch_http_array_meta("https://x/a.zarr", "0", {}) == ([1, 2, 3, 4, 5], "uint16")
    assert ngff.fetch_http_array_meta("https://x/b.zarr", "0", {}) == ([6, 7], "float32")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ngff.py -q -k http`
Expected: 4 failed, `AttributeError: ... 'fetch_http_attrs'`

- [ ] **Step 3: Implement the http helpers**

Append to `anybioimage/ngff.py`:

```python
def _http_json(url: str, headers: dict | None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def fetch_http_attrs(url: str, headers: dict | None) -> dict:
    """Raw group attrs of an http(s) zarr root: ``.zattrs`` (v2) else
    ``zarr.json["attributes"]`` (v3). Kernel-side ``urllib`` — no CORS, no
    fsspec/aiohttp dependency. Raises ``OSError`` when neither exists."""
    base = url.rstrip("/")
    try:
        return _http_json(f"{base}/.zattrs", headers)
    except Exception as first:
        try:
            doc = _http_json(f"{base}/zarr.json", headers)
        except Exception:
            raise OSError(f"No .zattrs or zarr.json at {base}: {first}") from first
        return dict(doc.get("attributes") or {})


def fetch_http_array_meta(url: str, path: str, headers: dict | None) -> tuple[list[int], str]:
    """``(shape, numpy dtype name)`` of array ``path`` under an http(s) zarr root."""
    base = f"{url.rstrip('/')}/{path.strip('/')}"
    try:
        doc = _http_json(f"{base}/.zarray", headers)
        raw = doc.get("dtype", "<u2")
    except Exception:
        doc = _http_json(f"{base}/zarr.json", headers)
        raw = doc.get("data_type", "uint16")
    try:
        dtype = str(np.dtype(raw))
    except Exception:
        dtype = "uint16"
    return [int(s) for s in doc.get("shape", [])], dtype
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ngff.py -q`
Expected: `20 passed`

- [ ] **Step 5: Rewire `image_loading.py`**

Replace the whole `_fetch_zarr_ome_metadata` function (lines 107–145) and `_zarr_url_is_plate` (148–167) with:

```python
def _fetch_zarr_ome_metadata(url: str, headers: dict):
    """Fetch the OME block + level-0 array meta of an http(s) zarr root.

    Returns ``(ome, axes, shape, dtype_str)``. ``ome`` is the NGFF block
    (top-level attrs for v0.4, ``attrs["ome"]`` for v0.5) so
    ``_channel_settings_from_omero`` finds ``omero`` in both layouts.
    Raises on network error / unparseable JSON.
    """
    from .. import ngff

    attrs = ngff.fetch_http_attrs(url, headers)
    _, ome = ngff.parse_ome_attrs(attrs)
    multiscales = ome.get("multiscales") or []
    axes, shape, dtype_str = [], [], "uint16"
    if multiscales and isinstance(multiscales[0], dict):
        datasets = multiscales[0].get("datasets") or []
        path = datasets[0].get("path") if datasets and isinstance(datasets[0], dict) else None
        if path is not None:
            try:
                shape, dtype_str = ngff.fetch_http_array_meta(url, str(path), headers)
            except Exception:
                pass
        if shape:
            axes = ngff.axes_from_multiscale(multiscales[0], len(shape))
    return ome, axes, shape, dtype_str


def _zarr_url_is_plate(url: str, headers: dict) -> bool:
    """True if the http(s) zarr root is an HCS plate (v0.4 or v0.5 layout).
    Network/parse errors return False so the caller's normal path surfaces
    its own error instead of masking it as "not a plate"."""
    from .. import ngff

    try:
        _, ome = ngff.parse_ome_attrs(ngff.fetch_http_attrs(url, headers or {}))
    except Exception:
        return False
    return ngff.is_plate_attrs(ome)
```

In `_set_zarr_url` change the source assignment:

```python
        self._zarr_source = {"mode": "url", "url": url, "headers": headers or {}}
```

Also in `_update_slice` and `_prefetch_adjacent_slices` change the guard
`if getattr(self, "_zarr_source", {}).get("url"):` → `if getattr(self, "_zarr_source", {}).get("mode"):` (two places).

- [ ] **Step 6: Update `tests/test_zarr_metadata.py`**

- `test_zarr_url_populates_dims_and_source`: expected dict becomes `{"mode": "url", "url": "https://example.org/img.ome.zarr", "headers": {}}`.
- `test_zarr_url_is_plate_detects_v04_and_v05`: `fake_urlopen` must raise for unknown URLs (the new probe tries `.zattrs` then `zarr.json`). Replace its body's `return _Resp(...)` with:

```python
    def fake_urlopen(req, timeout=30):
        if req.full_url not in samples:
            raise OSError("404")
        return _Resp(json.dumps(samples[req.full_url]).encode())
```

- [ ] **Step 7: Run the suite**

Run: `uv run pytest tests/ -q`
Expected: all pass (`215 passed`)

- [ ] **Step 8: Commit**

```bash
git add anybioimage/ngff.py anybioimage/mixins/image_loading.py tests/test_ngff.py tests/test_zarr_metadata.py
git commit -m "refactor(zarr): route http metadata probe through ngff; tag _zarr_source with mode"
```

---

### Task 4: `zarr_bridge.py` — pure parts: dtype mapping, byte-budget cache, chunk-block tile read

**Files:**
- Create: `anybioimage/mixins/zarr_bridge.py`
- Create: `tests/test_zarr_bridge.py`

- [ ] **Step 1: Write failing tests**

`tests/test_zarr_bridge.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_zarr_bridge.py -q`
Expected: `ModuleNotFoundError: No module named 'anybioimage.mixins.zarr_bridge'`

- [ ] **Step 3: Implement the pure parts**

`anybioimage/mixins/zarr_bridge.py`:

```python
"""Kernel-side chunk bridge: serves per-level tiles of an ``NgffImage`` to Viv.

Protocol (anywidget custom messages):
  JS → Py  {"kind": "chunk", "requestId": int, "level": int, "t": int, "c": int, "z": int,
            "tx": int, "ty": int, "tileSize": int}
  Py → JS  {"kind": "chunk", "requestId": int, "ok": true, "w": int, "h": int, "dtype": str}
           + buffers=[raw little-endian C-order bytes, h*w elements]
        or {"kind": "chunk", "requestId": int, "ok": false, "error": str}

Performance rule: zarr decodes whole chunks, so a tile read costs the same as
reading every T/C/Z plane inside that chunk. ``read_tile_block`` therefore
reads the enclosing chunk block once and returns one tile per plane it covers;
the byte-budgeted ``BridgeCache`` keeps them for the next requests.
"""
from __future__ import annotations

import itertools
import logging
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from .. import ngff
from .image_loading import _channel_settings_from_omero

logger = logging.getLogger(__name__)

DEFAULT_CACHE_BYTES = 256 * 1024 ** 2
_VIV_DTYPES = {"uint8", "uint16", "uint32", "float32"}
_SPATIAL = ("y", "x")

TileKey = tuple  # (level, t, c, z, ty, tx)
TileValue = tuple  # (w, h, bytes)


def viv_dtype(dtype) -> np.dtype:
    """Native-endian dtype Viv can upload: uint8/16/32 or float32; others → float32."""
    dt = np.dtype(dtype).newbyteorder("=")
    return dt if dt.name in _VIV_DTYPES else np.dtype("float32")


class BridgeCache:
    """Thread-safe LRU of tiles bounded by total payload bytes.

    Eviction never removes the most recently inserted entry, so a block larger
    than the budget still serves the tile that triggered it.
    """

    def __init__(self, max_bytes: int = DEFAULT_CACHE_BYTES):
        self.max_bytes = int(max_bytes)
        self._d: OrderedDict[TileKey, TileValue] = OrderedDict()
        self.nbytes = 0
        self._lock = threading.Lock()

    def get(self, key: TileKey) -> TileValue | None:
        with self._lock:
            val = self._d.get(key)
            if val is not None:
                self._d.move_to_end(key)
            return val

    def put_many(self, items) -> None:
        with self._lock:
            for key, val in items:
                old = self._d.pop(key, None)
                if old is not None:
                    self.nbytes -= len(old[2])
                self._d[key] = val
                self.nbytes += len(val[2])
            while self.nbytes > self.max_bytes and len(self._d) > 1:
                _, old = self._d.popitem(last=False)
                self.nbytes -= len(old[2])

    def clear(self) -> None:
        with self._lock:
            self._d.clear()
            self.nbytes = 0

    def __len__(self) -> int:
        return len(self._d)


def read_tile_block(img: ngff.NgffImage, level: int, t: int, c: int, z: int,
                    tx: int, ty: int, tile_size: int, out_dtype: np.dtype,
                    max_block_bytes: int) -> dict[TileKey, TileValue]:
    """Read tile ``(tx, ty)`` of ``level`` plus every sibling plane sharing its zarr chunk.

    Returns ``{(level, t, c, z, ty, tx): (w, h, bytes)}``. Absent axes index as
    0. Raises ``IndexError`` when the tile or the t/c/z position is out of
    range. If the enclosing block would exceed ``max_block_bytes`` only the
    requested plane is read.
    """
    if level < 0 or level >= len(img.levels):
        raise IndexError(f"level {level} out of range")
    arr = img.levels[level]
    axes, shape, chunks = img.axes, tuple(int(s) for s in arr.shape), tuple(int(k) for k in arr.chunks)
    yi, xi = axes.index("y"), axes.index("x")
    y0, x0 = ty * tile_size, tx * tile_size
    if y0 >= shape[yi] or x0 >= shape[xi] or tx < 0 or ty < 0:
        raise IndexError(f"tile ({tx},{ty}) outside level {level} ({shape[xi]}x{shape[yi]})")
    y1, x1 = min(y0 + tile_size, shape[yi]), min(x0 + tile_size, shape[xi])
    wanted = {"t": t, "c": c, "z": z}

    # Non-spatial axes: read the full chunk span so siblings come for free.
    ranges: list[tuple[int, int]] = []          # (start, stop) per axis, spatial = tile extent
    block_elems = (y1 - y0) * (x1 - x0)
    for i, ax in enumerate(axes):
        if ax == "y":
            ranges.append((y0, y1))
        elif ax == "x":
            ranges.append((x0, x1))
        else:
            pos = int(wanted.get(ax, 0))
            if pos < 0 or pos >= shape[i]:
                raise IndexError(f"{ax}={pos} outside level {level} extent {shape[i]}")
            start = (pos // chunks[i]) * chunks[i]
            stop = min(start + chunks[i], shape[i])
            ranges.append((start, stop))
            block_elems *= stop - start
    if block_elems * out_dtype.itemsize > max_block_bytes:
        ranges = [(int(wanted.get(ax, 0)), int(wanted.get(ax, 0)) + 1) if ax not in _SPATIAL else r
                  for ax, r in zip(axes, ranges)]

    block = np.asarray(arr[tuple(slice(a, b) for a, b in ranges)])
    block = np.ascontiguousarray(block.astype(out_dtype, copy=False))

    non_spatial = [i for i, ax in enumerate(axes) if ax not in _SPATIAL]
    out: dict[TileKey, TileValue] = {}
    w, h = x1 - x0, y1 - y0
    for combo in itertools.product(*[range(ranges[i][0], ranges[i][1]) for i in non_spatial]):
        idx: list = [slice(None)] * len(axes)
        pos = {"t": 0, "c": 0, "z": 0}
        for i, val in zip(non_spatial, combo):
            idx[i] = val - ranges[i][0]
            pos[axes[i]] = val
        plane = block[tuple(idx)]
        out[(level, pos["t"], pos["c"], pos["z"], ty, tx)] = (w, h, plane.tobytes())
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_zarr_bridge.py -q`
Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add anybioimage/mixins/zarr_bridge.py tests/test_zarr_bridge.py
git commit -m "feat(bridge): chunk-aware tile reader and byte-budget LRU cache"
```

---

### Task 5: `ZarrBridgeMixin` — attach/detach, message handler, viewer wiring

**Files:**
- Modify: `anybioimage/mixins/zarr_bridge.py`
- Modify: `anybioimage/mixins/__init__.py`
- Modify: `anybioimage/viewer.py:166-176, 193-224, 226-237`
- Modify: `tests/test_zarr_bridge.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_zarr_bridge.py`:

```python
import time

from anybioimage import BioImageViewer


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
    assert ch["data_min"] == 0.0 and 0.0 < ch["data_max"] <= 65535.0
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


def test_sibling_tile_is_cache_hit(viv, v04_store, monkeypatch):
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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_zarr_bridge.py -q`
Expected: new tests fail with `AttributeError: 'BioImageViewer' object has no attribute '_attach_bridge'`

- [ ] **Step 3: Implement the mixin**

Append to `anybioimage/mixins/zarr_bridge.py`:

```python
_RANGE_SAMPLE_MAX_PIXELS = 4 * 1024 * 1024


def _default_channel_ranges(img: ngff.NgffImage, dim_c: int) -> list[tuple[float, float]]:
    """Per-channel (min, max) from the lowest pyramid level at t=0, z=middle.

    Only used when the store has no ``omero`` block. Skipped (dtype range
    instead) when the lowest level is still bigger than 4 MP.
    """
    arr = img.levels[-1]
    axes = img.axes
    shape = tuple(int(s) for s in arr.shape)
    if shape[axes.index("y")] * shape[axes.index("x")] > _RANGE_SAMPLE_MAX_PIXELS:
        return []
    idx: list = []
    for i, ax in enumerate(axes):
        if ax in _SPATIAL or ax == "c":
            idx.append(slice(None))
        elif ax == "z":
            idx.append(shape[i] // 2)
        else:
            idx.append(0)
    data = np.asarray(arr[tuple(idx)])
    if "c" in axes:
        c_axis = [ax for ax in axes if ax in ("c", "y", "x")].index("c")
        data = np.moveaxis(data, c_axis, 0)
    else:
        data = data[None]
    out = []
    for ci in range(dim_c):
        plane = data[min(ci, data.shape[0] - 1)]
        out.append((float(plane.min()), float(plane.max())))
    return out


class ZarrBridgeMixin:
    """Serve tiles of an ``NgffImage`` to the Viv frontend over ``model.send``.

    Attributes expected from the host widget: ``_zarr_source``, ``dim_*``,
    ``height``, ``width``, ``current_t``, ``current_z``, ``_channel_settings``,
    ``image_data``, ``_render_ready``, ``bridge_cache_bytes``, ``_precompute_event``,
    ``_precompute_future``, ``_full_array``, ``_bioimage``, ``send``, ``on_msg``.
    """

    def _init_bridge(self) -> None:
        self._bridge_image: ngff.NgffImage | None = None
        self._bridge_dtype = np.dtype("uint16")
        self._bridge_cache = BridgeCache(int(getattr(self, "bridge_cache_bytes", DEFAULT_CACHE_BYTES)))
        self._bridge_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="zarr-bridge")
        self._bridge_send_lock = threading.Lock()
        self.on_msg(self._on_bridge_msg)
        self.observe(self._on_bridge_cache_bytes, names=["bridge_cache_bytes"])

    def _close_bridge(self) -> None:
        ex = getattr(self, "_bridge_executor", None)
        if ex is not None:
            ex.shutdown(wait=False, cancel_futures=True)
        self._bridge_image = None

    def _on_bridge_cache_bytes(self, change) -> None:
        self._bridge_cache.max_bytes = int(change["new"])
        self._bridge_cache.put_many([])  # trigger eviction under the new budget

    # ---- attach / detach -------------------------------------------------

    def _attach_bridge(self, img: ngff.NgffImage) -> None:
        """Point the viv frontend at ``img`` via the chunk bridge."""
        out_dtype = viv_dtype(img.dtype)
        if out_dtype != img.dtype:
            logger.warning("dtype %s not GPU-uploadable; serving as float32", img.dtype)

        if getattr(self, "_precompute_event", None) is not None:
            self._precompute_event.set()
        self._precompute_future = None
        self._full_array = None
        self._bioimage = None
        self._bridge_cache.clear()
        self._bridge_image = img
        self._bridge_dtype = out_dtype

        dim_c = img.size("c")
        channels = _channel_settings_from_omero({"omero": {"channels": img.omero_channels}}, dim_c, out_dtype)
        if not img.omero_channels:
            for ch, (lo, hi) in zip(channels, _default_channel_ranges(img, dim_c)):
                if hi > lo:
                    ch["data_min"], ch["data_max"] = lo, hi
                    ch["min"], ch["max"] = 0.0, 1.0

        with self.hold_trait_notifications():
            self.dim_t = img.size("t")
            self.dim_c = dim_c
            self.dim_z = img.size("z")
            self.height = img.size("y")
            self.width = img.size("x")
            self.current_t = 0
            self.current_z = 0
            self._channel_settings = channels
            self.image_data = ""
            self._render_ready = False
        self._zarr_source = {
            "mode": "bridge",
            "levels": [{"shape": [int(s) for s in a.shape], "chunks": [int(k) for k in a.chunks]}
                       for a in img.levels],
            "labels": list(img.axes),
            "dtype": out_dtype.name,
        }
        logger.info("Viv backend: kernel chunk bridge attached (%d levels, %s)", len(img.levels), out_dtype.name)

    def _detach_bridge(self) -> None:
        """Forget the bridged image (called when a non-bridge image is loaded)."""
        self._bridge_image = None
        cache = getattr(self, "_bridge_cache", None)
        if cache is not None:
            cache.clear()

    # ---- message handling ------------------------------------------------

    def _on_bridge_msg(self, widget, content, buffers) -> None:
        if not isinstance(content, dict) or content.get("kind") != "chunk":
            return
        self._bridge_executor.submit(self._serve_chunk, content)

    def _serve_chunk(self, req: dict) -> None:
        rid = req.get("requestId")
        try:
            img = self._bridge_image
            if img is None:
                raise RuntimeError("no bridged image attached")
            key = (int(req.get("level", 0)), int(req.get("t", 0)), int(req.get("c", 0)),
                   int(req.get("z", 0)), int(req["ty"]), int(req["tx"]))
            w, h, data = self._bridge_tile(img, key, int(req.get("tileSize", 512)))
            reply = {"kind": "chunk", "requestId": rid, "ok": True, "w": w, "h": h,
                     "dtype": self._bridge_dtype.name}
            with self._bridge_send_lock:
                self.send(reply, buffers=[data])
        except Exception as e:
            logger.debug("chunk request %r failed: %s", req, e)
            with self._bridge_send_lock:
                self.send({"kind": "chunk", "requestId": rid, "ok": False, "error": f"{type(e).__name__}: {e}"})

    def _bridge_tile(self, img: ngff.NgffImage, key: TileKey, tile_size: int) -> TileValue:
        hit = self._bridge_cache.get(key)
        if hit is not None:
            return hit
        level, t, c, z, ty, tx = key
        tiles = read_tile_block(img, level, t, c, z, tx, ty, tile_size, self._bridge_dtype,
                                max_block_bytes=self._bridge_cache.max_bytes)
        self._bridge_cache.put_many(tiles.items())
        return tiles[key]
```

- [ ] **Step 4: Register the mixin and wire the viewer**

`anybioimage/mixins/__init__.py` — add the import and export alongside the others:

```python
from .zarr_bridge import ZarrBridgeMixin
```
and add `"ZarrBridgeMixin"` to `__all__` (check the file's existing pattern and match it).

`anybioimage/viewer.py`:
1. Import: add `ZarrBridgeMixin` to the `from .mixins import (...)` block and to the `class BioImageViewer(...)` bases (put it after `ImageLoadingMixin`).
2. Traitlet, next to `_render_ready`:

```python
    # Byte budget of the kernel-side tile cache used by the zarr chunk bridge
    bridge_cache_bytes = traitlets.Int(256 * 1024 * 1024).tag(sync=False)
```
3. In `__init__`, after `self._render_backend = render_backend`:

```python
        self._init_bridge()
```
4. In `close()`, before `super().close()`:

```python
        if hasattr(self, "_close_bridge"):
            self._close_bridge()
```

`anybioimage/mixins/image_loading.py` — in `_set_numpy_image` and `_set_bioimage`, right after the existing `self._zarr_source = {}` reset, add:

```python
        if hasattr(self, "_detach_bridge"):
            self._detach_bridge()
```
and in `_set_zarr_url` after `self._bioimage = None` add the same two lines.

- [ ] **Step 5: Run the suite**

Run: `uv run pytest tests/ -q`
Expected: all pass (`225 passed`)

- [ ] **Step 6: Commit**

```bash
git add anybioimage/mixins/zarr_bridge.py anybioimage/mixins/__init__.py anybioimage/viewer.py anybioimage/mixins/image_loading.py tests/test_zarr_bridge.py
git commit -m "feat(bridge): ZarrBridgeMixin serves NgffImage tiles over anywidget messages"
```

---

### Task 6: `set_image` dispatch for local paths, `s3://`/`gs://`, `zarr.Group`

**Files:**
- Modify: `anybioimage/mixins/image_loading.py:26-52, 211-244, 290-295`
- Modify: `tests/test_zarr_detection.py`, `tests/test_zarr_metadata.py`

- [ ] **Step 1: Write failing tests**

Replace `tests/test_zarr_detection.py` with:

```python
"""Zarr input detectors: browser-fetchable URLs vs kernel-only paths."""
from pathlib import Path

import numpy as np
import pytest

from anybioimage.mixins.image_loading import _looks_like_zarr_path, _looks_like_zarr_url


@pytest.mark.parametrize("source", [
    "https://example.com/my.ome.zarr",
    "https://example.com/my.ome.zarr/",
    "http://localhost:8000/plate.zarr",
    "https://example.com/MY.OME.ZARR",
    "https://example.com/my.zarr?versionId=abc123",
])
def test_http_urls_detected(source):
    assert _looks_like_zarr_url(source) is True
    assert _looks_like_zarr_path(source) is False


@pytest.mark.parametrize("source", [
    "/tmp/my.ome.zarr",
    "./examples/image.zarr",
    "examples/image.zarr/",
    Path("/data/x.zarr"),
    "file:///data/my.ome.zarr",
    "s3://bucket/key/my.ome.zarr",
    "gs://bucket/my.zarr",
    "S3://BUCKET/X.ZARR",
])
def test_kernel_paths_detected(source):
    assert _looks_like_zarr_path(source) is True
    assert _looks_like_zarr_url(source) is False


@pytest.mark.parametrize("source", [
    "", "https://example.com/image.tif", "/tmp/image.png", "/tmp/foo.zarr.bak",
    "file:///data/movie.mp4", None, 42, np.zeros((4, 4)),
])
def test_non_zarr_rejected(source):
    assert _looks_like_zarr_url(source) is False
    assert _looks_like_zarr_path(source) is False
```

Append to `tests/test_zarr_metadata.py`:

```python
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


def test_bridge_then_url_switches_mode(viv_viewer, v04_store):
    viv_viewer.set_image(v04_store)
    assert viv_viewer._zarr_source["mode"] == "bridge"
    viv_viewer.set_image("https://example.org/img.ome.zarr")
    assert viv_viewer._zarr_source["mode"] == "url" and viv_viewer._bridge_image is None
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_zarr_detection.py tests/test_zarr_metadata.py -q`
Expected: `ImportError: cannot import name '_looks_like_zarr_path'` and failures in the new metadata tests

- [ ] **Step 3: Implement detection and dispatch**

In `anybioimage/mixins/image_loading.py` replace the `_URL_SCHEMES` constant and `_looks_like_zarr_url` with:

```python
_HTTP_SCHEMES = ("http://", "https://")
_KERNEL_SCHEMES = ("file://", "s3://", "gs://", "gcs://", "az://", "abfs://")


def _strip_zarr_suffix_candidate(s: str) -> str:
    return s.split("?", 1)[0].split("#", 1)[0].rstrip("/").lower()


def _looks_like_zarr_url(s) -> bool:
    """True for http(s) strings pointing at a ``.zarr`` path — the only stores
    the browser can fetch directly (Viv path on the viv backend)."""
    if not isinstance(s, str) or not s.lower().startswith(_HTTP_SCHEMES):
        return False
    return _strip_zarr_suffix_candidate(s).endswith(_ZARR_SUFFIXES)


def _looks_like_zarr_path(s) -> bool:
    """True for ``.zarr`` inputs only the kernel can open: local paths
    (``str``/``Path``) and fsspec URLs (``file://``, ``s3://``, ``gs://`` …).
    These go through the chunk bridge on the viv backend, bioio on Canvas2D."""
    from pathlib import Path

    if isinstance(s, Path):
        s = str(s)
    if not isinstance(s, str) or not s:
        return False
    lower = s.lower()
    if lower.startswith(_HTTP_SCHEMES):
        return False
    if "://" in lower and not lower.startswith(_KERNEL_SCHEMES):
        return False
    return _strip_zarr_suffix_candidate(s).endswith(_ZARR_SUFFIXES)
```

Replace the `set_image` method (signature through the `# --- existing main dispatch` comment) with:

```python
    def set_image(self, data, headers: dict | None = None, storage_options: dict | None = None):
        """Set the base image from a numpy array, BioImage object, OME-Zarr
        path/URL, or ``zarr.Group``.

        Args:
            data: numpy array, BioImage, ``zarr.Group``, local ``.zarr`` path
                  (``str``/``Path``), ``s3://``/``gs://``/``file://`` zarr URL,
                  or ``http(s)`` URL ending in ``.zarr`` / ``.ome.zarr``.
            headers: optional HTTP headers for http(s) zarr URLs (auth etc.).
            storage_options: optional fsspec options for ``s3://``/``gs://``
                  stores (credentials, ``anon``, endpoints).
        """
        import zarr

        backend = getattr(self, "_render_backend", "canvas2d")

        if isinstance(data, zarr.Group) or _looks_like_zarr_path(data):
            self._set_zarr_path(data, storage_options)
            return

        if _looks_like_zarr_url(data):
            if _zarr_url_is_plate(data, headers or {}):
                raise ValueError(
                    f"{data} is an HCS plate, not a single image. "
                    f"Use viewer.set_plate(url) instead of set_image(url) — "
                    f"it adds Well/FOV selectors for plate navigation."
                )
            if backend == "viv":
                try:
                    self._set_zarr_url(data, headers or {})
                    return
                except Exception as e:
                    logger.info(
                        "Viv zarr metadata load failed (%s); falling back to Canvas2D", e
                    )
            self._set_zarr_url_canvas2d(data)
            return
        if backend == "viv":
            logger.info("Non-zarr input on viv backend; rendering via Canvas2D pipeline.")
        # --- existing main dispatch, unchanged ---
        if hasattr(data, "dims") and hasattr(data, "dask_data"):
            self._set_bioimage(data)
        else:
            self._set_numpy_image(data)

    def _set_zarr_path(self, data, storage_options: dict | None) -> None:
        """Kernel-openable zarr (local / fsspec / Group): chunk bridge on viv,
        bioio on Canvas2D. Plates raise; other viv failures fall back to bioio."""
        import zarr

        from .. import ngff

        if getattr(self, "_render_backend", "canvas2d") == "viv":
            try:
                img = ngff.open_image(data, storage_options)
            except ngff.PlateError as e:
                raise ValueError(
                    f"{e}. Use viewer.set_plate(path) instead of set_image(path) — "
                    f"it adds Well/FOV selectors for plate navigation."
                ) from e
            except Exception as e:
                logger.info("Viv chunk-bridge open failed (%s); falling back to Canvas2D", e)
            else:
                self._attach_bridge(img)
                return
        if isinstance(data, zarr.Group):
            raise TypeError("zarr.Group input requires BioImageViewer(render_backend='viv')")
        self._set_zarr_url_canvas2d(str(data))
```

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/ -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add anybioimage/mixins/image_loading.py tests/test_zarr_detection.py tests/test_zarr_metadata.py
git commit -m "feat(zarr): set_image routes local/s3/gs zarr and zarr.Group through the chunk bridge on viv"
```

---

### Task 7: Plates through `ngff` + bridge per FOV

**Files:**
- Modify: `anybioimage/mixins/plate_loading.py`
- Modify: `tests/test_plate_viv.py`

- [ ] **Step 1: Update tests**

In `tests/test_plate_viv.py` replace `test_local_plate_on_viv_uses_bioio` with:

```python
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
    monkeypatch.setattr(v, "_attach_bridge", lambda img: (_ for _ in ()).throw(OSError("boom")))
    monkeypatch.setattr(v, "_load_plate_image_bioio", lambda p: called.setdefault("path", p))
    v.set_plate(plate_store)
    assert called["path"] == f"{plate_store}/A/1/0"


def test_canvas2d_local_plate_still_bioio(monkeypatch, plate_store):
    v = BioImageViewer()
    called = {}
    monkeypatch.setattr(v, "_load_plate_image_bioio", lambda p: called.setdefault("path", p))
    v.set_plate(plate_store)
    assert called["path"] == f"{plate_store}/A/1/0"
    assert v._zarr_source == {}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_plate_viv.py -q`
Expected: the three new tests fail (`_zarr_source == {}` / bioio import path taken)

- [ ] **Step 3: Implement**

In `anybioimage/mixins/plate_loading.py`:

Replace the body of `set_plate` from `import zarr` through the `plate_meta` selection with:

```python
        from .. import ngff

        store = ngff.open_group(path, storage_options)
        plate_meta = ngff.plate_layout(store)   # raises ValueError if not a plate
```
and change the signature to `def set_plate(self, path, storage_options: dict | None = None):` (document `storage_options` in the docstring as fsspec options for remote stores). Keep everything after (`self._plate_path = str(path)` onward) unchanged.

In `_load_well_fovs` replace the `well_attrs` / `well_meta` block (from `well_attrs = dict(well_group.attrs)` through the `else:` fallback) with:

```python
        from .. import ngff

        _, well_ome = ngff.read_ome_attrs(well_group)
        well_meta = well_ome.get("well") or {"images": []}
```

Replace `_load_plate_image` with:

```python
    def _load_plate_image(self, fov):
        """Load the image for the current well and given FOV.

        viv backend: http(s) plates hand the FOV subpath to the browser
        (``_set_zarr_url``); every other plate the kernel can open goes through
        the chunk bridge (``_attach_bridge``). Failures fall back to bioio.
        Canvas2D backend: bioio, unchanged.

        Args:
            fov: FOV path within the well (e.g., "0").
        """
        if not hasattr(self, "_current_well_path"):
            return

        image_path = f"{self._plate_path}/{self._current_well_path}/{fov}"

        if getattr(self, "_render_backend", "canvas2d") == "viv":
            try:
                if str(self._plate_path).lower().startswith(("http://", "https://")):
                    self._set_zarr_url(image_path, {})
                else:
                    from .. import ngff

                    self._attach_bridge(ngff.open_image(self._plate_store[f"{self._current_well_path}/{fov}"]))
                return
            except Exception as e:
                logger.info("Viv plate FOV load failed (%s); falling back to bioio", e)

        self._load_plate_image_bioio(image_path)
```

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/ -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add anybioimage/mixins/plate_loading.py tests/test_plate_viv.py
git commit -m "feat(plate): read plate/well metadata via ngff; bridge FOVs on viv for local plates"
```

---

### Task 8: Dependencies

**Files:**
- Modify: `pyproject.toml:26-52`

- [ ] **Step 1: Edit**

In `dependencies` add `"zarr>=3.0",` after `"bioio-ome-zarr",`. Add a new extra and include it in `all`/`complete`:

```toml
remote = [
    "s3fs>=2024.0",
    "gcsfs>=2024.0",
]
all = [
    "anybioimage[contours,bioio,remote,dev]",
]
complete = [
    "anybioimage[sam,contours,bioio,remote,dev]",
]
```

- [ ] **Step 2: Re-lock and verify import**

Run: `uv lock && uv sync --extra all && uv run python -c "import zarr, s3fs; print(zarr.__version__)"`
Expected: prints `3.x.x`, no errors

- [ ] **Step 3: Run suite + commit**

Run: `uv run pytest tests/ -q` → all pass

```bash
git add pyproject.toml uv.lock
git commit -m "build: zarr>=3 core dependency; remote extra for s3fs/gcsfs"
```

---

### Task 9: JS — port `AnywidgetPixelSource`

**Files:**
- Create: `anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.js`
- Create: `anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.test.js`

- [ ] **Step 1: Copy from the sibling worktree**

```bash
cp ../viv-backend/anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.js      anybioimage/frontend/viewer/src/render/pixel-sources/
cp ../viv-backend/anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.test.js anybioimage/frontend/viewer/src/render/pixel-sources/
```

- [ ] **Step 2: Add a failing test for label-aware `getRaster`**

Append to `anywidget-source.test.js` inside the `describe` block:

```js
  it('getRaster uses labels to find y/x extents (no t axis)', async () => {
    const model = mockModel((msg) => {
      queueMicrotask(() => model.emit('msg:custom',
        { kind: 'chunk', requestId: msg.requestId, ok: true, w: 2, h: 2, dtype: 'uint8' },
        [new Uint8Array([1, 2, 3, 4]).buffer]));
    });
    const src = new AnywidgetPixelSource(model, {
      shape: [3, 2, 2], dtype: 'Uint8', tileSize: 2, labels: ['z', 'y', 'x'],
    });
    const out = await src.getRaster({ selection: { z: 1 }, signal: new AbortController().signal });
    expect(out.width).toBe(2);
    expect(out.height).toBe(2);
    expect(Array.from(out.data)).toEqual([1, 2, 3, 4]);
  });
```

- [ ] **Step 3: Run vitest to see it fail**

Run (in `anybioimage/frontend/viewer/`): `npm test`
Expected: the new test fails (`getRaster` reads `this._shape[3]`/`[4]` → undefined width)

- [ ] **Step 4: Fix `getRaster` in `anywidget-source.js`**

Replace the first line of `getRaster`'s body `const [, , , yLen, xLen] = this._shape;` with:

```js
    const yLen = this._shape[this._labels.indexOf('y')];
    const xLen = this._shape[this._labels.indexOf('x')];
```

Also update the header comment's protocol line to mention `level`:

```js
 *   JS → Py : { kind: "chunk", requestId, level, t, c, z, tx, ty, tileSize }
```

- [ ] **Step 5: Run vitest**

Run: `npm test`
Expected: all pass (15 existing + 6 = `21 passed`)

- [ ] **Step 6: Commit**

```bash
git add anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.js anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.test.js
git commit -m "feat(frontend): port AnywidgetPixelSource (kernel chunk bridge PixelSource)"
```

---

### Task 10: JS — `bridge-source.js`

**Files:**
- Create: `anybioimage/frontend/viewer/src/render/pixel-sources/bridge-source.js`
- Create: `anybioimage/frontend/viewer/src/render/pixel-sources/bridge-source.test.js`

- [ ] **Step 1: Write failing tests**

`bridge-source.test.js`:

```js
import { describe, it, expect } from 'vitest';
import { openBridge, pickTileSize } from './bridge-source.js';

const LABELS = ['t', 'c', 'z', 'y', 'x'];

function mockModel() {
  return { send: () => {}, on: () => {}, off: () => {} };
}

describe('pickTileSize', () => {
  it('uses square power-of-two yx chunks within [256, 1024]', () => {
    expect(pickTileSize([10, 16, 512, 512], ['t', 'z', 'y', 'x'])).toBe(512);
    expect(pickTileSize([1, 1, 1, 256, 256], LABELS)).toBe(256);
    expect(pickTileSize([1, 1, 1, 1024, 1024], LABELS)).toBe(1024);
  });
  it('falls back to 512 otherwise', () => {
    expect(pickTileSize([1, 1, 1, 32, 32], LABELS)).toBe(512);     // too small
    expect(pickTileSize([1, 1, 1, 2048, 2048], LABELS)).toBe(512); // too big
    expect(pickTileSize([1, 1, 1, 512, 256], LABELS)).toBe(512);   // not square
    expect(pickTileSize([1, 1, 1, 300, 300], LABELS)).toBe(512);   // not pow2
    expect(pickTileSize(undefined, LABELS)).toBe(512);
  });
});

describe('openBridge', () => {
  it('builds one source per level with shared tileSize/dtype/labels', () => {
    const srcs = openBridge(mockModel(), {
      mode: 'bridge', dtype: 'uint16', labels: ['t', 'z', 'y', 'x'],
      levels: [
        { shape: [10, 3, 2048, 2048], chunks: [10, 16, 512, 512] },
        { shape: [10, 3, 1024, 1024], chunks: [10, 16, 512, 512] },
      ],
    });
    expect(srcs).toHaveLength(2);
    expect(srcs[0].shape).toEqual([10, 3, 2048, 2048]);
    expect(srcs[1].shape).toEqual([10, 3, 1024, 1024]);
    expect(srcs[0].tileSize).toBe(512);
    expect(srcs[1].tileSize).toBe(512);
    expect(srcs[0].dtype).toBe('Uint16');
    expect(srcs[0].labels).toEqual(['t', 'z', 'y', 'x']);
    expect(srcs[1]._level).toBe(1);
  });
  it('returns [] for a source without levels', () => {
    expect(openBridge(mockModel(), { mode: 'bridge' })).toEqual([]);
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm test`
Expected: `Failed to resolve import "./bridge-source.js"`

- [ ] **Step 3: Implement**

`bridge-source.js`:

```js
// anybioimage/frontend/viewer/src/render/pixel-sources/bridge-source.js
// Build Viv PixelSources for a kernel-served zarr (`_zarr_source.mode === "bridge"`).
// One AnywidgetPixelSource per pyramid level; Viv's MultiscaleImageLayer reads
// tileSize/dtype from level 0 and calls getTile on whichever level it selects.
import { AnywidgetPixelSource } from './anywidget-source.js';

const DEFAULT_TILE = 512;

/** Tile size that lines up with the store's yx chunks when they are square,
 *  a power of two, and within [256, 1024]; otherwise 512. */
export function pickTileSize(chunks, labels) {
  if (!Array.isArray(chunks) || !Array.isArray(labels)) return DEFAULT_TILE;
  const cy = chunks[labels.indexOf('y')];
  const cx = chunks[labels.indexOf('x')];
  const pow2 = Number.isInteger(cy) && cy > 0 && (cy & (cy - 1)) === 0;
  if (cy === cx && pow2 && cy >= 256 && cy <= 1024) return cy;
  return DEFAULT_TILE;
}

export function openBridge(model, zarrSource) {
  const levels = Array.isArray(zarrSource?.levels) ? zarrSource.levels : [];
  const labels = zarrSource?.labels || ['t', 'c', 'z', 'y', 'x'];
  const dtype = AnywidgetPixelSource.dtypeFromPython(zarrSource?.dtype);
  const tileSize = pickTileSize(levels[0]?.chunks, labels);
  return levels.map((lvl, level) => new AnywidgetPixelSource(model, {
    shape: lvl.shape, dtype, tileSize, level, labels,
  }));
}
```

- [ ] **Step 4: Run vitest → pass; commit**

Run: `npm test` → all pass

```bash
git add anybioimage/frontend/viewer/src/render/pixel-sources/bridge-source.js anybioimage/frontend/viewer/src/render/pixel-sources/bridge-source.test.js
git commit -m "feat(frontend): openBridge builds per-level PixelSources for the chunk bridge"
```

---

### Task 11: JS — mode switch in `VivCanvas`, `entry.js`, chrome guards; rebuild bundle

**Files:**
- Modify: `anybioimage/frontend/viewer/src/render/VivCanvas.jsx:39-58, 96`
- Modify: `anybioimage/frontend/viewer/src/entry.js:27-31`
- Modify: `anybioimage/frontend/viewer/src/canvas2d-chrome.js:98, 1047`
- Rebuild: `anybioimage/frontend/viewer/dist/viewer-bundle.js`

- [ ] **Step 1: `VivCanvas.jsx`**

Add the import:

```js
import { openBridge } from './pixel-sources/bridge-source.js';
```

Replace the source-loading `useEffect` (the one depending on `[zarrSource?.url]`) with:

```jsx
  useEffect(() => {
    let cancelled = false;
    let bridgeSources = null;
    async function run() {
      setError(null);
      const mode = zarrSource?.mode;
      if (!mode) { setSources(null); return; }
      try {
        let srcs;
        if (mode === 'bridge') {
          bridgeSources = openBridge(model, zarrSource);
          srcs = bridgeSources;
        } else {
          ({ sources: srcs } = await openOmeZarr(zarrSource.url, zarrSource.headers || {}));
        }
        if (!cancelled) setSources(srcs);
      } catch (e) {
        if (!cancelled) { setError(classifyLoadError(e, zarrSource.url || '(kernel bridge)')); setSources(null); }
      }
    }
    run();
    return () => {
      cancelled = true;
      if (bridgeSources) bridgeSources.forEach((s) => s.destroy());
    };
  }, [zarrSource, model]);
```

Change `if (!zarrSource?.url) return null;` → `if (!zarrSource?.mode) return null;`.

- [ ] **Step 2: `entry.js`**

In `syncMode`: `const viv = Boolean((model.get('_zarr_source') || {}).url);` → `const viv = Boolean((model.get('_zarr_source') || {}).mode);`. Update the file header comment: "switched on `_zarr_source.mode`".

- [ ] **Step 3: `canvas2d-chrome.js` guards (lines 98 and 1047)**

Both occurrences: `(model.get('_zarr_source') || {}).url` → `(model.get('_zarr_source') || {}).mode`. Update the adjacent comment "when a zarr URL is active" → "when a zarr source (URL or kernel bridge) is active".

- [ ] **Step 4: Rebuild, test, size gate**

Run (in `anybioimage/frontend/viewer/`):
```bash
npm run build && npm test && npm run size
```
Expected: bundle written, vitest green, size-limit under 4 MB.

- [ ] **Step 5: Python suite still green**

Run: `uv run pytest tests/ -q` → all pass (the canvas2d chrome is served raw; `test_backends.py` byte-checks may compare against the file — they must still pass).

- [ ] **Step 6: Commit**

```bash
git add anybioimage/frontend/viewer/src/render/VivCanvas.jsx anybioimage/frontend/viewer/src/entry.js anybioimage/frontend/viewer/src/canvas2d-chrome.js anybioimage/frontend/viewer/dist/viewer-bundle.js
git commit -m "feat(frontend): switch Viv canvas on _zarr_source.mode (url | bridge); rebuild bundle"
```

---

### Task 12: Docs

**Files:**
- Modify: `CLAUDE.md` (Rendering backends section), `README.md` (Rendering backends), `CHANGELOG.md`

- [ ] **Step 1: CLAUDE.md**

In the "Rendering backends" section replace the paragraph starting `**Viv** handles URL-schemed remote OME-Zarr only` with:

```markdown
**Viv** renders OME-Zarr in two ways, selected by `_zarr_source.mode`:
- `"url"` — `http(s)://…zarr` strings: browser-direct chunk fetch via Viv's `loadOmeZarr` (zarr v2 only; the server must allow CORS).
- `"bridge"` — local paths (`str`/`Path`), `file://`, `s3://`, `gs://` and `zarr.Group` inputs: the kernel opens the store with zarr-python 3 (v2 + v3) and serves per-level tiles over `model.send` (`anybioimage/mixins/zarr_bridge.py` ↔ `src/render/pixel-sources/anywidget-source.js`). Reads whole zarr chunk blocks once and caches every tile they contain in a byte-budgeted LRU (`viewer.bridge_cache_bytes`, default 256 MB). No full-plane loads, no RAM cap.

Everything else (numpy, BioImage, TIFF/CZI paths) silently falls back to Canvas2D (one `INFO` log line).

**NGFF metadata** lives in one module, `anybioimage/ngff.py` (lenient v0.4 top-level / v0.5+ `ome` block parsing, `open_image → NgffImage`, plate helpers, http probe). Spec changes go there; fixtures per version are in `tests/conftest.py`.
```

Add to the traitlets list: ``- `bridge_cache_bytes` (`Int`, not synced) — byte budget of the kernel tile cache``. Update the `_zarr_source` bullet to: ``{mode:"url", url, headers}`` or ``{mode:"bridge", levels:[{shape,chunks}], labels, dtype}``.

- [ ] **Step 2: README.md**

In the backends table change the `viv` row's "Best for" to `OME-Zarr — remote URLs browser-direct; local / S3 / GCS stores via the kernel chunk bridge (any size, zarr v2 + v3)`. Extend the code sample:

```python
viewer.set_image("/data/big.ome.zarr")                       # local, any size
viewer.set_image("s3://bucket/x.ome.zarr", storage_options={"anon": True})  # needs anybioimage[remote]
```

- [ ] **Step 3: CHANGELOG.md** — under the unreleased viv entry add:

```markdown
- Viv backend: kernel chunk bridge renders local / `s3://` / `gs://` OME-Zarr stores and `zarr.Group` inputs of any size (zarr v2 + v3); chunk-aware tile cache (`bridge_cache_bytes`).
- New `anybioimage.ngff` module: lenient OME-NGFF v0.4 / v0.5 metadata reader used by all zarr paths.
- `set_image(..., storage_options=)` / `set_plate(..., storage_options=)` for fsspec credentials; new `remote` extra (s3fs, gcsfs).
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md README.md CHANGELOG.md
git commit -m "docs: chunk bridge, ngff module, remote extra"
```

---

### Task 13: Demo notebook + browser validation

**Files:**
- Create: `examples/viv_local_zarr_demo.py`

- [ ] **Step 1: Write the marimo demo**

```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["marimo", "anybioimage", "zarr"]
# ///

import marimo

__generated_with = "0.23.8"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    from anybioimage import BioImageViewer

    return BioImageViewer, mo


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Viv backend — local OME-Zarr through the kernel chunk bridge

    The browser cannot fetch files from disk, so for local / S3 / GCS stores the
    kernel opens the zarr with zarr-python and streams per-level tiles to Viv.
    Only the tiles Viv asks for are read; whole chunk blocks are cached so
    scrubbing T/Z inside a chunk is free.
    """)
    return


@app.cell
def _(mo):
    path = mo.ui.text(value="examples/image.zarr", label="OME-Zarr path", full_width=True)
    path
    return (path,)


@app.cell
def _(BioImageViewer, mo, path):
    viewer = BioImageViewer(render_backend="viv")
    viewer.set_image(path.value)
    mo.ui.anywidget(viewer)
    return


if __name__ == "__main__":
    app.run()
```

Run: `uv run marimo check --fix examples/viv_local_zarr_demo.py`

- [ ] **Step 2: Browser validation (playwright-cli skill, per CLAUDE.md)**

1. `mkdir -p /tmp/anybioimage-screenshots`
2. Start: `cd /var/home/maartenpaul/Documents/GitHub/anyimage && uv run --project .worktrees/viv-reader marimo edit .worktrees/viv-reader/examples/viv_local_zarr_demo.py` (run from the main checkout so `examples/image.zarr` resolves; note the access token).
3. `playwright-cli open "http://localhost:2718?access_token=<token>" --browser=chromium`
4. Wait for the widget; assert via `page.evaluate` that a `MARIMO-ANYWIDGET` shadow root contains a WebGL canvas (`canvas` inside the Viv mount `div`, `.viewer-canvas` hidden) and that `document.querySelector` finds no element with text "Could not".
5. Screenshot `/tmp/anybioimage-screenshots/bridge-first-frame.png`; visually confirm image content (not blank/black).
6. Set the Z slider (index 3) to `1`, then `2`; screenshot each; confirm pixel change and that the kernel log shows no `chunk request … failed`.
7. Zoom in (mouse wheel on canvas) and confirm level-0 tiles sharpen (screenshot).
8. Console must be clean: collect `page.on('console')` errors → expect none.
9. `rm -rf /tmp/anybioimage-screenshots`

- [ ] **Step 3: Record timings in the spec**

Append a "Measured" line to the spec's chunk-aware cache section with the observed first-tile and sibling-tile latencies from the kernel log (`logger.info` timestamps) — e.g. "first 512² tile ≈ 450 ms (chunk decode), sibling T/Z tiles < 5 ms".

- [ ] **Step 4: Commit**

```bash
git add examples/viv_local_zarr_demo.py docs/superpowers/specs/2026-09-02-zarr-chunk-bridge-design.md
git commit -m "feat(examples): local OME-Zarr viv demo; record bridge timings"
```

---

## Self-review

**Spec coverage:** ngff module (T1–T3) ✓; bridge cache + chunk-block read (T4) ✓; mixin, protocol, dtype cast, `bridge_cache_bytes`, detach on new image (T5) ✓; dispatch order + plate guard + fallbacks + `zarr.Group` (T6) ✓; plates (T7) ✓; deps/extra (T8) ✓; JS port with labels (T9), bridge sources + tileSize rule (T10), mode switch incl. chrome guards + rebuild + size gate (T11) ✓; docs (T12) ✓; demo + playwright + timings (T13) ✓. Error table: store open failure → fallback (T6/T7), plate → ValueError (T6), missing fsspec backend → ImportError hint (T1), chunk error reply (T5), destroy on unmount (T11).

**Type consistency:** `TileKey = (level, t, c, z, ty, tx)` everywhere (T4 tests, T5 `_serve_chunk`); `TileValue = (w, h, bytes)` (cache `len(val[2])`, `_bridge_tile` return); `_zarr_source["mode"]` in `"url"`/`"bridge"` used by T3/T5/T6/T11; `NgffImage.size/shape/axes/levels/dtype/omero_channels` used identically in T2/T4/T5/T7.
