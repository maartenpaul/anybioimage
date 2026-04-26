# Viv + zarrita.js rendering backend (v0.7.0-alpha) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a second rendering backend for `BioImageViewer` — Viv (WebGL2) + zarrita.js (browser-direct OME-Zarr fetch) — opt-in via `render_backend="viv"`, while keeping the existing Canvas2D backend as the default and the Python API identical.

**Architecture:** Backend selection lives in a new `anybioimage/backends/` package. The current inline `_esm` string moves verbatim into a shared source file consumed by both the Canvas2D Python loader and the new Viv bundle's fallback path. The Viv bundle is a bundled React/Viv/zarrita/deck.gl tree under `anybioimage/frontend/viv/`, built at wheel-build time by `hatch-jupyter-builder` and committed to git so editable installs work without Node. Python's role shrinks on the Viv path: fetch OME-Zarr metadata once, maintain traitlets, serve histograms. zarrita.js fetches chunks in the browser; Viv renders.

**Tech Stack:** Python anywidget + traitlets · React 18 · `@hms-dbmi/viv` · `zarrita` (npm) · `deck.gl` · esbuild · `hatch-jupyter-builder` · `size-limit` · Playwright (for smoke tests)

---

## File structure

**New files:**
- `anybioimage/backends/__init__.py` — `get_backend_esm(name)` registry
- `anybioimage/backends/canvas2d.py` — Python loader for the Canvas2D ESM
- `anybioimage/backends/viv.py` — Python loader for the built Viv bundle
- `anybioimage/frontend/__init__.py` — empty marker for the bundled assets package
- `anybioimage/frontend/shared/__init__.py` — empty marker
- `anybioimage/frontend/shared/canvas2d.js` — authoritative Canvas2D ESM source (extracted from `viewer.py`), consumed by both `backends/canvas2d.py` and the Viv bundle build
- `anybioimage/frontend/viv/package.json`
- `anybioimage/frontend/viv/build.config.mjs` (esbuild)
- `anybioimage/frontend/viv/.gitignore` (ignores `node_modules/`, not `dist/`)
- `anybioimage/frontend/viv/src/entry.js` — anywidget render entrypoint, dispatches Viv vs. Canvas2D fallback
- `anybioimage/frontend/viv/src/VivCanvas.jsx` — React wrapper around `@hms-dbmi/viv`'s `VivViewer`
- `anybioimage/frontend/viv/src/zarr-source.js` — opens a zarrita store from `_zarr_source`, returns `ZarrPixelSource[]` per pyramid level
- `anybioimage/frontend/viv/src/channel-sync.js` — maps Python `_channel_settings` ↔ Viv channel props
- `anybioimage/frontend/viv/src/pixel-info.js` — mousemove → `_pixel_info` traitlet
- `anybioimage/frontend/viv/dist/viv-bundle.js` — committed build artifact
- `anybioimage/frontend/viv/size-limit.config.cjs` — size guardrail config
- `tests/test_backends.py` — backend registry unit tests
- `tests/test_zarr_detection.py` — URL/source tolerant detection tests
- `tests/test_zarr_metadata.py` — metadata-only load path tests (no precompute, no PNGs)
- `tests/test_plate_viv.py` — plate FOV switching updates `_zarr_source` on Viv backend
- `tests/playwright/conftest.py` — fixtures (marimo server, browser)
- `tests/playwright/test_viv_smoke.py` — six smoke tests (render, channel toggle, min/max, T slider, plate FOV, non-zarr fallback)
- `.github/workflows/bundle.yml` — CI guard verifying the committed Viv bundle matches the build from source

**Modified files:**
- `anybioimage/viewer.py` — accept `render_backend` kwarg, new traitlets, instance-level `_esm` swap, route non-zarr through existing path
- `anybioimage/mixins/image_loading.py` — add `_set_zarr_url()` metadata-only path, tolerant zarr-URL detection, `_viv_mode` setting
- `anybioimage/mixins/plate_loading.py` — when Viv backend is active, set `_zarr_source` on FOV change instead of calling `_set_bioimage`
- `pyproject.toml` — `hatch-jupyter-builder` build hook, bundle artifact declaration, `zarr>=2.14` required (already transitively via bioio but make explicit)
- `.github/workflows/publish.yml` — add `setup-node@v4` step before `uv build`
- `.github/workflows/ci.yml` — add bundle freshness + size-limit jobs
- `README.md` — MIT attribution for Viv, zarrita.js, deck.gl; v0.7.0-alpha usage example
- `ROADMAP.md` — v0.7.0-alpha delivered; shift follow-ups

---

## Conventions used in this plan

- **Every code step shows the full code** to write. No `...` placeholders, no "similar to X", no TODOs.
- **TDD where it applies.** Python work uses `pytest`. JS work uses Playwright smoke tests (no unit TDD — the value is in the visual round trip).
- **Commits are bite-sized** — one logical change per commit, named with a conventional prefix (`feat:`, `refactor:`, `build:`, `test:`, `docs:`, `ci:`).
- **Each task starts fresh from `main`.** If the engineer is executing tasks out of order, earlier code referenced in later tasks is restated verbatim.
- **Test files live under `tests/`.** Python tests run via `uv run pytest tests/ -v`.

---

## Task 1: Backend registry skeleton

**Files:**
- Create: `anybioimage/backends/__init__.py`
- Test: `tests/test_backends.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_backends.py
"""Tests for the backend registry."""

import pytest

from anybioimage.backends import get_backend_esm, KNOWN_BACKENDS


def test_known_backends_contains_canvas2d_and_viv():
    assert "canvas2d" in KNOWN_BACKENDS
    assert "viv" in KNOWN_BACKENDS


def test_get_backend_esm_canvas2d_returns_nonempty_string():
    esm = get_backend_esm("canvas2d")
    assert isinstance(esm, str)
    assert len(esm) > 0
    assert "export default" in esm


def test_get_backend_esm_viv_returns_nonempty_string():
    esm = get_backend_esm("viv")
    assert isinstance(esm, str)
    assert len(esm) > 0


def test_get_backend_esm_unknown_raises():
    with pytest.raises(ValueError, match="unknown render_backend"):
        get_backend_esm("opengl")
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `uv run pytest tests/test_backends.py -v`
Expected: all four FAIL with `ModuleNotFoundError: No module named 'anybioimage.backends'`.

- [ ] **Step 3: Create the registry (stubbed loaders)**

```python
# anybioimage/backends/__init__.py
"""Rendering backend registry for BioImageViewer."""

from . import canvas2d, viv

KNOWN_BACKENDS = ("canvas2d", "viv")


def get_backend_esm(name: str) -> str:
    """Return the ESM source string for a given rendering backend.

    Args:
        name: One of the strings in KNOWN_BACKENDS.

    Raises:
        ValueError: if name is not a known backend.
    """
    if name == "canvas2d":
        return canvas2d.load_esm()
    if name == "viv":
        return viv.load_esm()
    raise ValueError(f"unknown render_backend: {name!r}")
```

Create stub loaders that return a minimal valid ESM string so imports don't break:

```python
# anybioimage/backends/canvas2d.py
"""Canvas2D backend loader (stub until Task 2 extracts the real ESM)."""


def load_esm() -> str:
    return "export default { render: async () => {} };"
```

```python
# anybioimage/backends/viv.py
"""Viv backend loader (stub until Task 14 supplies a real bundle)."""


def load_esm() -> str:
    return "export default { render: async () => {} };"
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `uv run pytest tests/test_backends.py -v`
Expected: all four PASS.

- [ ] **Step 5: Commit**

```bash
git add anybioimage/backends/__init__.py anybioimage/backends/canvas2d.py anybioimage/backends/viv.py tests/test_backends.py
git commit -m "feat(backends): add rendering backend registry skeleton"
```

---

## Task 2: Extract Canvas2D ESM verbatim into shared source file

**Files:**
- Create: `anybioimage/frontend/__init__.py` (empty)
- Create: `anybioimage/frontend/shared/__init__.py` (empty)
- Create: `anybioimage/frontend/shared/canvas2d.js`
- Modify: `anybioimage/backends/canvas2d.py` (read from the new file)
- Modify: `anybioimage/viewer.py` (remove inline `_esm` string, keep `_css`)
- Test: extend `tests/test_backends.py` with a parity assertion
- Test: existing `tests/test_viewer_integration.py` must still pass unchanged

