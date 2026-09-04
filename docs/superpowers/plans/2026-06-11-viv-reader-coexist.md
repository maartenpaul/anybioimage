# Opt-in Viv Remote OME-Zarr Reader (coexistence) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Every task is self-contained** — it names its own files, port sources, full code, and test commands. Do not assume context from other tasks beyond the stated dependencies.

**Goal:** Add an efficient remote multidimensional (OME-Zarr) reader to `BioImageViewer` as an **opt-in** `render_backend="viv"` — browser-direct zarr chunk fetch + WebGL2 rendering — while keeping main's Canvas2D UI byte-for-byte as the default. Extend, not replace.

**Architecture:** Main's inline `_esm` (the "chrome": toolbar, channel panel, T/Z sliders, Canvas2D canvas) is extracted verbatim into a shared JS module used by both backends. The default backend serves it raw (no Node needed). The Viv backend is a small esbuild bundle whose entry imports the same chrome, hides the Canvas2D canvas when a zarr URL is active, and mounts a slim Viv/deck.gl canvas in the same wrapper — so main's existing DOM controls (`model.set('_channel_settings', …)`, `current_t`, …) drive Viv props with zero UI rewrite. Python adds a metadata-only zarr-URL load path (`_set_zarr_url`) as an early-dispatch branch in `set_image()`; everything non-zarr falls back silently to the unchanged Canvas2D pipeline. Finished pieces are ported from the `feature/viv-backend` worktree.

**Tech stack:** Python anywidget + traitlets; `@hms-dbmi/viv` 0.17.3 + deck.gl 9.0.38 + React 18 bundled via esbuild; hatch-jupyter-builder for wheel packaging.

---

## Context

The original approved design (`docs/superpowers/specs/2026-04-16-viv-backend-design.md` on `feature/viv-backend`) was "coexistence, not replacement": opt-in Viv backend, reuse main's UI. The project then pivoted on `feature/viv-backend` to a full React "unified viewer" that *replaced* main's UI (Phases 1–2.5, complete on that branch). The user has decided to course-correct back to the original coexistence design, on a **new branch off `main`**, porting the finished reader pieces from the branch. Remote OME-Zarr on main today goes through Python (bioio chunk fetch → CPU composite → PNG → websocket), which is slow; the Viv path makes the browser fetch chunks directly and composite on the GPU.