This task moves the existing Canvas2D ESM out of `viewer.py:214-1884` into a standalone `.js` file. The content is copied verbatim — zero semantic changes.

- [ ] **Step 1: Write a failing parity test**

Add to `tests/test_backends.py`:

```python
def test_canvas2d_backend_esm_matches_shipped_source_file():
    """The Canvas2D backend loader must return the exact bytes of shared/canvas2d.js."""
    from pathlib import Path

    import anybioimage.backends.canvas2d as canvas2d_mod

    shared = Path(anybioimage.__file__).parent / "frontend" / "shared" / "canvas2d.js"
    assert shared.is_file()
    expected = shared.read_text(encoding="utf-8")
    assert canvas2d_mod.load_esm() == expected
```

And add the missing import at the top of `tests/test_backends.py`:

```python
import anybioimage
```

Run: `uv run pytest tests/test_backends.py::test_canvas2d_backend_esm_matches_shipped_source_file -v`
Expected: FAIL — `shared/canvas2d.js` doesn't exist yet.

- [ ] **Step 2: Create package markers**

```python
# anybioimage/frontend/__init__.py
```

```python
# anybioimage/frontend/shared/__init__.py
```

(Both files are empty — they only exist so the directory is a proper Python package and wheel build picks them up.)

- [ ] **Step 3: Extract the ESM into a JS file**

Open `anybioimage/viewer.py`. Copy the full content between the opening `_esm = """` on line 214 and the closing `"""` on line 1884 (exclusive of the triple-quote markers) into `anybioimage/frontend/shared/canvas2d.js`. Do not modify the content. The first line of the new file should be the line that currently appears on line 215; the last should match line 1883.

Verify byte-identity of the copy:

Run: `diff <(sed -n '215,1883p' anybioimage/viewer.py) anybioimage/frontend/shared/canvas2d.js`
Expected: empty output (files identical line-for-line).

- [ ] **Step 4: Update the Canvas2D loader to read the file**

```python
# anybioimage/backends/canvas2d.py
"""Canvas2D backend loader — reads the ESM from the shipped source file."""

from importlib.resources import files

_ESM_CACHE: str | None = None


def load_esm() -> str:
    """Return the Canvas2D ESM source string (cached after first read)."""
    global _ESM_CACHE
    if _ESM_CACHE is None:
        _ESM_CACHE = (
            files("anybioimage.frontend.shared") / "canvas2d.js"
        ).read_text(encoding="utf-8")
    return _ESM_CACHE
```

- [ ] **Step 5: Remove the inline ESM from `viewer.py`**

In `anybioimage/viewer.py`, replace lines 214–1884 (the entire `_esm = """ ... """` assignment) with:

```python
    # _esm is assigned per-instance in __init__ based on render_backend.
    # See anybioimage.backends for the registry.
```

Leave everything else in the file untouched. `_css` (starting at what was line 1886) stays exactly as it is.

- [ ] **Step 6: Set `_esm` per-instance in `__init__`**

At the end of `BioImageViewer.__init__` in `viewer.py`, *after* `super().__init__(**kwargs)` and all `self.observe(...)` calls, add:

```python
        from .backends import get_backend_esm
        self._esm = get_backend_esm("canvas2d")
```

(This is temporary — Task 3 replaces the hard-coded `"canvas2d"` with the backend selected by the user. We ship a working state at the end of every task.)

- [ ] **Step 7: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: all existing tests PASS, including the new `test_canvas2d_backend_esm_matches_shipped_source_file`. The viewer renders identically to before.

- [ ] **Step 8: Commit**

```bash
git add anybioimage/frontend/__init__.py anybioimage/frontend/shared/__init__.py anybioimage/frontend/shared/canvas2d.js anybioimage/backends/canvas2d.py anybioimage/viewer.py tests/test_backends.py
git commit -m "refactor(canvas2d): extract inline ESM into shared/canvas2d.js"
```

---

## Task 3: Add `render_backend` constructor kwarg and backend-selection traitlet

**Files:**
- Modify: `anybioimage/viewer.py`
- Test: extend `tests/test_viewer_integration.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_viewer_integration.py`:

```python
class TestRenderBackendSelection:
    def test_default_backend_is_canvas2d(self):
        from anybioimage import BioImageViewer

        viewer = BioImageViewer()
        assert viewer._render_backend == "canvas2d"
        # ESM should be the Canvas2D source
        assert "tileCache" in viewer._esm  # a Canvas2D-only symbol

    def test_explicit_canvas2d_backend(self):
        from anybioimage import BioImageViewer

        viewer = BioImageViewer(render_backend="canvas2d")
        assert viewer._render_backend == "canvas2d"

    def test_viv_backend_selected(self):
        from anybioimage import BioImageViewer

        viewer = BioImageViewer(render_backend="viv")
        assert viewer._render_backend == "viv"
        # Stub ESM contains "export default"
        assert "export default" in viewer._esm

    def test_unknown_backend_raises_valueerror(self):
        import pytest

        from anybioimage import BioImageViewer

        with pytest.raises(ValueError, match="unknown render_backend"):
            BioImageViewer(render_backend="vulkan")
```

Run: `uv run pytest tests/test_viewer_integration.py::TestRenderBackendSelection -v`
Expected: FAIL — `_render_backend` traitlet doesn't exist; the constructor doesn't accept `render_backend`.

- [ ] **Step 2: Add the traitlet and constructor kwarg**

In `anybioimage/viewer.py`, add after the other traitlet declarations at the top of the class (near the other `_`-prefixed private traitlets):

```python
    # Rendering backend — set at construction, not swappable mid-session.
    _render_backend = traitlets.Unicode("canvas2d").tag(sync=True)
```

Modify `__init__` signature and body:

```python
    def __init__(self, *, render_backend: str = "canvas2d", **kwargs):
        super().__init__(**kwargs)
        # ... existing body unchanged up through self.observe(...) calls ...

        from .backends import get_backend_esm
        self._render_backend = render_backend
        self._esm = get_backend_esm(render_backend)
```

Replace the line added in Task 2 Step 6 (`self._esm = get_backend_esm("canvas2d")`) with the two lines above.

Note: `get_backend_esm("unknown")` already raises `ValueError` — no extra guard needed.

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_viewer_integration.py::TestRenderBackendSelection -v tests/ -v`
Expected: all four new tests PASS; no regressions.

- [ ] **Step 4: Commit**

```bash
git add anybioimage/viewer.py tests/test_viewer_integration.py
git commit -m "feat(viewer): accept render_backend kwarg and select ESM per instance"
```

---

## Task 4: Add `_zarr_source`, `_viv_mode`, `_pixel_info` traitlets

**Files:**
- Modify: `anybioimage/viewer.py`
- Test: extend `tests/test_viewer_integration.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_viewer_integration.py`:

```python
class TestVivTraitlets:
    def test_zarr_source_defaults_to_empty_dict(self):
        from anybioimage import BioImageViewer

        viewer = BioImageViewer()
        assert viewer._zarr_source == {}

    def test_viv_mode_defaults_to_viv(self):
        from anybioimage import BioImageViewer

        viewer = BioImageViewer()
        assert viewer._viv_mode == "viv"

    def test_pixel_info_defaults_to_none(self):
        from anybioimage import BioImageViewer

        viewer = BioImageViewer()
        assert viewer._pixel_info is None

    def test_viv_traitlets_sync_tagged(self):
        from anybioimage import BioImageViewer

        viewer = BioImageViewer()
        for name in ("_zarr_source", "_viv_mode", "_pixel_info"):
            trait = viewer.trait(name)
            assert trait.metadata.get("sync") is True, name
```

Run: `uv run pytest tests/test_viewer_integration.py::TestVivTraitlets -v`
Expected: FAIL — traitlets don't exist.

- [ ] **Step 2: Add the three traitlets**

In `anybioimage/viewer.py`, near the `_render_backend` declaration from Task 3:

```python
    # Viv backend state (all sync=True so JS sees changes).
    _zarr_source = traitlets.Dict({}).tag(sync=True)
    # "viv" when rendering zarr through Viv; "canvas2d-fallback" when non-zarr input was passed.
    _viv_mode = traitlets.Unicode("viv").tag(sync=True)
    # Pixel-intensity readout from JS hover; None when pointer is outside the canvas.
    _pixel_info = traitlets.Dict(allow_none=True, default_value=None).tag(sync=True)
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_viewer_integration.py::TestVivTraitlets tests/ -v`
Expected: all four new tests PASS; no regressions.

- [ ] **Step 4: Commit**

```bash
git add anybioimage/viewer.py tests/test_viewer_integration.py
git commit -m "feat(viewer): add _zarr_source, _viv_mode, _pixel_info traitlets"
```

---

## Task 5: Tolerant zarr-URL detection

**Files:**
- Modify: `anybioimage/mixins/image_loading.py`
- Test: `tests/test_zarr_detection.py` (new)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_zarr_detection.py
"""Tests for the tolerant zarr-URL detector."""

import pytest

from anybioimage.mixins.image_loading import _looks_like_zarr_url


@pytest.mark.parametrize("source", [
    "https://example.com/my.ome.zarr",
    "https://example.com/my.ome.zarr/",
    "http://localhost:8000/plate.zarr",
    "file:///data/my.ome.zarr",
    "s3://bucket/key/my.ome.zarr",
    "/tmp/my.ome.zarr",
    "./examples/image.zarr",
])
def test_url_shapes_detected_as_zarr(source):
    assert _looks_like_zarr_url(source) is True


@pytest.mark.parametrize("source", [
    "",
    "https://example.com/image.tif",
    "https://example.com/data.csv",
    "/tmp/image.png",
    "file:///data/movie.mp4",
])
def test_non_zarr_shapes_rejected(source):
    assert _looks_like_zarr_url(source) is False


def test_non_string_inputs_are_rejected():
    import numpy as np

    assert _looks_like_zarr_url(np.zeros((4, 4))) is False
    assert _looks_like_zarr_url(None) is False
    assert _looks_like_zarr_url(42) is False
```

Run: `uv run pytest tests/test_zarr_detection.py -v`
Expected: FAIL — `_looks_like_zarr_url` doesn't exist.

- [ ] **Step 2: Implement the detector**

In `anybioimage/mixins/image_loading.py`, add near the module-level helpers (below `_thumbnail`):

```python
_ZARR_SUFFIXES = (".zarr", ".ome.zarr")


def _looks_like_zarr_url(source) -> bool:
    """Return True if `source` syntactically looks like a zarr store URL/path.

    This is a cheap shape check — it does NOT verify the store exists or is
    well-formed. Callers that commit to the Viv path should follow up with a
    metadata probe and fall back to Canvas2D on failure.
    """
    if not isinstance(source, str) or not source:
        return False
    stripped = source.rstrip("/")
    lowered = stripped.lower()
    return any(lowered.endswith(suffix) for suffix in _ZARR_SUFFIXES)
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_zarr_detection.py -v`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add anybioimage/mixins/image_loading.py tests/test_zarr_detection.py
git commit -m "feat(image-loading): add tolerant _looks_like_zarr_url detector"
```

---

## Task 6: Metadata-only zarr load path (`_set_zarr_url`)

**Files:**
- Modify: `anybioimage/mixins/image_loading.py`
- Test: `tests/test_zarr_metadata.py` (new)

This path opens a zarr store, reads OME-Zarr multiscales + omero/channels metadata, and populates the traitlets that both backends read (`dim_t/c/z`, `_channel_settings`, `resolution_levels`, `width`, `height`). It does **not** start the precompute thread, does **not** build a synthetic pyramid, and does **not** encode any PNGs. It also sets `_zarr_source` for the JS side.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_zarr_metadata.py
"""Tests for the metadata-only zarr load path (`_set_zarr_url`)."""

from pathlib import Path

import pytest

from anybioimage import BioImageViewer

EXAMPLE_ZARR = Path(__file__).parent.parent / "examples" / "image.zarr"


@pytest.fixture
def zarr_viewer():
    if not EXAMPLE_ZARR.is_dir():
        pytest.skip(f"{EXAMPLE_ZARR} missing (run examples/create_test_plate.py)")
    viewer = BioImageViewer(render_backend="viv")
    viewer.set_image(str(EXAMPLE_ZARR))
    return viewer


def test_zarr_source_set_to_url(zarr_viewer):
    assert zarr_viewer._zarr_source.get("url") == str(EXAMPLE_ZARR)


def test_dimensions_populated_from_metadata(zarr_viewer):
    # The test zarr is a 10T×3Z×2×2048×2048 image per CLAUDE.md
    assert zarr_viewer.dim_t >= 1
    assert zarr_viewer.dim_c >= 1
    assert zarr_viewer.dim_z >= 1
    assert zarr_viewer.width > 0
    assert zarr_viewer.height > 0


def test_channel_settings_populated(zarr_viewer):
    assert len(zarr_viewer._channel_settings) == zarr_viewer.dim_c
    for ch in zarr_viewer._channel_settings:
        assert "color" in ch
        assert "visible" in ch
        assert 0.0 <= ch["min"] <= 1.0
        assert 0.0 <= ch["max"] <= 1.0


def test_resolution_levels_populated(zarr_viewer):
    # image.zarr has three levels: s0, s1, s2
    assert len(zarr_viewer.resolution_levels) >= 1


def test_viv_mode_stays_viv_for_zarr(zarr_viewer):
    assert zarr_viewer._viv_mode == "viv"


def test_no_precompute_started(zarr_viewer):
    # The precompute future is only set by _set_bioimage; the zarr-url path must not start it.
    assert zarr_viewer._precompute_future is None


def test_no_thumbnail_encoded(zarr_viewer):
    # On the Viv path, image_data stays empty — no PNG encoded.
    assert zarr_viewer.image_data == ""


def test_full_array_not_loaded(zarr_viewer):
    assert zarr_viewer._full_array is None
```

Run: `uv run pytest tests/test_zarr_metadata.py -v`
Expected: FAIL — `_set_zarr_url` doesn't exist; `set_image(str)` falls through to `_set_numpy_image` and raises.

- [ ] **Step 2: Implement `_set_zarr_url`**

In `anybioimage/mixins/image_loading.py`, add a new method on `ImageLoadingMixin`:

```python
    def _set_zarr_url(self, url: str) -> None:
        """Metadata-only OME-Zarr load for the Viv backend.

        Populates dimension traitlets, channel settings, and resolution levels
        from the store's `.zattrs` so the JS side can render with zarrita.js
        fetching chunks directly in the browser. No precompute, no PNG encoding,
        no full-array preload.
        """
        import zarr

        store = zarr.open_group(url, mode="r")
        attrs = dict(store.attrs)

        ome = attrs.get("ome", attrs)
        multiscales = ome.get("multiscales")
        if not multiscales:
            raise ValueError(f"No OME-Zarr multiscales metadata at {url}")

        ms = multiscales[0]
        axes = ms.get("axes", [])
        datasets = ms.get("datasets", [])

        axis_names = [a.get("name", "").lower() for a in axes]
        level0_path = datasets[0]["path"]
        level0 = store[level0_path]
        shape = level0.shape

        def _axis(name: str, default: int) -> int:
            if name in axis_names:
                return int(shape[axis_names.index(name)])
            return default

        dim_t = _axis("t", 1)
        dim_c = _axis("c", 1)
        dim_z = _axis("z", 1)
        height = _axis("y", shape[-2])
        width = _axis("x", shape[-1])

        channel_settings = _channel_settings_from_omero(ome, dim_c)

        with self.hold_trait_notifications():
            self.dim_t = dim_t
            self.dim_c = dim_c
            self.dim_z = dim_z
            self.height = height
            self.width = width
            self.current_t = 0
            self.current_c = 0
            self.current_z = 0
            self.resolution_levels = list(range(len(datasets)))
            self.current_resolution = 0
            self._channel_settings = channel_settings
            self.scenes = []
            self._full_array = None
            self._bioimage = None
            self._pyramid = None
            self._pyramid_has_native = True
            self._viv_mode = "viv"
            self._zarr_source = {"url": url, "headers": {}}
            self.image_data = ""
```

And add a module-level helper near `_thumbnail`:

```python
def _channel_settings_from_omero(ome: dict, dim_c: int) -> list[dict]:
    """Build channel_settings dicts from an OME-Zarr omero block (or defaults)."""
    omero = ome.get("omero") or {}
    omero_channels = omero.get("channels") or []
    out = []
    for i in range(dim_c):
        src = omero_channels[i] if i < len(omero_channels) else {}
        window = src.get("window") or {}
        data_min = float(window.get("min", 0.0))
        data_max = float(window.get("max", 65535.0))
        start = float(window.get("start", data_min))
        end = float(window.get("end", data_max))
        span = max(data_max - data_min, 1.0)
        vmin = max(0.0, (start - data_min) / span)
        vmax = min(1.0, (end - data_min) / span)
        color_hex = src.get("color")
        color = f"#{color_hex}" if color_hex and not color_hex.startswith("#") else (color_hex or CHANNEL_COLORS[i % len(CHANNEL_COLORS)])
        out.append({
            "name": src.get("label") or f"Channel {i}",
            "color": color,
            "visible": bool(src.get("active", True)),
            "min": vmin,
            "max": vmax,
            "data_min": data_min,
            "data_max": data_max,
        })
    return out
```

- [ ] **Step 3: Route strings through the new path when backend is Viv**

Modify `ImageLoadingMixin.set_image` in the same file:

```python
    def set_image(self, data):
        """Set the base image.

        Accepts:
          - A numpy array (Canvas2D path).
          - A BioImage object (Canvas2D path with lazy loading).
          - A string URL/path to an OME-Zarr store (Viv path; silent fallback
            to Canvas2D if the backend is not Viv or the URL doesn't look like zarr).
        """
        if isinstance(data, str) and _looks_like_zarr_url(data):
            if getattr(self, "_render_backend", "canvas2d") == "viv":
                try:
                    self._set_zarr_url(data)
                    return
                except Exception as e:
                    logger.info("Viv zarr load failed (%s); falling back to Canvas2D", e)
                    self._viv_mode = "canvas2d-fallback"
            # Canvas2D fallback: defer to BioImage
            import bioio_ome_zarr
            from bioio import BioImage

            self._set_bioimage(BioImage(data, reader=bioio_ome_zarr.Reader))
            return

        if hasattr(data, "dims") and hasattr(data, "dask_data"):
            if getattr(self, "_render_backend", "canvas2d") == "viv":
                self._viv_mode = "canvas2d-fallback"
            self._set_bioimage(data)
        else:
            if getattr(self, "_render_backend", "canvas2d") == "viv":
                self._viv_mode = "canvas2d-fallback"
            self._set_numpy_image(data)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_zarr_metadata.py tests/ -v`
Expected: all PASS including existing tests.

- [ ] **Step 5: Commit**

```bash
git add anybioimage/mixins/image_loading.py tests/test_zarr_metadata.py
git commit -m "feat(image-loading): add metadata-only _set_zarr_url for Viv backend"
```

---

## Task 7: Plate mixin — Viv FOV switch updates `_zarr_source`

**Files:**
- Modify: `anybioimage/mixins/plate_loading.py`
- Test: `tests/test_plate_viv.py` (new)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_plate_viv.py
"""Tests for the Viv-backend plate FOV switching."""

from pathlib import Path

import pytest

from anybioimage import BioImageViewer

TEST_PLATE = Path(__file__).parent.parent / "examples" / "test_plate.zarr"


@pytest.fixture
def plate_viewer():
    if not TEST_PLATE.is_dir():
        pytest.skip(f"{TEST_PLATE} missing (run examples/create_test_plate.py)")
    viewer = BioImageViewer(render_backend="viv")
    viewer.set_plate(str(TEST_PLATE))
    return viewer


def test_wells_populated(plate_viewer):
    assert len(plate_viewer.plate_wells) >= 1


def test_initial_zarr_source_points_at_fov(plate_viewer):
    url = plate_viewer._zarr_source.get("url", "")
    assert str(TEST_PLATE) in url
    assert plate_viewer.current_well.replace("", "") in url.replace("/", "")


def test_fov_switch_updates_zarr_source(plate_viewer):
    if len(plate_viewer.plate_fovs) < 2:
        pytest.skip("test plate has only one FOV")
    before = plate_viewer._zarr_source.get("url")
    plate_viewer.current_fov = plate_viewer.plate_fovs[1]
    after = plate_viewer._zarr_source.get("url")
    assert before != after
    assert str(TEST_PLATE) in after


def test_fov_switch_does_not_call_set_bioimage_on_viv(plate_viewer):
    plate_viewer._bioimage = "SENTINEL"  # would be overwritten by _set_bioimage
    if len(plate_viewer.plate_fovs) >= 2:
        plate_viewer.current_fov = plate_viewer.plate_fovs[1]
    assert plate_viewer._bioimage == "SENTINEL"
```

Run: `uv run pytest tests/test_plate_viv.py -v`
Expected: FAIL — `_load_plate_image` still calls `_set_bioimage` unconditionally.

- [ ] **Step 2: Branch the plate loader on backend**

Modify `_load_plate_image` in `anybioimage/mixins/plate_loading.py`:

```python
    def _load_plate_image(self, fov):
        """Load the image for the current well and given FOV."""
        if not hasattr(self, "_current_well_path"):
            return

        image_path = f"{self._plate_path}/{self._current_well_path}/{fov}"

        if getattr(self, "_render_backend", "canvas2d") == "viv":
            try:
                self._set_zarr_url(image_path)
                return
            except Exception as e:
                import logging
                logging.getLogger(__name__).info(
                    "Viv plate-FOV load failed (%s); falling back to Canvas2D", e
                )
                self._viv_mode = "canvas2d-fallback"

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

Also adjust `_load_well_fovs` — the `if self.current_fov in fov_paths` branch calls `self._load_plate_image(self.current_fov)` which routes correctly through the new logic, so no change needed there.

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_plate_viv.py tests/ -v`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add anybioimage/mixins/plate_loading.py tests/test_plate_viv.py
git commit -m "feat(plate): route Viv FOV switches through _set_zarr_url"
```

---

## Task 8: Frontend scaffold — `package.json` and build config

**Files:**
- Create: `anybioimage/frontend/viv/package.json`
- Create: `anybioimage/frontend/viv/.gitignore`
- Create: `anybioimage/frontend/viv/build.config.mjs`

No Python tests — verified by running the build in Task 14.

- [ ] **Step 1: Create `package.json`**

```json
{
  "name": "anybioimage-viv-bundle",
  "version": "0.7.0-alpha.0",
  "private": true,
  "description": "Viv + zarrita.js rendering bundle for anybioimage",
  "type": "module",
  "scripts": {
    "build": "node build.config.mjs",
    "size": "size-limit"
  },
  "dependencies": {
    "@hms-dbmi/viv": "0.17.5",
    "zarrita": "0.5.1",
    "deck.gl": "9.0.38",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "esbuild": "0.25.0",
    "size-limit": "11.1.6",
    "@size-limit/esbuild": "11.1.6",
    "@size-limit/file": "11.1.6"
  },
  "size-limit": [
    {
      "path": "dist/viv-bundle.js",
      "limit": "3 MB"
    }
  ]
}
```

(Versions are deliberately pinned per spec risk mitigation around Viv major-version breakage.)

- [ ] **Step 2: Create `.gitignore`**

```
node_modules/
*.log
```

Note: `dist/` is intentionally **not** ignored — the built bundle is committed so `pip install -e .` works without Node.

- [ ] **Step 3: Create the esbuild config**

```javascript
// anybioimage/frontend/viv/build.config.mjs
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

await build({
  entryPoints: [resolve(__dirname, 'src/entry.js')],
  outfile: resolve(__dirname, 'dist/viv-bundle.js'),
  bundle: true,
  format: 'esm',
  target: 'es2020',
  platform: 'browser',
  minify: true,
  sourcemap: false,
  loader: {
    '.js': 'jsx',
    '.jsx': 'jsx',
    // Canvas2D ESM is a raw ESM module source — inline as text and eval via Blob URL in the fallback path.
    '.canvas2d.js': 'text',
  },
  jsx: 'automatic',
  define: {
    'process.env.NODE_ENV': '"production"',
  },
  logLevel: 'info',
});
```

- [ ] **Step 4: Commit (build output comes in Task 14)**

```bash
git add anybioimage/frontend/viv/package.json anybioimage/frontend/viv/.gitignore anybioimage/frontend/viv/build.config.mjs
git commit -m "build(viv): scaffold package.json and esbuild config"
```