**Scope decisions (locked by user):**
- Opt-in `render_backend="viv"`; default `"canvas2d"` is behaviorally identical to main. **Zero Canvas2D regression is a hard gate** (full existing test suite must pass unchanged).
- Viv handles **URL-schemed OME-Zarr only** (`http(s)://`, `s3://`, `gs://`, `file://` + `.zarr` suffix). numpy / BioImage / bare-path `.zarr` / TIFF / CZI stay on Canvas2D with a one-line info log — silent fallback, no errors.
- The numpy→JS chunk bridge (`PixelSourceMixin` / `anywidget-source.js` from the branch) is **out of scope**.
- HCS plates: in scope — FOV switch on a remote plate updates `_zarr_source` instead of reloading through Python.
- No `_viv_mode` traitlet (derivable from `_render_backend` + `_zarr_source.url`). No subprocess-from-widget verification gates.
- Known alpha limitations (document, don't fix): annotation/SAM tools, brightness/contrast sliders, and histogram are inert on Viv-rendered images (they keep working on Canvas2D); deferred per original spec §4 to v0.7.1+.

## Shared constants (read by every subagent)

- **Repo root:** `/var/home/maartenpaul/Documents/GitHub/anyimage`
- **New branch / worktree:** branch `feature/viv-reader` off `main`, worktree at `/var/home/maartenpaul/Documents/GitHub/anyimage/.worktrees/viv-reader` (created in Task 0). **All file paths in tasks are relative to this worktree** unless absolute.
- **PORT_SRC** (read-only port source — the old branch's worktree):
  `/var/home/maartenpaul/Documents/GitHub/anyimage/.worktrees/viv-backend`
  Never modify anything under PORT_SRC.
- **Python env:** the project uses `uv`. Run tests as `uv run pytest …` from the worktree root. If the new worktree has no `.venv`, run `uv sync --extra all` once (or `uv pip install -e ".[all]"`).
- **Verified facts about `main`** (don't re-derive):
  - `anybioimage/viewer.py` is 2432 lines. `_esm = """` opens at **line 217**; the JS content is **lines 218–1896** (last content line is `    export default { render };`); the closing `"""` is **line 1897**. `_css = """` starts at line 1899. Inside the JS: `async function render({ model, el })` (line 242), `function requestTiles(tiles, t, z) {` (line 313), `function renderCanvas() {` (line 1258), `canvasWrapper.className = 'canvas-wrapper'` (line 870), `canvas.className = 'viewer-canvas'` (line 874).
  - Channel dicts on main: `{name, color, visible, min (0–1), max (0–1), data_min, data_max}`. The chrome's panel writes back via shallow copies, so extra keys (`index`, `color_kind`, `lut`, `gamma`) survive round-trips.
  - `mixins/image_loading.py`: `set_image(self, data)` at line 68 (BioImage duck-type → `_set_bioimage`, else `_set_numpy_image`); `_set_numpy_image` line 81; `_set_bioimage` line 154; `_start_precompute` line 728 (cancels via `self._precompute_event.set()`, then submits only when `_full_array` or `_bioimage` is set); `_prefetch_adjacent_slices` line 748; `_update_slice` line 798; module has `logger = logging.getLogger(__name__)`.
  - `mixins/plate_loading.py` (163 lines): `_load_plate_image(self, fov)` builds `image_path = f"{self._plate_path}/{self._current_well_path}/{fov}"` and calls `_set_bioimage(BioImage(image_path, reader=bioio_ome_zarr.Reader))`. No logger import yet.

## Dependency graph / parallel lanes

```
Task 0 (setup)
 ├─ Lane A (Python):   Task 1 → Task 2 → Task 4 → Task 5
 │                     Task 3 ──────────↗ (parallel with 1–2)
 ├─ Lane B (Frontend): Task 6 → Task 7 → Task 8
 └─ Join:              Task 9 (needs 1 + 8) → Task 10 ∥ Task 11 ∥ Task 13
Final gate:            Task 12 (needs 4, 5, 9)
```

Dispatchable in parallel: {Task 1, Task 3, Task 6}; later {Task 10, Task 11, Task 13}.

---

### Task 0: Branch + worktree setup

**Files:** none in repo (git operations); copy this plan into the repo.

- [ ] **Step 1: Create the worktree**

```bash
cd /var/home/maartenpaul/Documents/GitHub/anyimage
git worktree add .worktrees/viv-reader -b feature/viv-reader main
cd .worktrees/viv-reader
uv sync --extra all 2>/dev/null || uv pip install -e ".[all]"
```

- [ ] **Step 2: Baseline — full suite green on untouched main**

Run: `uv run pytest tests/ -x -q`
Expected: PASS (this is the regression baseline; record the test count).

- [ ] **Step 3: Copy this plan into the repo and commit**

```bash
mkdir -p docs/superpowers/plans
cp /var/home/maartenpaul/.claude/plans/could-you-write-a-glittery-cloud.md \
   docs/superpowers/plans/2026-06-11-viv-reader-coexist.md
git add docs/superpowers/plans/2026-06-11-viv-reader-coexist.md
git commit -m "docs(superpowers): opt-in Viv remote zarr reader plan (coexistence)"
```

---

### Task 1: Extract main's Canvas2D ESM into a shared chrome module + backend loaders

**Depends on:** Task 0.
**Files:**
- Create: `anybioimage/backends/__init__.py`, `anybioimage/backends/canvas2d.py`, `anybioimage/backends/viv.py`
- Create: `anybioimage/frontend/__init__.py` (empty), `anybioimage/frontend/viewer/__init__.py` (empty), `anybioimage/frontend/viewer/src/canvas2d-chrome.js`
- Modify: `anybioimage/viewer.py` (replace the inline `_esm` block, lines 217–1897)
- Test: `tests/test_backends.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_backends.py
import pytest

from anybioimage.backends import KNOWN_BACKENDS, get_backend_esm


def test_known_backends():
    assert KNOWN_BACKENDS == ("canvas2d", "viv")


def test_canvas2d_esm_is_mains_chrome():
    esm = get_backend_esm("canvas2d")
    assert "export default { render }" in esm
    assert "function renderCanvas()" in esm
    assert "canvas-wrapper" in esm


def test_unknown_backend_raises():
    with pytest.raises(ValueError, match="vulkan"):
        get_backend_esm("vulkan")


def test_viv_loader_missing_bundle_or_bundle():
    # Bundle is built in a later task. Before that, the loader must raise a
    # helpful RuntimeError; after, it returns the bundle. Accept either.
    try:
        esm = get_backend_esm("viv")
    except RuntimeError as e:
        assert "npm" in str(e)
    else:
        assert "render" in esm
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_backends.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'anybioimage.backends'`

- [ ] **Step 3: Extract the chrome verbatim**

First verify the markers (line numbers can shift only if main moved — they should not have):

```bash
sed -n '217p;1896p;1897p' anybioimage/viewer.py
```

Expected output exactly:

```
    _esm = """
    export default { render };
    """
```

Then extract:

```bash
mkdir -p anybioimage/frontend/viewer/src
sed -n '218,1896p' anybioimage/viewer.py > anybioimage/frontend/viewer/src/canvas2d-chrome.js
touch anybioimage/frontend/__init__.py anybioimage/frontend/viewer/__init__.py
```

- [ ] **Step 4: Add the (inert-by-default) Viv render guard to the chrome**

In `anybioimage/frontend/viewer/src/canvas2d-chrome.js`, find the line `        function renderCanvas() {` and insert directly below it:

```js
            // Viv backend owns the canvas when a zarr URL is active; the
            // Canvas2D draw path stands down. Inert on the default backend
            // (these traits are undefined / empty there).
            if (model.get('_render_backend') === 'viv' && (model.get('_zarr_source') || {}).url) return;
```

Find `        function requestTiles(tiles, t, z) {` and insert the same two-line guard (comment may be shortened to `// see renderCanvas guard`) directly below it.

- [ ] **Step 5: Write the backend loaders**

```python
# anybioimage/backends/__init__.py
"""Rendering-backend registry: maps a backend name to its anywidget ESM source."""
KNOWN_BACKENDS = ("canvas2d", "viv")


def get_backend_esm(name: str) -> str:
    """Return the anywidget ESM source string for the given backend."""
    if name == "canvas2d":
        from . import canvas2d
        return canvas2d.get_esm()
    if name == "viv":
        from . import viv
        return viv.get_esm()
    raise ValueError(f"Unknown render_backend {name!r}; expected one of {KNOWN_BACKENDS}")
```

```python
# anybioimage/backends/canvas2d.py
"""Default backend: main's original inline Canvas2D viewer, served as a raw
ESM string. Self-contained vanilla JS — no Node toolchain involved."""
from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=1)
def get_esm() -> str:
    return (
        files("anybioimage") / "frontend" / "viewer" / "src" / "canvas2d-chrome.js"
    ).read_text(encoding="utf-8")
```

```python
# anybioimage/backends/viv.py
"""Viv backend: pre-built esbuild bundle (browser-direct zarr fetch + WebGL2)."""
from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=1)
def get_esm() -> str:
    bundle = files("anybioimage") / "frontend" / "viewer" / "dist" / "viewer-bundle.js"
    try:
        return bundle.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise RuntimeError(
            "Viv bundle not found. Build it with: "
            "cd anybioimage/frontend/viewer && npm install && npm run build"
        ) from e
```

- [ ] **Step 6: Replace the inline `_esm` in `viewer.py`**

Near the top of `anybioimage/viewer.py`, with the other relative imports, add:

```python
from .backends import KNOWN_BACKENDS, get_backend_esm
```

Delete lines 217–1897 (the whole `_esm = """…"""` block) and put in their place:

```python
    _esm = get_backend_esm("canvas2d")
```

(`_css` stays in `viewer.py`, shared by both backends.)

- [ ] **Step 7: Run new tests + the full regression suite**

Run: `uv run pytest tests/test_backends.py -q && uv run pytest tests/ -q`
Expected: all PASS, same count as the Task 0 baseline plus the 4 new tests. Also verify byte-parity of the extraction (only the two guards differ):

```bash
diff <(sed -n '218,1896p' <(git show main:anybioimage/viewer.py)) anybioimage/frontend/viewer/src/canvas2d-chrome.js
```

Expected: exactly two hunks, each adding the guard lines — nothing else.

- [ ] **Step 8: Commit**

```bash
git add anybioimage/backends anybioimage/frontend anybioimage/viewer.py tests/test_backends.py
git commit -m "refactor(backends): extract Canvas2D ESM into shared chrome module + backend registry"
```

---

### Task 2: `render_backend` kwarg + new traitlets

**Depends on:** Task 1.
**Files:**
- Modify: `anybioimage/viewer.py` (traitlet block ~line 115 area; `__init__` at ~line 165)
- Test: `tests/test_render_backend.py` (new)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_render_backend.py
import pytest

from anybioimage import BioImageViewer


def test_default_backend_is_canvas2d():
    v = BioImageViewer()
    assert v._render_backend == "canvas2d"
    assert v._zarr_source == {}
    assert v._render_ready is False


def test_explicit_canvas2d():
    v = BioImageViewer(render_backend="canvas2d")
    assert v._render_backend == "canvas2d"


def test_viv_backend_selects_viv_esm():
    from anybioimage.backends import get_backend_esm
    try:
        viv_esm = get_backend_esm("viv")
    except RuntimeError:
        pytest.skip("viv bundle not built yet")
    v = BioImageViewer(render_backend="viv")
    assert v._render_backend == "viv"
    assert v._esm == viv_esm
    assert v._esm != get_backend_esm("canvas2d")


def test_unknown_backend_raises():
    with pytest.raises(ValueError, match="vulkan"):
        BioImageViewer(render_backend="vulkan")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_render_backend.py -q`
Expected: FAIL — `AttributeError: ... '_render_backend'` / `TypeError: unexpected keyword`.

- [ ] **Step 3: Implement**

In `anybioimage/viewer.py`, add to the traitlet declarations (next to the existing `_channel_settings` etc.):

```python
    # --- Viv backend (opt-in) ---
    _render_backend = traitlets.Unicode("canvas2d").tag(sync=True)
    # {url, headers} for browser-direct OME-Zarr fetch; {} = no zarr image
    _zarr_source = traitlets.Dict({}).tag(sync=True)
    # Flipped True by the Viv frontend once the first frame has props+viewState
    _render_ready = traitlets.Bool(False).tag(sync=True)
```

Change `__init__` (currently `def __init__(self, **kwargs):`):

```python
    def __init__(self, *, render_backend: str = "canvas2d", **kwargs):
        if render_backend not in KNOWN_BACKENDS:
            raise ValueError(
                f"Unknown render_backend {render_backend!r}; expected one of {KNOWN_BACKENDS}"
            )
        if render_backend != "canvas2d":
            # Must be set BEFORE super().__init__ — anywidget snapshots _esm
            # from the instance during widget construction.
            self._esm = get_backend_esm(render_backend)
        super().__init__(**kwargs)
        # ... existing body unchanged ...
        self._render_backend = render_backend
```

(Keep every existing line of the old body; only the signature, the pre-super `_esm` override, and the trailing `self._render_backend = render_backend` are new.)

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_render_backend.py tests/ -q`
Expected: PASS (viv-esm test skips until the bundle exists).

- [ ] **Step 5: Commit**

```bash
git add anybioimage/viewer.py tests/test_render_backend.py
git commit -m "feat(backends): render_backend kwarg + _zarr_source/_render_ready traitlets"
```

---

### Task 3: Tolerant zarr-URL detection (port)

**Depends on:** Task 0. Parallel with Tasks 1–2 (touches only `image_loading.py` module top + its own test file).
**Files:**
- Modify: `anybioimage/mixins/image_loading.py` (module level, below the existing constants)
- Test: `tests/test_zarr_detection.py` (port)

- [ ] **Step 1: Port the test verbatim**

```bash
cp /var/home/maartenpaul/Documents/GitHub/anyimage/.worktrees/viv-backend/tests/test_zarr_detection.py tests/test_zarr_detection.py
```

Run: `uv run pytest tests/test_zarr_detection.py -q`
Expected: FAIL — `ImportError: cannot import name '_looks_like_zarr_url'`

- [ ] **Step 2: Add the detection helpers**

In `anybioimage/mixins/image_loading.py`, after the existing module constants (`_THUMBNAIL_MAX` etc.), add — this is a verbatim port from `PORT_SRC/anybioimage/mixins/image_loading.py` lines 13–36:

```python
_ZARR_SUFFIXES = (".zarr", ".ome.zarr", ".zarr/")

_URL_SCHEMES = ("http://", "https://", "s3://", "gs://", "file://")


def _looks_like_zarr_url(s) -> bool:
    """Return True only for strings that are BOTH a URL (with an explicit
    scheme the browser can fetch from) AND point at a .zarr path.

    Filesystem paths ending in `.zarr` are NOT URLs — the browser cannot
    fetch them. Those go through the bioio path instead.
    """
    if not isinstance(s, str):
        return False
    lower = s.lower()
    if not lower.startswith(_URL_SCHEMES):
        return False
    stripped = s.split("?", 1)[0].split("#", 1)[0].rstrip("/").lower()
    return stripped.endswith(_ZARR_SUFFIXES)
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_zarr_detection.py -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add anybioimage/mixins/image_loading.py tests/test_zarr_detection.py
git commit -m "feat(zarr): tolerant URL-schemed zarr detection (port from viv-backend)"
```

---

### Task 4: Metadata-only zarr load path + `set_image` dispatch

**Depends on:** Tasks 2 and 3.
**Files:**
- Modify: `anybioimage/mixins/image_loading.py` (new module funcs + 4 method edits)
- Test: `tests/test_zarr_metadata.py` (new — do **not** port the branch's file; it is mostly xfailed legacy)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_zarr_metadata.py
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
def viv_viewer(monkeypatch):
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


def test_metadata_failure_falls_back_to_bioio(monkeypatch, caplog):
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


def test_numpy_on_viv_falls_back_to_canvas2d(caplog):
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
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_zarr_metadata.py -q`
Expected: FAIL — `AttributeError: ... '_fetch_zarr_ome_metadata'`.

- [ ] **Step 3: Add the metadata fetcher (port + extend)**

In `anybioimage/mixins/image_loading.py`, below `_looks_like_zarr_url` (from Task 3), add. This is the branch's `_fetch_zarr_ome_metadata` (PORT_SRC `anybioimage/mixins/image_loading.py` lines 86–157) **extended to also return axes + shape** so all dims can populate main's sliders:

```python
def _channel_settings_from_omero(ome: dict, dim_c: int, dtype=None) -> list[dict]:
    """Build channel_settings dicts from an OME-Zarr omero block (or defaults).

    Produces a superset of the Canvas2D schema: the chrome reads
    {name,color,visible,min,max,data_min,data_max}; the Viv layer additionally
    reads {index,color_kind,lut,gamma}. min/max are normalized to [0,1] of the
    data range, matching the Canvas2D convention.
    """
    dtype_min = dtype_max = None
    if dtype is not None and np.issubdtype(np.dtype(dtype), np.integer):
        info = np.iinfo(np.dtype(dtype))
        dtype_min, dtype_max = float(info.min), float(info.max)
    omero = ome.get("omero") or {}
    omero_channels = omero.get("channels") or []
    default_palette = ["#ff0000", "#00ff00", "#0000ff", "#ff00ff", "#00ffff", "#ffff00"]
    out = []
    for i in range(dim_c):
        src = omero_channels[i] if i < len(omero_channels) else {}
        window = src.get("window") or {}
        omero_min = float(window.get("min", 0.0))
        omero_max = float(window.get("max", 65535.0))
        if dtype_min is not None:
            data_min, data_max = dtype_min, dtype_max
        else:
            data_min, data_max = omero_min, omero_max
        start = float(window.get("start", omero_min))
        end = float(window.get("end", omero_max))
        omero_span = max(omero_max - omero_min, 1.0)
        vmin = max(0.0, (start - omero_min) / omero_span)
        vmax = min(1.0, (end - omero_min) / omero_span)
        color_hex = src.get("color")
        if color_hex:
            color = color_hex if color_hex.startswith("#") else f"#{color_hex}"
        else:
            color = default_palette[i % len(default_palette)]
        out.append({
            "index": i,
            "name": src.get("label", f"Ch {i}"),
            "visible": True,
            "color_kind": "solid",
            "color": color,
            "lut": "viridis",
            "data_min": data_min,
            "data_max": data_max,
            "min": vmin,
            "max": vmax,
            "gamma": 1.0,
        })
    return out


def _fetch_zarr_ome_metadata(url: str, headers: dict):
    """Fetch `.zattrs` + level-0 `.zarray` from a zarr root URL.

    Returns ``(zattrs, axes, shape, dtype_str)`` where ``axes`` is the
    multiscales axis-name list (e.g. ``["t","c","z","y","x"]``), ``shape`` is
    the level-0 array shape in the same order, and ``dtype_str`` a numpy dtype
    name (e.g. ``"uint16"``). Raises on network error / unparseable JSON.
    """
    import json
    import urllib.request

    base = url.rstrip("/")

    def _get_json(rel: str):
        req = urllib.request.Request(f"{base}/{rel}", headers=headers or {})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    zattrs = _get_json(".zattrs")
    multiscales = zattrs.get("multiscales") or []
    axes, shape, dtype_raw = [], [], "<u2"
    if multiscales:
        axes = [a.get("name", "") for a in (multiscales[0].get("axes") or [])]
        datasets = multiscales[0].get("datasets") or []
        if datasets and datasets[0].get("path") is not None:
            try:
                zarray = _get_json(f"{datasets[0]['path']}/.zarray")
                shape = list(zarray.get("shape", []))
                dtype_raw = zarray.get("dtype", "<u2")
            except Exception:
                pass
    if not axes and shape:
        # Pre-0.4 stores without an axes block: assume trailing-YX TCZYX order.
        axes = ["t", "c", "z", "y", "x"][-len(shape):]
    try:
        dtype_str = str(np.dtype(dtype_raw))
    except Exception:
        dtype_str = "uint16"
    return zattrs, axes, shape, dtype_str
```

- [ ] **Step 4: Add `_set_zarr_url` + the bioio fallback helper to `ImageLoadingMixin`**

Add these methods to `ImageLoadingMixin` (place after `set_image`):

```python
    def _set_zarr_url(self, url: str, headers: dict) -> None:
        """Viv path: fetch OME metadata once, populate dim/channel traitlets,
        and hand chunk fetching + rendering to the browser via _zarr_source.
        No precompute, no composites, no PNG encoding."""
        url = url.rstrip("/")
        zattrs, axes, shape, dtype_str = _fetch_zarr_ome_metadata(url, headers or {})

        def _dim(name: str) -> int:
            if name in axes:
                i = axes.index(name)
                if i < len(shape):
                    return int(shape[i])
            return 1

        dim_c = _dim("c")
        channels = _channel_settings_from_omero(zattrs, dim_c, dtype_str)

        # Cancel any running Canvas2D precompute (same idiom as _start_precompute).
        if getattr(self, "_precompute_event", None) is not None:
            self._precompute_event.set()
        self._precompute_future = None
        self._full_array = None
        self._bioimage = None

        with self.hold_trait_notifications():
            self.dim_t = _dim("t")
            self.dim_c = dim_c
            self.dim_z = _dim("z")
            self.height = _dim("y")
            self.width = _dim("x")
            self.current_t = 0
            self.current_z = 0
            self._channel_settings = channels
            self.image_data = ""
        self._zarr_source = {"url": url, "headers": headers or {}}
        logger.info("Viv backend: browser-direct zarr source set to %s", url)

    def _set_zarr_url_canvas2d(self, url: str) -> None:
        """Canvas2D path for zarr URLs: load through bioio as before."""
        import bioio_ome_zarr
        from bioio import BioImage

        self._set_bioimage(BioImage(url, reader=bioio_ome_zarr.Reader))
```

- [ ] **Step 5: Rewrite `set_image` dispatch (keep the existing tail verbatim)**

Replace the body of `set_image` (line 68) with:

```python
    def set_image(self, data, headers: dict | None = None):
        """Set the base image from a numpy array, BioImage object, or
        (URL-schemed) OME-Zarr URL string.

        Args:
            data: numpy array, BioImage, or ``http(s)/s3/gs/file`` URL ending
                  in ``.zarr`` / ``.ome.zarr``.
            headers: optional HTTP headers for zarr URLs (auth etc.).
        """
        if _looks_like_zarr_url(data):
            if getattr(self, "_render_backend", "canvas2d") == "viv":
                try:
                    self._set_zarr_url(data, headers or {})
                    return
                except Exception as e:
                    logger.info(
                        "Viv zarr metadata load failed (%s); falling back to Canvas2D", e
                    )
            self._set_zarr_url_canvas2d(data)
            return
        if getattr(self, "_render_backend", "canvas2d") == "viv":
            logger.info("Non-zarr input on viv backend; rendering via Canvas2D pipeline.")
        # --- existing main dispatch, unchanged ---
        if hasattr(data, "dims") and hasattr(data, "dask_data"):
            self._set_bioimage(data)
        else:
            self._set_numpy_image(data)
```

- [ ] **Step 6: Guard the Canvas2D hot paths + clear `_zarr_source` on non-zarr loads**

Four small edits in `anybioimage/mixins/image_loading.py`:

1. At the very top of `_update_slice` (line ~798) insert:

```python
        if getattr(self, "_zarr_source", {}).get("url"):
            return  # Viv owns rendering for zarr-URL images
```

2. Same two lines at the very top of `_prefetch_adjacent_slices` (line ~748).
3. At the very top of `_set_numpy_image` (line ~81) insert:

```python
        if getattr(self, "_zarr_source", None):
            self._zarr_source = {}
```

4. Same two lines at the very top of `_set_bioimage` (line ~154).

(`_start_precompute` needs no guard: with `_full_array is None and _bioimage is None` it already submits nothing.)

- [ ] **Step 7: Run tests + full regression suite**

Run: `uv run pytest tests/test_zarr_metadata.py -q && uv run pytest tests/ -q`
Expected: PASS, no regressions.

- [ ] **Step 8: Commit**

```bash
git add anybioimage/mixins/image_loading.py tests/test_zarr_metadata.py
git commit -m "feat(zarr): metadata-only _set_zarr_url path + set_image dispatch with silent Canvas2D fallback"
```

---

### Task 5: HCS plate FOV switch drives `_zarr_source`

**Depends on:** Task 4.
**Files:**
- Modify: `anybioimage/mixins/plate_loading.py`
- Test: `tests/test_plate_viv.py` (new — write fresh; the branch's version targets the replaced architecture)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_plate_viv.py
"""Viv backend: remote-plate FOV switches update _zarr_source (no Python reload)."""
from anybioimage import BioImageViewer


def _prime_plate(v, plate_path):
    # Simulate state normally established by set_plate()/_load_well_fovs()
    v._plate_path = plate_path
    v._current_well_path = "A/1"


def test_remote_plate_fov_sets_zarr_source(monkeypatch):
    v = BioImageViewer(render_backend="viv")
    _prime_plate(v, "https://example.org/plate.zarr")
    seen = {}
    monkeypatch.setattr(v, "_set_zarr_url", lambda url, headers: seen.setdefault("url", url))
    v._load_plate_image("0")
    assert seen["url"] == "https://example.org/plate.zarr/A/1/0"


def test_local_plate_on_viv_uses_bioio(monkeypatch):
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


def test_viv_plate_metadata_failure_falls_back(monkeypatch):
    v = BioImageViewer(render_backend="viv")
    _prime_plate(v, "https://example.org/plate.zarr")

    def boom(url, headers):
        raise OSError("403")
    monkeypatch.setattr(v, "_set_zarr_url", boom)
    called = {}
    monkeypatch.setattr(v, "_load_plate_image_bioio", lambda p: called.setdefault("path", p))
    v._load_plate_image("0")
    assert called["path"] == "https://example.org/plate.zarr/A/1/0"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_plate_viv.py -q`
Expected: FAIL — `AttributeError: ... '_load_plate_image_bioio'`.

- [ ] **Step 3: Implement**

In `anybioimage/mixins/plate_loading.py`: add to the imports at the top:

```python
import logging

logger = logging.getLogger(__name__)
```

Replace `_load_plate_image` (currently builds `image_path` then BioImage/`_set_bioimage`) with:

```python
    def _load_plate_image(self, fov):
        """Load the image for the current well and given FOV.

        On the viv backend with a remote (http/https) plate, hand the FOV's
        zarr subpath straight to the browser via _zarr_source — no Python
        chunk reload. Everything else uses the bioio path, unchanged.
        """
        if not hasattr(self, "_current_well_path"):
            return

        image_path = f"{self._plate_path}/{self._current_well_path}/{fov}"

        if (
            getattr(self, "_render_backend", "canvas2d") == "viv"
            and str(self._plate_path).lower().startswith(("http://", "https://"))
        ):
            try:
                self._set_zarr_url(image_path, {})
                return
            except Exception as e:
                logger.info("Viv plate FOV load failed (%s); falling back to bioio", e)

        self._load_plate_image_bioio(image_path)

    def _load_plate_image_bioio(self, image_path):
        """Original bioio plate-image load (Canvas2D path)."""
        try:
            import bioio_ome_zarr
            from bioio import BioImage

            img = BioImage(image_path, reader=bioio_ome_zarr.Reader)
            self._set_bioimage(img)
        except ImportError:
            raise ImportError(
                "bioio and bioio-ome-zarr are required for plate loading. "
                "Install with: pip install bioio bioio-ome-zarr"
            )
```

(The `except ImportError` block is main's existing text — keep it verbatim.)

- [ ] **Step 4: Run tests + regression suite**

Run: `uv run pytest tests/test_plate_viv.py tests/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add anybioimage/mixins/plate_loading.py tests/test_plate_viv.py
git commit -m "feat(plates): viv FOV switch updates _zarr_source; bioio path untouched"
```

---

### Task 6: Frontend scaffold (port)

**Depends on:** Task 0. Parallel with Lane A.
**Files:**
- Create: `anybioimage/frontend/viewer/package.json`, `anybioimage/frontend/viewer/build.config.mjs`, `anybioimage/frontend/viewer/.gitignore`

- [ ] **Step 1: Port build config and package manifest**

```bash
SRC=/var/home/maartenpaul/Documents/GitHub/anyimage/.worktrees/viv-backend/anybioimage/frontend/viewer
mkdir -p anybioimage/frontend/viewer
cp "$SRC/package.json" "$SRC/build.config.mjs" anybioimage/frontend/viewer/
cp "$SRC/.gitignore" anybioimage/frontend/viewer/ 2>/dev/null || printf 'node_modules/\n' > anybioimage/frontend/viewer/.gitignore
```

Then edit `anybioimage/frontend/viewer/package.json`: remove the devDependencies `"@testing-library/react"` and `"jsdom"` (the React-component tests that needed them are not ported). Keep everything else exactly as-is — especially the `overrides` block pinning `@luma.gl/*` 9.0.28 / `@deck.gl/*` 9.0.38 (required for Viv 0.17 compatibility; do not bump) and the `size-limit` config (4 MB on `dist/viewer-bundle.js`).

- [ ] **Step 2: Install and sanity-check**

```bash
cd anybioimage/frontend/viewer && npm install && npx esbuild --version && cd -
```

Expected: install succeeds; esbuild prints a version.

- [ ] **Step 3: Commit (lockfile included; node_modules ignored)**

```bash
git add anybioimage/frontend/viewer/package.json anybioimage/frontend/viewer/package-lock.json \
        anybioimage/frontend/viewer/build.config.mjs anybioimage/frontend/viewer/.gitignore
git commit -m "build(frontend): esbuild scaffold for viv bundle (port from viv-backend)"
```

---

### Task 7: Port the render kernel verbatim

**Depends on:** Task 6.
**Files (create, all under `anybioimage/frontend/viewer/`):**
- `src/render/pixel-sources/zarr-source.js` (+ none — no test on branch)
- `src/render/layers/buildImageLayer.js` + `src/render/layers/buildImageLayer.test.js`
- `src/util/perf.js` + `src/util/perf.test.js`
- `src/model/useModelTrait.js`

- [ ] **Step 1: Copy verbatim from PORT_SRC**

```bash
SRC=/var/home/maartenpaul/Documents/GitHub/anyimage/.worktrees/viv-backend/anybioimage/frontend/viewer/src
DST=anybioimage/frontend/viewer/src
mkdir -p "$DST/render/pixel-sources" "$DST/render/layers" "$DST/util" "$DST/model"
cp "$SRC/render/pixel-sources/zarr-source.js"        "$DST/render/pixel-sources/"
cp "$SRC/render/layers/buildImageLayer.js"           "$DST/render/layers/"
cp "$SRC/render/layers/buildImageLayer.test.js"      "$DST/render/layers/"
cp "$SRC/util/perf.js" "$SRC/util/perf.test.js"      "$DST/util/"
cp "$SRC/model/useModelTrait.js"                     "$DST/model/"
```

These are the proven pieces: `openOmeZarr()` (Viv's `loadOmeZarr`, browser-direct chunk fetch, multiscale-aware) and `buildImageLayerProps()` (axes-aware selections — handles stores without a `t`/`z` axis — OMERO colors, contrast from normalized min/max × data range).

- [ ] **Step 2: Run the ported unit tests**

Run: `cd anybioimage/frontend/viewer && npx vitest run && cd -`
Expected: PASS. If `buildImageLayer.test.js` fails on imports of out-of-scope modules (e.g. `anywidget-source.js`), delete only those specific test cases — the file's core cases test pure prop-building and must pass.

- [ ] **Step 3: Commit**

```bash
git add anybioimage/frontend/viewer/src
git commit -m "feat(frontend): port zarr-source + buildImageLayer render kernel from viv-backend"
```

---

### Task 8: Slim `VivCanvas.jsx`

**Depends on:** Task 7.
**Files:**
- Create: `anybioimage/frontend/viewer/src/render/VivCanvas.jsx`

This is the branch's `DeckCanvas.jsx` (`PORT_SRC/anybioimage/frontend/viewer/src/render/DeckCanvas.jsx`) stripped of masks, annotations, interaction controller, scale bar, preview layers, and the chunk-bridge — image rendering + pan/zoom only.

- [ ] **Step 1: Write the component**

```jsx
// anybioimage/frontend/viewer/src/render/VivCanvas.jsx
// Slim Viv canvas: remote OME-Zarr only. Derived from the unified viewer's
// DeckCanvas.jsx with masks/annotations/tools stripped (deferred per spec §4).
import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { OrthographicView } from '@deck.gl/core';
import { MultiscaleImageLayer, getDefaultInitialViewState } from '@hms-dbmi/viv';

import { openOmeZarr } from './pixel-sources/zarr-source.js';
import { buildImageLayerProps } from './layers/buildImageLayer.js';
import { useModelTrait } from '../model/useModelTrait.js';

function useContainerSize(ref, fallback = { width: 800, height: 600 }) {
  const [size, setSize] = useState(fallback);
  useLayoutEffect(() => {
    if (!ref.current) return;
    const el = ref.current;
    const measure = () => {
      const rect = el.getBoundingClientRect();
      setSize({
        width: Math.max(1, Math.floor(rect.width)) || fallback.width,
        height: Math.max(1, Math.floor(rect.height)) || fallback.height,
      });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref, fallback.width, fallback.height]);
  return size;
}

export function VivCanvas({ model }) {
  const zarrSource = useModelTrait(model, '_zarr_source');
  const channelSettings = useModelTrait(model, '_channel_settings');
  const currentT = useModelTrait(model, 'current_t');
  const currentZ = useModelTrait(model, 'current_z');
  const imageVisible = useModelTrait(model, 'image_visible') !== false;

  const containerRef = useRef(null);
  const { width, height } = useContainerSize(containerRef);
  const [sources, setSources] = useState(null);
  const [error, setError] = useState(null);
  const [viewState, setViewState] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function run() {
      setError(null);
      if (!zarrSource?.url) { setSources(null); return; }
      try {
        const { sources: srcs } = await openOmeZarr(zarrSource.url, zarrSource.headers || {});
        if (!cancelled) setSources(srcs);
      } catch (e) {
        if (!cancelled) { setError(String(e)); setSources(null); }
      }
    }
    run();
    return () => { cancelled = true; };
  }, [zarrSource?.url]);

  useEffect(() => {
    if (!sources || !sources.length) return;
    setViewState(getDefaultInitialViewState(sources, { width, height }, 0));
    // Intentionally not depending on width/height: don't reset the user's
    // pan/zoom on container resize.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sources]);

  const imageLayerProps = useMemo(() => {
    if (!sources || !sources.length) return null;
    return buildImageLayerProps({
      sources,
      channels: channelSettings || [],
      currentT: currentT || 0,
      currentZ: currentZ || 0,
    });
  }, [sources, channelSettings, currentT, currentZ]);

  // Flip-once readiness flag for tests/fixtures.
  useEffect(() => {
    if (imageLayerProps && viewState && !model.get('_render_ready')) {
      model.set('_render_ready', true);
      model.save_changes();
    }
  }, [imageLayerProps, viewState, model]);

  const layers = useMemo(() => {
    if (!imageLayerProps || !imageVisible) return [];
    return [new MultiscaleImageLayer({ id: 'viv-image', viewportId: 'ortho', ...imageLayerProps })];
  }, [imageLayerProps, imageVisible]);

  if (!zarrSource?.url) return null;
  if (error) {
    return <div style={{ color: '#b00', padding: 12 }}>Failed to load image: {error}</div>;
  }

  return (
    <div ref={containerRef} style={{ position: 'absolute', inset: 0 }}>
      {!sources ? (
        <div style={{ padding: 12, color: '#666' }}>Loading…</div>
      ) : (
        <DeckGL
          width={width}
          height={height}
          layers={layers}
          views={[new OrthographicView({ id: 'ortho', controller: true })]}
          viewState={viewState ? { ortho: viewState } : undefined}
          onViewStateChange={({ viewState: v }) => setViewState(v)}
          useDevicePixels={true}
          getCursor={({ isDragging }) => (isDragging ? 'grabbing' : 'grab')}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Type-check by building (no entry yet — direct esbuild invocation)**

```bash
cd anybioimage/frontend/viewer && npx esbuild src/render/VivCanvas.jsx --bundle --format=esm \
  --jsx=automatic --loader:.js=jsx --outfile=/dev/null && cd -
```

Expected: builds with no errors.

- [ ] **Step 3: Commit**

```bash
git add anybioimage/frontend/viewer/src/render/VivCanvas.jsx
git commit -m "feat(frontend): slim VivCanvas (image + pan/zoom only)"
```

---

### Task 9: Viv entry (chrome-import seam), bundle build, Python loader test

**Depends on:** Tasks 1 and 8.
**Files:**
- Create: `anybioimage/frontend/viewer/src/entry.js`
- Create: `anybioimage/frontend/viewer/dist/viewer-bundle.js` (build artifact, committed)
- Test: extend `tests/test_backends.py`

- [ ] **Step 1: Write the entry**

```js
// anybioimage/frontend/viewer/src/entry.js
// Viv backend entry: build main's full Canvas2D chrome (toolbar, channel
// panel, sliders — its renderCanvas()/requestTiles() self-guard when a zarr
// URL is active), then mount the Viv WebGL canvas in the same wrapper.
// Exactly one canvas is visible at a time, switched on _zarr_source.
import chrome from './canvas2d-chrome.js'; // both files live in src/
import React from 'react';
import { createRoot } from 'react-dom/client';
import { VivCanvas } from './render/VivCanvas.jsx';

async function render({ model, el }) {
  const cleanupChrome = await chrome.render({ model, el });

  const wrapper = el.querySelector('.canvas-wrapper');
  const c2dCanvas = el.querySelector('canvas.viewer-canvas');
  if (!wrapper) {
    console.error('anybioimage viv entry: .canvas-wrapper not found; Canvas2D only');
    return cleanupChrome;
  }
  if (!wrapper.style.position) wrapper.style.position = 'relative';

  const mount = document.createElement('div');
  mount.style.cssText = 'position:absolute;inset:0;';
  wrapper.appendChild(mount);
  const root = createRoot(mount);
  root.render(React.createElement(VivCanvas, { model }));

  const syncMode = () => {
    const viv = Boolean((model.get('_zarr_source') || {}).url);
    if (c2dCanvas) c2dCanvas.style.display = viv ? 'none' : '';
    mount.style.display = viv ? '' : 'none';
  };
  model.on('change:_zarr_source', syncMode);
  syncMode();

  return () => {
    model.off('change:_zarr_source', syncMode);
    root.unmount();
    mount.remove();
    if (typeof cleanupChrome === 'function') cleanupChrome();
  };
}

export default { render };
```

- [ ] **Step 2: Build the bundle**

Run: `cd anybioimage/frontend/viewer && npm run build && cd -`
Expected: `dist/viewer-bundle.js` produced, esbuild reports size (expect ~1.5–2 MB minified).

- [ ] **Step 3: Smoke the bundle exports**

```bash
node -e "import('./anybioimage/frontend/viewer/dist/viewer-bundle.js').then(m => { if (typeof m.default.render !== 'function') { console.error('no render export'); process.exit(1);} console.log('bundle OK'); }).catch(e => { console.error(e); process.exit(1); })"
```

Expected: `bundle OK`. (If Node chokes on browser globals at import time, that's acceptable — fall back to `grep -c 'render' dist/viewer-bundle.js` returning ≥1 and let Playwright (Task 12) be the functional check. Note which check was used in the commit message.)

- [ ] **Step 4: Add the loader test**

Append to `tests/test_backends.py`:

```python
def test_viv_esm_is_committed_bundle():
    from pathlib import Path

    import anybioimage
    from anybioimage.backends import viv

    bundle = (
        Path(anybioimage.__file__).parent / "frontend" / "viewer" / "dist" / "viewer-bundle.js"
    )
    assert bundle.exists(), "bundle must be committed"
    assert viv.get_esm() == bundle.read_text(encoding="utf-8")
```

Run: `uv run pytest tests/test_backends.py tests/test_render_backend.py -q`
Expected: PASS — including the previously-skipped `test_viv_backend_selects_viv_esm`.

- [ ] **Step 5: Commit (bundle is checked in so pip/editable installs need no Node)**

```bash
git add -f anybioimage/frontend/viewer/dist/viewer-bundle.js
git add anybioimage/frontend/viewer/src/entry.js tests/test_backends.py
git commit -m "feat(frontend): viv entry imports canvas2d chrome + mounts VivCanvas; commit built bundle"
```

(Use `git add -f` only if `.gitignore` patterns would exclude `dist/`; check first with `git check-ignore`.)

---

### Task 10: Wheel packaging

**Depends on:** Task 9. Parallel with Tasks 11, 13.
**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add build config**

Reference: `PORT_SRC/pyproject.toml` lines 66–100 have a working version of this. Apply to this branch's `pyproject.toml`:

Change `[build-system]` to:

```toml
[build-system]
requires = ["hatchling", "hatch-jupyter-builder>=0.9"]
build-backend = "hatchling.build"
```

Add (adjusting any existing `[tool.hatch.build.targets.wheel]` section):

```toml
[tool.hatch.build.targets.wheel]
packages = ["anybioimage"]
exclude = [
    "anybioimage/frontend/viewer/node_modules/",
    "anybioimage/frontend/viewer/src/",
    "anybioimage/frontend/viewer/package.json",
    "anybioimage/frontend/viewer/package-lock.json",
    "anybioimage/frontend/viewer/build.config.mjs",
    "anybioimage/frontend/viewer/.gitignore",
]

[tool.hatch.build.targets.wheel.force-include]
"anybioimage/frontend/viewer/dist/viewer-bundle.js" = "anybioimage/frontend/viewer/dist/viewer-bundle.js"
# The default backend reads the chrome at runtime — it must ship even though src/ is excluded.
"anybioimage/frontend/viewer/src/canvas2d-chrome.js" = "anybioimage/frontend/viewer/src/canvas2d-chrome.js"

[tool.hatch.build.hooks.jupyter-builder]
build-function = "hatch_jupyter_builder.npm_builder"
ensured-targets = ["anybioimage/frontend/viewer/dist/viewer-bundle.js"]
skip-if-exists = ["anybioimage/frontend/viewer/dist/viewer-bundle.js"]

[tool.hatch.build.hooks.jupyter-builder.build-kwargs]
path = "anybioimage/frontend/viewer"
build_cmd = "build"
npm = ["npm"]

[tool.hatch.build.targets.sdist]
include = ["anybioimage/", "README.md", "LICENSE", "pyproject.toml"]
exclude = ["anybioimage/frontend/viewer/node_modules/"]
```

(`skip-if-exists` means source installs with the committed bundle never invoke npm — pip users and Python-only contributors need no Node.)

- [ ] **Step 2: Build and inspect the wheel**

```bash
uv build --wheel
unzip -l dist/anybioimage-*.whl | grep -E "viewer-bundle\.js|canvas2d-chrome\.js"
```

Expected: both files listed.

- [ ] **Step 3: Verify a clean install renders both backends' ESM**

```bash
uv venv /tmp/abi-wheel-test --python 3.12
uv pip install --python /tmp/abi-wheel-test/bin/python dist/anybioimage-*.whl
/tmp/abi-wheel-test/bin/python -c "
from anybioimage.backends import get_backend_esm
assert 'renderCanvas' in get_backend_esm('canvas2d')
assert len(get_backend_esm('viv')) > 100_000
print('wheel OK')"
rm -rf /tmp/abi-wheel-test
```

Expected: `wheel OK`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build(wheel): ship canvas2d chrome + viv bundle; jupyter-builder hook with skip-if-exists"
```

---

### Task 11: CI — bundle freshness + Node in publish

**Depends on:** Task 9. Parallel with Tasks 10, 13.
**Files:**
- Create: `.github/workflows/bundle.yml` (port)
- Modify: `.github/workflows/publish.yml`

- [ ] **Step 1: Port the bundle workflow**

```bash
cp /var/home/maartenpaul/Documents/GitHub/anyimage/.worktrees/viv-backend/.github/workflows/bundle.yml .github/workflows/bundle.yml
```

Read the copied file and verify/adjust: it must (a) trigger on changes under `anybioimage/frontend/viewer/**`, (b) `npm ci` + `npm run build` in `anybioimage/frontend/viewer`, (c) fail if `git diff --exit-code -- anybioimage/frontend/viewer/dist/viewer-bundle.js` shows drift, (d) run `npx size-limit`. If any of those four steps is missing, add it.

- [ ] **Step 2: Add Node to the publish workflow**

In `.github/workflows/publish.yml`, before the package build step, insert:

```yaml
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
```

(With Task 10's `skip-if-exists`, publish builds use the committed bundle; Node is belt-and-braces for `ensured-targets`.)

- [ ] **Step 3: Validate YAML + commit**

Run: `uv run python -c "import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob('.github/workflows/*.yml')]; print('yaml OK')"`
Expected: `yaml OK`.

```bash
git add .github/workflows/bundle.yml .github/workflows/publish.yml
git commit -m "ci: bundle freshness + size gate; node in publish workflow"
```

---

### Task 12: End-to-end Playwright verification (final gate)

**Depends on:** Tasks 4, 5, 9 (run after everything else is merged into the branch).
**Files:**
- Create: `examples/viv_remote_zarr_demo.py` (marimo notebook)

This task follows the project's documented browser-test workflow (CLAUDE.md): marimo server + `playwright-cli` skill, chromium, widget inside `MARIMO-ANYWIDGET` shadow DOM, screenshots under `/tmp/anybioimage-screenshots/` (create at start, delete when done). This is the project's standard harness — not a widget-spawned subprocess gate.

- [ ] **Step 1: Write the demo notebook**

```python
# examples/viv_remote_zarr_demo.py
import marimo

__generated_with = "0.19.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    from anybioimage import BioImageViewer

    # Public IDR OME-Zarr (same fixture URL the viv-backend branch validated against)
    URL = "https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0062A/6001240.zarr"
    viewer = BioImageViewer(render_backend="viv")
    viewer.set_image(URL)
    mo.ui.anywidget(viewer)
    return (viewer,)


@app.cell
def _(mo):
    import numpy as np

    from anybioimage import BioImageViewer as _BIV

    # Fallback check: numpy input on the viv backend renders via Canvas2D
    fallback_viewer = _BIV(render_backend="viv")
    fallback_viewer.set_image(
        (np.random.rand(2, 256, 256) * 65535).astype("uint16")
    )
    mo.ui.anywidget(fallback_viewer)
    return


if __name__ == "__main__":
    app.run()
```

Run: `uv run marimo check --fix examples/viv_remote_zarr_demo.py`
Expected: no errors.

- [ ] **Step 2: Run the browser checks**

```bash
mkdir -p /tmp/anybioimage-screenshots
uv run marimo edit examples/viv_remote_zarr_demo.py  # note the access token in the printed URL
# then: playwright-cli open "http://localhost:2718?access_token=<token>" --browser=chromium
```

Checks (each = screenshot + non-blank-pixel assertion via shadow-DOM canvas sampling, per the CLAUDE.md patterns; for the Viv viewer the canvas is deck.gl's WebGL canvas — sample with `gl.readPixels` fallback or screenshot-diff if `getContext('2d')` is unavailable):

1. **Remote zarr renders:** first widget shows a non-blank image (`viewer._render_ready` flips True — poll `model` via a cell printing `viewer._render_ready`).
2. **Channel toggle:** click a channel eye-toggle in the layers panel → sampled rendering changes.
3. **Min/max drag:** move a channel min slider → rendering changes.
4. **T slider:** set T-slider (slider index 2) to a different value → rendering changes without Python tile traffic (no `image_data` updates — assert `viewer.image_data == ""` after).
5. **Fallback:** second widget (numpy on viv) shows the Canvas2D viewer with a visible image.
6. **Plate FOV (if a public remote plate URL is available):** `set_plate` + FOV dropdown change → rendering changes. If no public HCS plate is reachable, mark this check as skipped in the report — the Python-side logic is covered by `tests/test_plate_viv.py`.

```bash
rm -rf /tmp/anybioimage-screenshots
```

- [ ] **Step 3: Full suite one last time + commit**

Run: `uv run pytest tests/ -q`
Expected: PASS.

```bash
git add examples/viv_remote_zarr_demo.py
git commit -m "test(e2e): viv remote-zarr demo notebook + browser validation"
```

---

### Task 13: Docs, attribution, CHANGELOG

**Depends on:** Task 9. Parallel with Tasks 10–11.
**Files:**
- Modify: `README.md`, `CHANGELOG.md`, `CLAUDE.md`

- [ ] **Step 1: README — backend section + attribution**

Add under the usage section:

```markdown
## Rendering backends

| Backend | Default | Best for |
|---|---|---|
| `canvas2d` | ✅ | Local arrays, BioImage/TIFF/CZI/ND2, full annotation & SAM toolset |
| `viv` | opt-in | Remote OME-Zarr URLs — browser-direct chunk fetch, GPU compositing |

```python
# Opt in to the Viv backend for remote OME-Zarr:
viewer = BioImageViewer(render_backend="viv")
viewer.set_image("https://example.com/data.ome.zarr")
viewer.set_plate("https://example.com/plate.zarr")  # well/FOV switching stays browser-side
```

Non-zarr inputs on the `viv` backend fall back to Canvas2D automatically (one info log).
Alpha limitations on Viv-rendered images: annotation/SAM tools, brightness/contrast
sliders, and histograms are inactive (use per-channel min/max); they remain fully
functional on the Canvas2D backend.

### Attribution

The Viv backend builds on [Viv](https://github.com/hms-dbmi/viv) (MIT),
[deck.gl](https://deck.gl) (MIT), and Viv's zarr loader (zarrita/zarr.js lineage, MIT).
```

- [ ] **Step 2: CHANGELOG**

Add at the top:

```markdown
## Unreleased — v0.7.0-alpha

### Added
- Opt-in `render_backend="viv"`: remote OME-Zarr rendered via WebGL2 with
  browser-direct chunk fetch (no Python tile round-trips). Main UI unchanged.
- `set_image(url, headers=...)` accepts URL-schemed `.zarr`/`.ome.zarr` strings
  on both backends (Canvas2D routes them through bioio).
- HCS plates on the viv backend: FOV switching swaps the zarr subpath browser-side.

### Changed
- Canvas2D ESM extracted verbatim to `anybioimage/frontend/viewer/src/canvas2d-chrome.js`
  (served raw — behavior identical; no Node needed for the default backend).

### Build
- `anybioimage/frontend/viewer/` esbuild bundle for the viv backend; pre-built
  bundle committed and shipped in the wheel (no Node at install time).
```

- [ ] **Step 3: CLAUDE.md — add a short "Rendering backends" subsection** under Key Classes describing: `render_backend="viv"` opt-in, `_zarr_source`/`_render_backend`/`_render_ready` traitlets, chrome extraction location, bundle rebuild command (`cd anybioimage/frontend/viewer && npm run build`), and the rule that chrome edits require a bundle rebuild (CI `bundle.yml` enforces freshness).

- [ ] **Step 4: Commit**

```bash
git add README.md CHANGELOG.md CLAUDE.md
git commit -m "docs: viv backend usage, limitations, attribution + changelog"
```

---

## End-to-end verification (release gate for the branch)

1. `uv run pytest tests/ -q` — full suite green; every test that passed on `main` still passes (Canvas2D no-regression guarantee).
2. `cd anybioimage/frontend/viewer && npx vitest run && npm run build && git diff --exit-code dist/viewer-bundle.js` — kernel tests pass; committed bundle is fresh.
3. `uv build --wheel` → wheel contains `canvas2d-chrome.js` + `viewer-bundle.js`; installs and imports in a Node-free venv (Task 10 Step 3).
4. Browser (Task 12): remote IDR zarr renders on viv; channel toggle / min-max / T-slider change pixels with `image_data` staying empty; numpy-on-viv silently falls back to Canvas2D; default-backend notebook behaves exactly as on main.
5. Subjective (spec acceptance): T/Z scrubbing on remote zarr feels responsive; no blank frames; channel drags snappy.

## Known follow-ups (explicitly out of this plan)

- Masks / annotations / SAM on Viv-rendered images (original spec: v0.7.1–v0.7.2).
- Brightness/contrast as Viv shader uniforms; Python-side histograms for zarr URLs.
- numpy/BioImage chunk bridge (`PixelSourceMixin`) for GPU-rendering local data.
- `_pixel_info` hover readout (portable from `PORT_SRC/.../render/onHoverPixelInfo.js` when wanted).