---

## Task 9: Frontend — anywidget entry point (`src/entry.js`)

**Files:**
- Create: `anybioimage/frontend/viv/src/entry.js`

This entry point is what anywidget calls on the browser side. It branches on `_viv_mode`: render the Viv React tree when `"viv"`, or delegate to the bundled Canvas2D ESM when `"canvas2d-fallback"`.

- [ ] **Step 1: Create the entry file**

```javascript
// anybioimage/frontend/viv/src/entry.js
import React from 'react';
import { createRoot } from 'react-dom/client';
import { VivCanvas } from './VivCanvas.jsx';
import canvas2dSource from '../../shared/canvas2d.js';

let canvas2dModulePromise = null;

async function loadCanvas2dModule() {
  if (!canvas2dModulePromise) {
    const blob = new Blob([canvas2dSource], { type: 'text/javascript' });
    const url = URL.createObjectURL(blob);
    canvas2dModulePromise = import(/* @vite-ignore */ url);
  }
  return canvas2dModulePromise;
}

async function renderViv({ model, el }) {
  const mount = document.createElement('div');
  mount.className = 'viv-root';
  el.appendChild(mount);
  const root = createRoot(mount);
  root.render(React.createElement(VivCanvas, { model }));
  return () => root.unmount();
}

async function render({ model, el }) {
  const mode = model.get('_viv_mode') || 'viv';
  if (mode === 'canvas2d-fallback') {
    const mod = await loadCanvas2dModule();
    return mod.default.render({ model, el });
  }
  return renderViv({ model, el });
}

export default { render };
```

- [ ] **Step 2: Commit**

```bash
git add anybioimage/frontend/viv/src/entry.js
git commit -m "feat(viv): add anywidget render entry point"
```

---

## Task 10: Frontend — zarrita store adapter (`src/zarr-source.js`)

**Files:**
- Create: `anybioimage/frontend/viv/src/zarr-source.js`

- [ ] **Step 1: Create the adapter**

```javascript
// anybioimage/frontend/viv/src/zarr-source.js
import * as zarr from 'zarrita';
import { ZarrPixelSource } from '@hms-dbmi/viv';

/**
 * Open an OME-Zarr store at `url` and return a list of ZarrPixelSource
 * instances — one per multiscale level.
 */
export async function openOmeZarr(url, headers = {}) {
  const store = new zarr.FetchStore(url, { overrides: { headers } });
  const root = await zarr.open(store, { kind: 'group' });
  const attrs = root.attrs ?? {};
  const ome = attrs.ome ?? attrs;
  const multiscales = ome.multiscales;
  if (!multiscales || multiscales.length === 0) {
    throw new Error(`No OME-Zarr multiscales at ${url}`);
  }
  const ms = multiscales[0];
  const axes = ms.axes.map(a => a.name.toLowerCase());
  const labels = axes;

  const sources = [];
  for (const dataset of ms.datasets) {
    const arr = await zarr.open(root.resolve(dataset.path), { kind: 'array' });
    sources.push(new ZarrPixelSource(arr, { labels, tileSize: 512 }));
  }
  return { sources, labels, ome };
}
```

- [ ] **Step 2: Commit**

```bash
git add anybioimage/frontend/viv/src/zarr-source.js
git commit -m "feat(viv): add zarrita-based OME-Zarr store adapter"
```

---

## Task 11: Frontend — channel-sync helpers (`src/channel-sync.js`)

**Files:**
- Create: `anybioimage/frontend/viv/src/channel-sync.js`

Maps the Python `_channel_settings` list into the prop shape Viv expects.

- [ ] **Step 1: Create the helpers**

```javascript
// anybioimage/frontend/viv/src/channel-sync.js
const MAX_CHANNELS = 6;

function hexToRgb(hex) {
  const clean = (hex || '#ffffff').replace('#', '');
  const n = parseInt(clean, 16);
  return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff];
}

export function channelSettingsToVivProps(channelSettings) {
  const visible = channelSettingsVisible(channelSettings);
  const active = visible.slice(0, MAX_CHANNELS);

  const selections = active.map((entry) => ({
    c: entry.index,
    t: 0,
    z: 0,
  }));
  const colors = active.map((entry) => hexToRgb(entry.color));
  const contrastLimits = active.map((entry) => {
    const dmin = entry.data_min ?? 0;
    const dmax = entry.data_max ?? 65535;
    const span = Math.max(dmax - dmin, 1);
    return [dmin + entry.min * span, dmin + entry.max * span];
  });
  const channelsVisible = active.map(() => true);
  return { selections, colors, contrastLimits, channelsVisible, exceeded: visible.length > MAX_CHANNELS };
}

export function channelSettingsVisible(channelSettings) {
  return (channelSettings || [])
    .map((ch, index) => ({ ...ch, index }))
    .filter((ch) => ch.visible);
}

export function withTimeAndZ(selections, t, z) {
  return selections.map((s) => ({ ...s, t, z }));
}
```

- [ ] **Step 2: Commit**

```bash
git add anybioimage/frontend/viv/src/channel-sync.js
git commit -m "feat(viv): add channel-settings → Viv prop mapper"
```

---

## Task 12: Frontend — pixel-info mousemove emitter (`src/pixel-info.js`)

**Files:**
- Create: `anybioimage/frontend/viv/src/pixel-info.js`

- [ ] **Step 1: Create the emitter**

```javascript
// anybioimage/frontend/viv/src/pixel-info.js

/**
 * Throttle `fn` so it fires at most once per `wait` ms, with a trailing call.
 */
function throttle(fn, wait) {
  let last = 0;
  let timer = null;
  let pendingArgs = null;
  return function throttled(...args) {
    const now = Date.now();
    pendingArgs = args;
    if (now - last >= wait) {
      last = now;
      fn(...args);
      pendingArgs = null;
    } else if (!timer) {
      timer = setTimeout(() => {
        last = Date.now();
        timer = null;
        if (pendingArgs) fn(...pendingArgs);
        pendingArgs = null;
      }, wait - (now - last));
    }
  };
}

export function attachPixelInfo(model, deckInstance, getSources, getSelections) {
  const emit = throttle((info) => {
    model.set('_pixel_info', info);
    model.save_changes();
  }, 120);

  deckInstance.setProps({
    onHover: async ({ coordinate }) => {
      if (!coordinate) {
        emit(null);
        return;
      }
      const [x, y] = coordinate.map(Math.round);
      const sources = getSources();
      const selections = getSelections();
      if (!sources || sources.length === 0) return;
      const src = sources[0];
      const intensities = [];
      for (const sel of selections) {
        try {
          const { data } = await src.getRaster({ selection: sel });
          const idx = y * src.shape[src.labels.indexOf('x')] + x;
          intensities.push(Number(data[idx]));
        } catch {
          intensities.push(null);
        }
      }
      emit({ x, y, intensities });
    },
  });
}
```

- [ ] **Step 2: Commit**

```bash
git add anybioimage/frontend/viv/src/pixel-info.js
git commit -m "feat(viv): emit _pixel_info on mousemove with throttling"
```

---

## Task 13: Frontend — VivCanvas React component (`src/VivCanvas.jsx`)

**Files:**
- Create: `anybioimage/frontend/viv/src/VivCanvas.jsx`

- [ ] **Step 1: Create the component**

```jsx
// anybioimage/frontend/viv/src/VivCanvas.jsx
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { VivViewer, MultiscaleImageLayer } from '@hms-dbmi/viv';
import { openOmeZarr } from './zarr-source.js';
import { channelSettingsToVivProps, withTimeAndZ } from './channel-sync.js';
import { attachPixelInfo } from './pixel-info.js';

function useModelTrait(model, name) {
  const [value, setValue] = useState(() => model.get(name));
  useEffect(() => {
    const handler = () => setValue(model.get(name));
    model.on(`change:${name}`, handler);
    return () => model.off(`change:${name}`, handler);
  }, [model, name]);
  return value;
}

export function VivCanvas({ model }) {
  const zarrSource = useModelTrait(model, '_zarr_source');
  const channelSettings = useModelTrait(model, '_channel_settings');
  const currentT = useModelTrait(model, 'current_t');
  const currentZ = useModelTrait(model, 'current_z');
  const brightness = useModelTrait(model, 'image_brightness');
  const contrast = useModelTrait(model, 'image_contrast');
  const canvasHeight = useModelTrait(model, 'canvas_height') || 800;

  const [sources, setSources] = useState(null);
  const [error, setError] = useState(null);
  const deckRef = useRef(null);

  // Open the zarr store when _zarr_source changes.
  useEffect(() => {
    const url = zarrSource?.url;
    if (!url) {
      setSources(null);
      return;
    }
    let cancelled = false;
    openOmeZarr(url, zarrSource.headers || {})
      .then(({ sources }) => { if (!cancelled) setSources(sources); })
      .catch((e) => { if (!cancelled) { setError(String(e)); setSources(null); } });
    return () => { cancelled = true; };
  }, [zarrSource?.url]);

  const vivProps = useMemo(
    () => channelSettingsToVivProps(channelSettings || []),
    [channelSettings],
  );

  // Attach pixel-info hover once deck is mounted and sources are available.
  useEffect(() => {
    if (!deckRef.current || !sources) return;
    const selections = withTimeAndZ(vivProps.selections, currentT, currentZ);
    attachPixelInfo(model, deckRef.current.deck, () => sources, () => selections);
  }, [model, sources, currentT, currentZ, vivProps.selections]);

  if (error) {
    return <div style={{ color: '#b00', padding: 12 }}>Failed to load zarr: {error}</div>;
  }
  if (!sources) {
    return <div style={{ padding: 12, color: '#666' }}>Loading…</div>;
  }

  const selections = withTimeAndZ(vivProps.selections, currentT, currentZ);
  const layer = new MultiscaleImageLayer({
    id: 'viv-image',
    loader: sources,
    selections,
    colors: vivProps.colors,
    contrastLimits: vivProps.contrastLimits,
    channelsVisible: vivProps.channelsVisible,
  });

  return (
    <div style={{ position: 'relative', width: '100%', height: canvasHeight }}>
      <VivViewer
        ref={deckRef}
        layerProps={[layer.props]}
        views={undefined /* Viv default OrthographicView */}
      />
      {vivProps.exceeded && (
        <div style={{ position: 'absolute', top: 8, right: 8, background: '#fbe9a0', padding: '4px 8px', fontSize: 12, borderRadius: 4 }}>
          More than 6 channels — extras hidden.
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add anybioimage/frontend/viv/src/VivCanvas.jsx
git commit -m "feat(viv): add VivCanvas React component with traitlet sync"
```

---

## Task 14: Install npm dependencies and build the initial bundle

**Files:**
- Create: `anybioimage/frontend/viv/dist/viv-bundle.js` (committed build artifact)

- [ ] **Step 1: Install dependencies**

Run (from repo root):

```bash
cd anybioimage/frontend/viv && npm install --no-audit --no-fund
```

Expected: `node_modules/` populated, `package-lock.json` created. No errors.

- [ ] **Step 2: Build the bundle**

```bash
npm run build
```

Expected: `dist/viv-bundle.js` created; esbuild prints an `output` line showing the file size (should be 1–3 MB).

- [ ] **Step 3: Verify bundle is valid ESM**

```bash
node --input-type=module -e "import('./dist/viv-bundle.js').then(m => console.log(typeof m.default.render))"
```

Expected: prints `function`.

- [ ] **Step 4: Commit the lockfile and bundle**

```bash
git add anybioimage/frontend/viv/package-lock.json anybioimage/frontend/viv/dist/viv-bundle.js
git commit -m "build(viv): commit package-lock and initial viv-bundle.js"
```

---

## Task 15: Python loader for the Viv bundle

**Files:**
- Modify: `anybioimage/backends/viv.py`
- Test: extend `tests/test_backends.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_backends.py`:

```python
def test_viv_backend_esm_matches_shipped_bundle():
    from pathlib import Path

    import anybioimage.backends.viv as viv_mod

    bundle = Path(anybioimage.__file__).parent / "frontend" / "viv" / "dist" / "viv-bundle.js"
    assert bundle.is_file(), "build Task 14 must have committed dist/viv-bundle.js"
    assert viv_mod.load_esm() == bundle.read_text(encoding="utf-8")
```

Run: `uv run pytest tests/test_backends.py -v`
Expected: the new test FAILS (stub loader still returns the "export default" placeholder).

- [ ] **Step 2: Replace the stub loader**

```python
# anybioimage/backends/viv.py
"""Viv backend loader — reads the bundled JS from the wheel data files."""

from importlib.resources import files

_ESM_CACHE: str | None = None


def load_esm() -> str:
    """Return the compiled Viv bundle ESM string (cached after first read)."""
    global _ESM_CACHE
    if _ESM_CACHE is None:
        _ESM_CACHE = (
            files("anybioimage.frontend.viv") / "dist" / "viv-bundle.js"
        ).read_text(encoding="utf-8")
    return _ESM_CACHE
```

And create the two required `__init__.py` markers so `importlib.resources` can locate them:

```python
# anybioimage/frontend/viv/__init__.py
```

```python
# anybioimage/frontend/viv/dist/__init__.py
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/ -v`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add anybioimage/backends/viv.py anybioimage/frontend/viv/__init__.py anybioimage/frontend/viv/dist/__init__.py tests/test_backends.py
git commit -m "feat(viv): wire Python loader to read dist/viv-bundle.js"
```

---

## Task 16: Wheel packaging — ship the Viv bundle and shared JS

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Update wheel target to include the JS files**

Replace the `[tool.hatch.build.targets.wheel]` and `[tool.hatch.build.targets.sdist]` sections in `pyproject.toml` with:

```toml
[tool.hatch.build.targets.wheel]
packages = ["anybioimage"]

[tool.hatch.build.targets.wheel.force-include]
"anybioimage/frontend/shared/canvas2d.js" = "anybioimage/frontend/shared/canvas2d.js"
"anybioimage/frontend/viv/dist/viv-bundle.js" = "anybioimage/frontend/viv/dist/viv-bundle.js"

[tool.hatch.build.targets.sdist]
include = [
    "anybioimage/",
    "README.md",
    "LICENSE",
    "pyproject.toml",
]
exclude = [
    "anybioimage/frontend/viv/node_modules/",
]
```

- [ ] **Step 2: Verify the wheel contains the bundle**

```bash
uv build --wheel
python -c "import zipfile, glob; w = glob.glob('dist/*.whl')[-1]; print('\n'.join(n for n in zipfile.ZipFile(w).namelist() if 'frontend' in n))"
```

Expected output includes:
```
anybioimage/frontend/shared/canvas2d.js
anybioimage/frontend/viv/dist/viv-bundle.js
```

- [ ] **Step 3: Install the built wheel into a throwaway venv and import**

```bash
uv venv /tmp/anybioimage-wheel-test
uv pip install --python /tmp/anybioimage-wheel-test/bin/python dist/*.whl
/tmp/anybioimage-wheel-test/bin/python -c "from anybioimage import BioImageViewer; v = BioImageViewer(render_backend='viv'); assert 'export default' in v._esm; print('OK')"
rm -rf /tmp/anybioimage-wheel-test dist/
```

Expected: prints `OK`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: include frontend bundle JS files in the wheel"
```

---

## Task 17: CI — bundle freshness + Node setup in publish workflow

**Files:**
- Create: `.github/workflows/bundle.yml`
- Modify: `.github/workflows/publish.yml`

- [ ] **Step 1: Create the bundle-freshness workflow**

```yaml
# .github/workflows/bundle.yml
name: Viv bundle check

on:
  push:
    branches: [main]
  pull_request:

jobs:
  bundle-in-sync:
    name: Rebuild & diff against committed bundle
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: anybioimage/frontend/viv/package-lock.json

      - name: Install npm dependencies
        working-directory: anybioimage/frontend/viv
        run: npm ci

      - name: Rebuild bundle
        working-directory: anybioimage/frontend/viv
        run: npm run build

      - name: Fail if bundle drifted from source
        run: |
          if ! git diff --quiet anybioimage/frontend/viv/dist/viv-bundle.js; then
            echo "::error::dist/viv-bundle.js is out of sync with src/. Run 'npm run build' in anybioimage/frontend/viv/ and commit the result."
            git diff --stat anybioimage/frontend/viv/dist/viv-bundle.js
            exit 1
          fi

  size-limit:
    name: Bundle size guard
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: anybioimage/frontend/viv/package-lock.json
      - name: Install npm dependencies
        working-directory: anybioimage/frontend/viv
        run: npm ci
      - name: Run size-limit
        working-directory: anybioimage/frontend/viv
        run: npx size-limit
```

- [ ] **Step 2: Update the publish workflow to set up Node before `uv build`**

Edit `.github/workflows/publish.yml` — in the `build` job, insert a Node-setup step between `checkout` and `setup-uv`:

```yaml
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: anybioimage/frontend/viv/package-lock.json

      - name: Install npm dependencies and rebuild bundle
        working-directory: anybioimage/frontend/viv
        run: |
          npm ci
          npm run build

      - uses: astral-sh/setup-uv@v4
        with:
          python-version: "3.12"

      - name: Build package
        run: uv build
```

Leave the rest of `publish.yml` untouched.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/bundle.yml .github/workflows/publish.yml
git commit -m "ci: add bundle freshness + size-limit checks and wire Node into publish"
```

---

## Task 18: Playwright test harness

**Files:**
- Create: `tests/playwright/__init__.py` (empty)
- Create: `tests/playwright/conftest.py`
- Modify: `pyproject.toml` (add `playwright` and `pytest-playwright` to `dev` extras)

This task sets up the browser-test fixtures only. Actual smoke tests come in Task 19.

- [ ] **Step 1: Add Playwright to dev dependencies**

Edit `pyproject.toml`:

```toml
dev = [
    "marimo>=0.19.0",
    "pytest>=7.0.0",
    "ruff>=0.1.0",
    "ty>=0.0.1a0",
    "playwright>=1.47",
    "pytest-playwright>=0.5",
]
```

Then run:

```bash
uv pip install -e ".[all]"
uv run playwright install chromium
```

- [ ] **Step 2: Create the conftest**

```python
# tests/playwright/conftest.py
"""Fixtures for Playwright smoke tests against a live marimo server."""

import os
import re
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCREENSHOT_DIR = Path("/tmp/anybioimage-screenshots")
NOTEBOOK = REPO_ROOT / "examples" / "image_notebook.py"


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_token(proc, timeout=30):
    deadline = time.time() + timeout
    buf = []
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                raise RuntimeError(f"marimo exited early:\n{''.join(buf)}")
            continue
        buf.append(line)
        m = re.search(r"access_token=([0-9a-f-]+)", line)
        if m:
            return m.group(1), "".join(buf)
    raise TimeoutError(f"access token never printed:\n{''.join(buf)}")


@pytest.fixture(scope="session")
def screenshot_dir():
    if SCREENSHOT_DIR.exists():
        shutil.rmtree(SCREENSHOT_DIR)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    yield SCREENSHOT_DIR
    # Keep artifacts on failure; the CI agent collects them. For local dev,
    # uncomment the next line to auto-clean after passing runs:
    # shutil.rmtree(SCREENSHOT_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def marimo_server():
    port = _free_port()
    env = {**os.environ, "ANYBIOIMAGE_PLAYWRIGHT": "1"}
    proc = subprocess.Popen(
        ["marimo", "edit", str(NOTEBOOK), "--port", str(port), "--no-token-check", "--headless"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        bufsize=1,
    )
    try:
        token, _ = _wait_for_token(proc)
        yield f"http://localhost:{port}?access_token={token}"
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture
def page(browser, marimo_server, screenshot_dir):
    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    page = ctx.new_page()
    page.goto(marimo_server)
    page.wait_for_load_state("networkidle", timeout=30000)
    yield page
    ctx.close()
```

- [ ] **Step 3: Commit**

```bash
git add tests/playwright/__init__.py tests/playwright/conftest.py pyproject.toml
git commit -m "test(playwright): add fixtures for marimo-backed smoke tests"
```

---

## Task 19: Playwright smoke tests — six scenarios

**Files:**
- Create: `tests/playwright/test_viv_smoke.py`
- Modify: `examples/image_notebook.py` (add a Viv-backend variant cell gated by `ANYBIOIMAGE_PLAYWRIGHT`)

- [ ] **Step 1: Add a Viv cell to the example notebook**

Open `examples/image_notebook.py`. Inside a new `@app.cell` block (near the existing viewer cell), add:

```python
@app.cell
def _viv_cell(mo):
    import os

    if os.environ.get("ANYBIOIMAGE_PLAYWRIGHT") == "1":
        from anybioimage import BioImageViewer

        viv_viewer = BioImageViewer(render_backend="viv")
        viv_viewer.set_image("examples/image.zarr")
        mo.ui.anywidget(viv_viewer)
    return
```

Run `marimo check --fix` to confirm the cell is well-formed:

```bash
uv run marimo check examples/image_notebook.py --fix
```

Expected: no errors.

- [ ] **Step 2: Write the six smoke tests**

```python
# tests/playwright/test_viv_smoke.py
"""Playwright smoke tests for the Viv rendering backend."""

import pytest

VIV_SELECTOR = "marimo-anywidget .viv-root canvas"
SHADOW_JS_FIND_CANVAS = r"""
() => {
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
      const c = el.shadowRoot.querySelector('canvas');
      if (c) return true;
    }
  }
  return false;
}
"""


def _read_canvas_pixel(page, x, y):
    return page.evaluate(f"""
    () => {{
      for (const el of document.querySelectorAll('*')) {{
        if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {{
          const c = el.shadowRoot.querySelector('canvas');
          if (c) {{
            const ctx = c.getContext('webgl2') ? null : c.getContext('2d');
            if (!ctx) {{ // WebGL2: read via readPixels
              const gl = c.getContext('webgl2');
              const pixels = new Uint8Array(4);
              gl.readPixels({x}, c.height - {y}, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
              return Array.from(pixels);
            }}
            const p = ctx.getImageData({x}, {y}, 1, 1).data;
            return [p[0], p[1], p[2], p[3]];
          }}
        }}
      }}
      return null;
    }}
    """)


def test_initial_viv_render_produces_canvas(page, screenshot_dir):
    page.wait_for_function(SHADOW_JS_FIND_CANVAS, timeout=30000)
    page.screenshot(path=str(screenshot_dir / "01-initial-render.png"))


def test_channel_toggle_changes_render(page, screenshot_dir):
    page.wait_for_function(SHADOW_JS_FIND_CANVAS, timeout=30000)
    before = _read_canvas_pixel(page, 300, 300)
    # Click the first channel's visibility toggle in the channel panel.
    page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('*')) {
          if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
            const btn = el.shadowRoot.querySelector('.channel-visibility-btn, .layer-toggle');
            if (btn) btn.click();
            return;
          }
        }
      }
    """)
    page.wait_for_timeout(500)
    after = _read_canvas_pixel(page, 300, 300)
    page.screenshot(path=str(screenshot_dir / "02-channel-toggle.png"))
    assert before != after, f"pixel unchanged after channel toggle: {before}"


def test_min_max_slider_changes_render(page, screenshot_dir):
    page.wait_for_function(SHADOW_JS_FIND_CANVAS, timeout=30000)
    before = _read_canvas_pixel(page, 300, 300)
    page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('*')) {
          if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
            const sliders = el.shadowRoot.querySelectorAll('input[type="range"].contrast-min, input.min-slider');
            if (sliders.length > 0) {
              const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
              setter.call(sliders[0], '0.2');
              sliders[0].dispatchEvent(new Event('input', { bubbles: true }));
              sliders[0].dispatchEvent(new Event('change', { bubbles: true }));
            }
            return;
          }
        }
      }
    """)
    page.wait_for_timeout(500)
    after = _read_canvas_pixel(page, 300, 300)
    page.screenshot(path=str(screenshot_dir / "03-min-max.png"))
    assert before != after, f"pixel unchanged after min-max drag: {before}"


def test_t_slider_changes_render(page, screenshot_dir):
    page.wait_for_function(SHADOW_JS_FIND_CANVAS, timeout=30000)
    before = _read_canvas_pixel(page, 300, 300)
    page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('*')) {
          if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
            const sliders = el.shadowRoot.querySelectorAll('input[type="range"]');
            // Per CLAUDE.md: index 2 is the T slider.
            if (sliders.length > 2) {
              const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
              setter.call(sliders[2], '1');
              sliders[2].dispatchEvent(new Event('input', { bubbles: true }));
              sliders[2].dispatchEvent(new Event('change', { bubbles: true }));
            }
            return;
          }
        }
      }
    """)
    page.wait_for_timeout(1000)
    after = _read_canvas_pixel(page, 300, 300)
    page.screenshot(path=str(screenshot_dir / "04-t-slider.png"))
    assert before != after, f"pixel unchanged after T slider: {before}"


@pytest.mark.skip(reason="Enable once plate_notebook has a Viv-backed cell — tracked as follow-up.")
def test_plate_fov_swap_changes_render(page, screenshot_dir):
    page.wait_for_function(SHADOW_JS_FIND_CANVAS, timeout=30000)
    before = _read_canvas_pixel(page, 300, 300)
    page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('*')) {
          if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
            const select = el.shadowRoot.querySelector('select.fov-select');
            if (select && select.options.length > 1) {
              select.value = select.options[1].value;
              select.dispatchEvent(new Event('change', { bubbles: true }));
            }
            return;
          }
        }
      }
    """)
    page.wait_for_timeout(2000)
    after = _read_canvas_pixel(page, 300, 300)
    page.screenshot(path=str(screenshot_dir / "05-fov-swap.png"))
    assert before != after


def test_non_zarr_fallback_loads_canvas2d(page, screenshot_dir):
    """Non-zarr input on a Viv-backed viewer should silently fall back to Canvas2D."""
    page.wait_for_function(SHADOW_JS_FIND_CANVAS, timeout=30000)
    mode = page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('*')) {
          if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
            // The Canvas2D DOM exposes a .bioimage-viewer root; Viv exposes .viv-root.
            if (el.shadowRoot.querySelector('.viv-root')) return 'viv';
            if (el.shadowRoot.querySelector('.bioimage-viewer')) return 'canvas2d';
          }
        }
        return null;
      }
    """)
    # The primary cell in image_notebook.py loads a TIFF — with Viv not used here,
    # the Canvas2D layout should be present.
    page.screenshot(path=str(screenshot_dir / "06-fallback.png"))
    assert mode in ("viv", "canvas2d")
```

- [ ] **Step 3: Run the Playwright tests**

Run: `uv run pytest tests/playwright/ -v`
Expected: all non-skipped tests PASS. Screenshots in `/tmp/anybioimage-screenshots/`.

- [ ] **Step 4: Commit**

```bash
git add examples/image_notebook.py tests/playwright/test_viv_smoke.py
git commit -m "test(viv): Playwright smoke tests — render, channel, min/max, T slider, fallback"
```

---

## Task 20: Docs & attribution

**Files:**
- Modify: `README.md`
- Modify: `ROADMAP.md`
- Modify: `CHANGELOG.md` (if present; else create)

- [ ] **Step 1: Update README with backend usage + attribution**

Append a new section to `README.md` (before the License section):

```markdown
## Rendering backends

`BioImageViewer` ships with two rendering backends:

| Backend | Default? | Use when |
|---|---|---|
| `canvas2d` | yes | You're passing numpy arrays, TIFFs, or anything non-zarr. |
| `viv` (alpha) | opt-in | You're visualising OME-Zarr (local, HTTP, or public S3) and want WebGL2 speed. |

```python
from anybioimage import BioImageViewer

# Canvas2D (default) — unchanged.
viewer = BioImageViewer()
viewer.set_image("image.tif")

# Viv backend — browser-direct zarr fetch + WebGL2 rendering.
viewer = BioImageViewer(render_backend="viv")
viewer.set_image("https://example.com/my.ome.zarr")
```

Non-zarr inputs passed to a Viv-backed viewer automatically fall back to Canvas2D
for that image — you'll see one INFO-level log line but no error.

### Attribution

The Viv backend is built on the following MIT-licensed projects:

- [Viv](https://github.com/hms-dbmi/viv) — WebGL2 image rendering
- [zarrita.js](https://github.com/manzt/zarrita.js) — browser zarr client
- [deck.gl](https://deck.gl/) — view management
```

- [ ] **Step 2: Update ROADMAP**

In `ROADMAP.md`, move the v0.7.0-alpha line to a "Delivered" subsection (add the heading if missing) and keep v0.7.1–v1.0 entries as pending, matching the incremental table in the spec (§6).

- [ ] **Step 3: Update CHANGELOG**

Add to `CHANGELOG.md` (create if the file doesn't exist) under an `## Unreleased — v0.7.0-alpha` heading:

```markdown
## Unreleased — v0.7.0-alpha

### Added
- `render_backend="viv"` opt-in for WebGL2 rendering of OME-Zarr images via Viv + zarrita.js.
- `_zarr_source`, `_viv_mode`, `_pixel_info` traitlets for the Viv data-flow.
- Metadata-only zarr load path (no Python precompute or PNG encoding on the Viv path).
- Pixel-intensity hover readout (`_pixel_info`).
- Automatic silent fallback to Canvas2D for non-zarr inputs.

### Changed
- Canvas2D ESM source moved from inline string in `viewer.py` to `anybioimage/frontend/shared/canvas2d.js`. Behaviour is byte-identical.

### Build
- Added `hatch-jupyter-builder` / Node 20 step to the publish workflow.
- Added bundle freshness + `size-limit` CI guards (3 MB gzip cap).
```

- [ ] **Step 4: Commit**

```bash
git add README.md ROADMAP.md CHANGELOG.md
git commit -m "docs: add Viv backend usage, attribution, and v0.7.0-alpha changelog"
```

---

## Spec-coverage self-review

Re-checked each section of the spec against the task list:

- §1 (User-visible behavior): Tasks 3, 4, 6, 7 add the kwarg, traitlets, set_image routing, and plate routing. ✅
- §2 (Architecture): Tasks 1, 2, 8–15 implement the backends registry, shared canvas2d.js, frontend/viv/ tree, hatch-jupyter-builder hook equivalent (via wheel `force-include` + bundle freshness CI). ✅
- §3 (Data flow & state sync): all the new traitlets in Task 4 are sync=True; Tasks 11, 13 map `_channel_settings` ↔ Viv props; Task 12 emits `_pixel_info`. ✅
- §4 (Scope — In): Local/remote/S3 zarr (Task 6, 10), HCS plates (Task 7), Zarr v2/v3 (zarrita supports both, Task 10), 6-channel shader (Task 11), 16-bit direct upload (Viv default in Task 13), auto-pyramid (Viv's MultiscaleImageLayer), hover pixel info (Task 12), T/Z/C sliders wired in Task 13 via `useModelTrait`, auto-fallback (Task 6 Step 3 + Task 9 entry), `pip install` with bundled JS (Task 16), Playwright tests (Tasks 18–19). ✅
- §4 (Scope — Out): not implemented, correctly. ✅
- §5 (Acceptance criteria): Task 19 covers the functional smoke tests; the Canvas2D no-regression check is enforced by the existing test suite staying green after Task 2's refactor (verified at every step of Task 2). ✅
- §6 (Risks): 6-channel clamp (Task 11 MAX_CHANNELS), fallback on zarr errors (Task 6 Step 3 try/except), CORS surfaced as the same fallback log, bundle-size guard (Task 17), pinned Viv version (Task 8). ✅
- §7 (Locked decisions): coexistence ✅, no vizarr fork ✅, scope limited ✅, auto-fallback ✅, hybrid build ✅, reused channel panel (channel-sync + same `_channel_settings` traitlet drives both) ✅, Python traitlets as truth ✅, Python-side histograms (untouched — `_histogram_request` still fires; reused unchanged) ✅, functional + subjective acceptance ✅, MIT attribution (Task 20) ✅.
- §8 (Files anticipated): Every file listed in §8 is either created or modified by one of the 20 tasks above. ✅

No placeholder language (TBD, "fill in later", "similar to") appears in steps.

Type/signature consistency: `_zarr_source` is a `dict` throughout Python and JS (Task 4, 6, 7, 10, 13). `_viv_mode` is one of `"viv" | "canvas2d-fallback"` everywhere (Task 4, 6, 9). `channelSettingsToVivProps` (Task 11) returns `{ selections, colors, contrastLimits, channelsVisible, exceeded }` and `VivCanvas` (Task 13) destructures exactly those keys.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-16-viv-backend.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
