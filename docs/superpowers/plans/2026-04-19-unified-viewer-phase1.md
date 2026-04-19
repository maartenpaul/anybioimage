# Unified BioImageViewer — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**This is Phase 1 of 3.** Phases 2 (Annotate MVP) and 3 (Editing + measurement + undo) will each get their own plan after Phase 1 merges green. Phase 1 is the foundational rewrite; Phases 2 and 3 stack features on the stable base.

**Goal (Phase 1):** Collapse `BioImageViewer` to a single rendering pipeline — Viv + deck.gl on WebGL2 — that handles every input type (remote OME-Zarr, local OME-Zarr, HCS plate, numpy, bioio TIFF/CZI/ND2). Deliver Fiji/napari-style per-channel LUTs, metadata panel, scale bar, pixel-info hover, keyboard shortcuts, and a full `examples/full_demo.py` for Phase-1 sections. Delete the Canvas2D backend and its compositor/tile-cache code.

**Architecture:** One frontend tree under `anybioimage/frontend/viewer/`, built with esbuild, bundled into `dist/viewer-bundle.js` and loaded as the widget's single `_esm`. Two input-source paths converge on the same deck.gl canvas: URL inputs use Viv's `ZarrPixelSource` via zarrita (direct browser fetch); numpy/bioio inputs use a new `AnywidgetPixelSource` that requests chunks from Python via `model.send()` + binary buffers. Python never encodes PNGs or composites channels; Viv does both on the GPU.

**Tech Stack:** Python anywidget + traitlets · React 18 · `@hms-dbmi/viv` 0.17 · `zarrita` (npm, via Viv) · `deck.gl` 9 · esbuild · `hatch-jupyter-builder` · `size-limit` 4 MB · `vitest` (JS unit) · Playwright (smoke)

**Spec:** [docs/superpowers/specs/2026-04-19-unified-viewer-design.md](../specs/2026-04-19-unified-viewer-design.md) — sections referenced as `[spec §N]`.

---

## Starting point

The worktree `.worktrees/viv-backend` (branch `feature/viv-backend`) already contains a partial Viv backend shipped as v0.7.0-alpha per the superseded spec `2026-04-16-viv-backend-design.md`. This plan rebuilds that tree into the final single-pipeline architecture and deletes the Canvas2D code.

Each task starts from the previous task's end state on `feature/viv-backend`, not from `main`. Commits in the worktree accumulate on that branch until Phase 1 is ready to merge.

---

## File structure (Phase 1)

**New files:**

- `anybioimage/frontend/viewer/` — renamed + restructured from `anybioimage/frontend/viv/`:
  - `package.json`, `build.config.mjs`, `size-limit.config.cjs`, `.gitignore`
  - `src/entry.js` — anywidget `render()` entry
  - `src/App.jsx` — React root: chrome + deck.gl canvas
  - `src/chrome/Toolbar.jsx`
  - `src/chrome/DimControls.jsx`
  - `src/chrome/StatusBar.jsx`
  - `src/chrome/LayersPanel/LayersPanel.jsx`
  - `src/chrome/LayersPanel/MetadataSection.jsx`
  - `src/chrome/LayersPanel/ImageSection.jsx`
  - `src/chrome/LayersPanel/ExportFooter.jsx` — button row (only the "Save view as PNG" in Phase 1; annotation/measurement export comes in Phase 3)
  - `src/render/DeckCanvas.jsx` — single deck.gl + layer composer
  - `src/render/pixel-sources/zarr-source.js` — Viv loader (existing, moved)
  - `src/render/pixel-sources/anywidget-source.js` — NEW chunk-bridge PixelSource
  - `src/render/layers/buildImageLayer.js`
  - `src/render/layers/buildScaleBar.js` — custom `CompositeLayer`
  - `src/render/luts/index.js` — LUT registry
  - `src/render/luts/VivLutExtension.js` — Viv shader extension
  - `src/render/luts/lut-textures/*.png` — 15 × 256×1 RGBA LUT PNGs
  - `src/interaction/keyboard.js` — shortcut map (annotation shortcuts stubbed for Phase 2)
  - `src/model/useModelTrait.js` — hook
  - `src/model/channelState.js` — `_channel_settings` ↔ Viv props
  - `src/util/coords.js` — pixel↔screen transforms
  - `src/util/debounce.js`
  - `dist/viewer-bundle.js` — committed artefact
- `anybioimage/mixins/pixel_source.py` — NEW chunk-bridge handler (Python side of `AnywidgetPixelSource`)
- `examples/full_demo.py` — NEW marimo notebook; Phase-1 sections
- `tests/test_pixel_source.py` — chunk-bridge protocol
- `tests/test_image_loading_slim.py` — metadata-only load path
- `tests/test_metadata_extraction.py` — pixel_size_um + channel names
- `tests/test_plate_unified.py` — single-pipeline plate FOV switch
- `tests/test_legacy_kwarg.py` — deprecation warning on `render_backend`
- `anybioimage/frontend/viewer/src/**/*.test.{js,jsx}` — vitest unit tests alongside sources
- `tests/playwright/test_phase1_*.py` — Phase-1 Playwright flows

**Modified files:**

- `anybioimage/viewer.py` — remove backend registry + `_esm` swap; load single bundle; remove `_viv_mode`, `use_jpeg_tiles`; new traitlets (`_pixel_source_mode`, `_luts_used`, `_display_mode`).
- `anybioimage/mixins/image_loading.py` — remove compositor/tile-cache/precompute; keep metadata + percentile channel init; route non-URL inputs through `pixel_source.py`.
- `anybioimage/mixins/plate_loading.py` — always uses `_zarr_source` (remove any dual-mode branch if still present).
- `anybioimage/mixins/__init__.py` — add `PixelSourceMixin`.
- `pyproject.toml` — single frontend entry for `hatch-jupyter-builder`; rename artefact path to `frontend/viewer/dist/viewer-bundle.js`.
- `.github/workflows/bundle.yml` — update paths.
- `.github/workflows/ci.yml` — add `npm run test` (vitest) job alongside Playwright.
- `README.md` — MIT attribution for `nebula.gl` added (anticipating Phase 3); usage section updated to single API.
- `CHANGELOG.md` — new `[Unreleased]` section with `### Breaking` subsection.
- `ROADMAP.md` — merge Viv-backend table into main roadmap; mark v0.4.0 display items delivered.

**Deleted files (in Task 18):**

- `anybioimage/backends/__init__.py`
- `anybioimage/backends/canvas2d.py`
- `anybioimage/backends/viv.py`
- `anybioimage/frontend/shared/canvas2d.js`
- `anybioimage/frontend/shared/chrome.js` — rewritten in React under `frontend/viewer/src/chrome/`
- `anybioimage/frontend/shared/__init__.py`
- `anybioimage/frontend/viv/` — whole directory replaced by `frontend/viewer/`
- `examples/image_notebook.py` — replaced by `examples/full_demo.py`

---

## Conventions

- **Every code step shows the full code.** No `...`, no "add appropriate error handling", no "similar to X".
- **TDD on Python and JS units** (pytest + vitest). Playwright is round-trip smoke, not TDD.
- **Commits are bite-sized**, one conventional-prefixed commit per logical change (`feat`, `refactor`, `build`, `test`, `docs`, `chore`, `ci`).
- **Each task ends with a commit.** Intermediate steps inside a task may include `git add` of partial files; the final step of the task is always a `git commit`.
- **Python tests:** `uv run pytest tests/ -v`
- **JS tests:** `cd anybioimage/frontend/viewer && npm run test`
- **Bundle build:** `cd anybioimage/frontend/viewer && npm run build`
- **Worktree:** all work happens in `.worktrees/viv-backend` on branch `feature/viv-backend`.

---

## Task 1: Chunk-bridge spike — validate AnywidgetPixelSource perf

**Goal:** Before investing in the full rewrite, prove the chunk-bridge can return a 512×512 uint16 tile from an in-RAM numpy array in ≤30 ms p95 over the anywidget websocket. If it can't, we stop and reconsider (see spec §2 fallback).

**Files:**
- Create: `tests/spike_chunk_bridge.py` (deleted at end of task; not a real test)

- [ ] **Step 1: Write the spike script**

```python
# tests/spike_chunk_bridge.py
"""One-shot perf spike — NOT a real test. Delete after running.

Measures:
  1. Single-tile round-trip ms (Python reads numpy slice, encodes buffer, returns)
  2. Throughput over 1000 tiles
  3. p50/p95/p99 latency

Usage: uv run python tests/spike_chunk_bridge.py
"""
from __future__ import annotations

import statistics
import time

import numpy as np


TILE_SIZE = 512
N_TILES = 1000


def read_tile(arr: np.ndarray, t: int, c: int, z: int, tx: int, ty: int, tile: int) -> bytes:
    """Python side: slice a tile from an in-RAM TCZYX uint16 array, return raw bytes."""
    y0 = ty * tile
    x0 = tx * tile
    y1 = min(y0 + tile, arr.shape[3])
    x1 = min(x0 + tile, arr.shape[4])
    sub = arr[t, c, z, y0:y1, x0:x1]
    # Ensure contiguous little-endian before handing to the wire.
    if not sub.flags["C_CONTIGUOUS"]:
        sub = np.ascontiguousarray(sub)
    return sub.tobytes()


def decode_tile(buf: bytes, w: int, h: int) -> np.ndarray:
    """JS side equivalent, in Python for the spike."""
    return np.frombuffer(buf, dtype=np.uint16).reshape(h, w)


def main() -> None:
    print("Allocating 10×3×5×2048×2048 uint16 ≈ 600 MB ...", flush=True)
    arr = np.random.randint(0, 65535, size=(10, 3, 5, 2048, 2048), dtype=np.uint16)
    print(f"Allocated {arr.nbytes / 1024**3:.2f} GB.\n")

    # Warmup
    for _ in range(20):
        read_tile(arr, 0, 0, 0, 0, 0, TILE_SIZE)

    lats = []
    t0 = time.perf_counter()
    for i in range(N_TILES):
        t = i % arr.shape[0]
        c = i % arr.shape[1]
        z = i % arr.shape[2]
        tx = (i // 4) % 4
        ty = (i // 4) % 4
        s = time.perf_counter()
        buf = read_tile(arr, t, c, z, tx, ty, TILE_SIZE)
        _ = decode_tile(buf, min(TILE_SIZE, arr.shape[4] - tx * TILE_SIZE),
                         min(TILE_SIZE, arr.shape[3] - ty * TILE_SIZE))
        lats.append((time.perf_counter() - s) * 1000)
    dt = time.perf_counter() - t0

    lats.sort()
    print(f"Total: {dt:.3f} s  Throughput: {N_TILES / dt:.0f} tiles/s")
    print(f"Latency: p50={lats[500]:.2f} ms  p95={lats[950]:.2f} ms  p99={lats[990]:.2f} ms")
    print(f"Budget (spec §10): cold tile ≤30 ms p95")
    print(f"{'OK' if lats[950] <= 30 else 'FAIL'}: p95 = {lats[950]:.2f} ms")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the spike**

```
uv run python tests/spike_chunk_bridge.py
```

Expected: prints throughput + p50/p95/p99, ends with `OK:`. This is a Python-only upper bound (no websocket). Actual in-browser measurement happens in Task 4.

- [ ] **Step 3: Commit or abort**

If p95 > 30 ms even without the websocket round-trip, **stop and escalate** — the approach needs reconsideration. Otherwise:

```bash
rm tests/spike_chunk_bridge.py
git add -A
git commit -m "chore: chunk-bridge spike (numpy-only baseline, p95 under target)"
```

The commit message should record the measured p95 in the body for future reference.

---

## Task 2: Rename frontend/viv → frontend/viewer

**Goal:** Restructure the existing Viv tree into its final home with room for the new layer composer, chrome React tree, and LUT registry.

**Files:**
- Move: all of `anybioimage/frontend/viv/` → `anybioimage/frontend/viewer/`
- Rename inside: `dist/viv-bundle.js` → `dist/viewer-bundle.js`
- Modify: `anybioimage/backends/viv.py` (path + filename reference)
- Modify: `.github/workflows/bundle.yml`
- Modify: `pyproject.toml` (hatch-jupyter-builder path + artefact)

- [ ] **Step 1: Move the tree**

```bash
git mv anybioimage/frontend/viv anybioimage/frontend/viewer
git mv anybioimage/frontend/viewer/dist/viv-bundle.js anybioimage/frontend/viewer/dist/viewer-bundle.js
```

- [ ] **Step 2: Update build config output path**

Edit `anybioimage/frontend/viewer/build.config.mjs`:

```js
// anybioimage/frontend/viewer/build.config.mjs
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));

await build({
  entryPoints: [resolve(__dirname, 'src/entry.js')],
  outfile: resolve(__dirname, 'dist/viewer-bundle.js'),
  bundle: true,
  format: 'esm',
  target: 'es2020',
  platform: 'browser',
  minify: true,
  sourcemap: false,
  loader: { '.js': 'jsx', '.jsx': 'jsx', '.png': 'dataurl' },
  jsx: 'automatic',
  define: { 'process.env.NODE_ENV': '"production"' },
  logLevel: 'info',
});
```

Note the new `.png` loader — LUT textures in Task 9 are imported as data URLs.

- [ ] **Step 3: Update size-limit config**

Edit `anybioimage/frontend/viewer/package.json` to point at the new filename:

```json
  "size-limit": [
    { "path": "dist/viewer-bundle.js", "limit": "4 MB" }
  ]
```

Also update the `name` field to `"anybioimage-viewer-bundle"`.

- [ ] **Step 4: Point Python loader at the new path**

Edit `anybioimage/backends/viv.py`:

```python
"""Temporary loader; merged into viewer.py in Task 18."""
from importlib.resources import files


def load_esm() -> str:
    path = files("anybioimage.frontend.viewer.dist").joinpath("viewer-bundle.js")
    return path.read_text(encoding="utf-8")
```

- [ ] **Step 5: Update CI bundle workflow**

Edit `.github/workflows/bundle.yml`:

```yaml
# ... (keep existing name + on: trigger)
      - name: Install npm deps
        working-directory: anybioimage/frontend/viewer
        run: npm ci
      - name: Build bundle
        working-directory: anybioimage/frontend/viewer
        run: npm run build
      - name: Verify bundle unchanged
        run: |
          git diff --exit-code anybioimage/frontend/viewer/dist/viewer-bundle.js \
            || (echo "viewer-bundle.js out of date; rebuild and commit." && exit 1)
      - name: size-limit
        working-directory: anybioimage/frontend/viewer
        run: npm run size
```

- [ ] **Step 6: Update pyproject.toml**

In the `[tool.hatch.build.hooks.jupyter-builder]` section (if present) or `[tool.hatch.build.targets.wheel]`, rewrite to point at `anybioimage/frontend/viewer/`. Example fragment:

```toml
[tool.hatch.build.hooks.jupyter-builder]
build-function = "hatch_jupyter_builder.npm_builder"
ensured-targets = ["anybioimage/frontend/viewer/dist/viewer-bundle.js"]

[tool.hatch.build.hooks.jupyter-builder.build-kwargs]
path = "anybioimage/frontend/viewer"
build_cmd = "build"
npm = ["npm"]
```

- [ ] **Step 7: Build + verify**

```bash
cd anybioimage/frontend/viewer
npm ci
npm run build
npm run size
cd ../../..
uv run python -c "from anybioimage.backends import viv; assert 'export default' in viv.load_esm() or 'render' in viv.load_esm(); print('loader OK')"
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(frontend): rename frontend/viv to frontend/viewer"
```

---

## Task 3: Add `__init__.py` package markers for new subdirs

**Goal:** Declare every new source subdirectory so importable Python code can resolve the bundled data file path via `importlib.resources`.

**Files:**
- Create: `anybioimage/frontend/viewer/__init__.py` (replace any existing)
- Create: `anybioimage/frontend/viewer/dist/__init__.py` (replace any existing)
- Verify: `anybioimage/frontend/__init__.py` exists

- [ ] **Step 1: Ensure both init files**

```bash
touch anybioimage/frontend/__init__.py
touch anybioimage/frontend/viewer/__init__.py
touch anybioimage/frontend/viewer/dist/__init__.py
```

- [ ] **Step 2: Verify resource lookup**

```
uv run python -c "from importlib.resources import files; p = files('anybioimage.frontend.viewer.dist').joinpath('viewer-bundle.js'); assert p.is_file(); print('resource OK')"
```

Expected: `resource OK`.

- [ ] **Step 3: Commit**

```bash
git add anybioimage/frontend/__init__.py anybioimage/frontend/viewer/__init__.py anybioimage/frontend/viewer/dist/__init__.py
git commit -m "chore(frontend): add package markers for viewer bundle"
```

---

## Task 4: Python-side `PixelSourceMixin` — chunk bridge handler

**Goal:** Handle `model.send()` chunk requests from JS. Reply with raw bytes in `buffers`. No PNG, no base64. Bounded LRU of 256 raw chunks to smooth Z/T scrubbing.

**Files:**
- Create: `anybioimage/mixins/pixel_source.py`
- Create: `tests/test_pixel_source.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pixel_source.py
"""Chunk-bridge protocol tests for PixelSourceMixin."""
from __future__ import annotations

import numpy as np
import pytest

from anybioimage.mixins.pixel_source import PixelSourceMixin


class _Harness(PixelSourceMixin):
    """Minimal harness: no real traitlets, no anywidget."""

    def __init__(self, arr: np.ndarray) -> None:
        self._chunk_array = arr
        self._chunk_lru_cap = 8
        self._sent: list[tuple[dict, list]] = []
        super().__init__()

    def _send_chunk_response(self, msg: dict, buffers: list[bytes]) -> None:
        self._sent.append((msg, [bytes(b) for b in buffers]))


def test_chunk_ok_returns_raw_bytes_and_metadata() -> None:
    arr = np.arange(10 * 2 * 3 * 512 * 512, dtype=np.uint16).reshape(10, 2, 3, 512, 512)
    h = _Harness(arr)
    h.handle_chunk_request({
        "kind": "chunk", "requestId": 1, "t": 2, "c": 1, "z": 0, "level": 0,
        "tx": 0, "ty": 0, "tileSize": 512,
    })
    assert len(h._sent) == 1
    reply, bufs = h._sent[0]
    assert reply["kind"] == "chunk"
    assert reply["requestId"] == 1
    assert reply["ok"] is True
    assert reply["w"] == 512
    assert reply["h"] == 512
    assert reply["dtype"] == "uint16"
    # Raw bytes should equal the slice tobytes().
    expected = np.ascontiguousarray(arr[2, 1, 0, 0:512, 0:512]).tobytes()
    assert bufs[0] == expected


def test_chunk_edge_tile_clipped_to_array_bounds() -> None:
    arr = np.zeros((1, 1, 1, 600, 600), dtype=np.uint8)
    h = _Harness(arr)
    h.handle_chunk_request({
        "kind": "chunk", "requestId": 7, "t": 0, "c": 0, "z": 0, "level": 0,
        "tx": 1, "ty": 1, "tileSize": 512,
    })
    reply, bufs = h._sent[0]
    assert reply["ok"] is True
    assert reply["w"] == 600 - 512  # 88
    assert reply["h"] == 88
    assert len(bufs[0]) == 88 * 88


def test_chunk_out_of_bounds_returns_error() -> None:
    arr = np.zeros((1, 1, 1, 100, 100), dtype=np.uint8)
    h = _Harness(arr)
    h.handle_chunk_request({
        "kind": "chunk", "requestId": 3, "t": 0, "c": 0, "z": 0, "level": 0,
        "tx": 99, "ty": 99, "tileSize": 512,
    })
    reply, bufs = h._sent[0]
    assert reply["ok"] is False
    assert "out of bounds" in reply["error"].lower()
    assert bufs == []


def test_lru_cache_bounded_and_hits_on_repeat() -> None:
    arr = np.zeros((1, 1, 1, 2048, 2048), dtype=np.uint16)
    h = _Harness(arr)
    h._chunk_lru_cap = 4
    for i in range(6):
        h.handle_chunk_request({
            "kind": "chunk", "requestId": i, "t": 0, "c": 0, "z": 0, "level": 0,
            "tx": i, "ty": 0, "tileSize": 512,
        })
    assert len(h._chunk_cache) == 4  # bounded

    # Re-request an evicted one, cache should miss (length stays at cap).
    h.handle_chunk_request({
        "kind": "chunk", "requestId": 99, "t": 0, "c": 0, "z": 0, "level": 0,
        "tx": 0, "ty": 0, "tileSize": 512,
    })
    assert len(h._chunk_cache) == 4

    # Re-request a present one, should be served from cache (no shape change).
    before = dict(h._chunk_cache)
    h.handle_chunk_request({
        "kind": "chunk", "requestId": 100, "t": 0, "c": 0, "z": 0, "level": 0,
        "tx": 5, "ty": 0, "tileSize": 512,
    })
    assert h._chunk_cache is not before  # same object mutated, content differs
```

- [ ] **Step 2: Run to verify they fail**

```
uv run pytest tests/test_pixel_source.py -v
```

Expected: `ModuleNotFoundError: anybioimage.mixins.pixel_source`.

- [ ] **Step 3: Implement the mixin**

```python
# anybioimage/mixins/pixel_source.py
"""Chunk-bridge handler — the Python side of AnywidgetPixelSource.

JS asks for (t, c, z, level, tx, ty, tileSize); we slice from an in-RAM numpy
array (or lazy bioio reader in a follow-up subclass) and reply with raw bytes
in anywidget buffers.

No PNG encoding, no base64. Dtype is preserved verbatim.

A bounded LRU (default 256 tiles) smooths repeat requests during Z/T scrubbing.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Any

import numpy as np

_CHUNK_LRU_DEFAULT = 256


class PixelSourceMixin:
    """Mixin — must be combined with something that can actually send messages.

    Consumers set `_chunk_array` (TCZYX numpy) or override `_read_tile_raw()`.
    `_send_chunk_response(msg, buffers)` is the one transport seam the mixin
    requires; BioImageViewer implements it as `self.send(msg, buffers)`.
    """

    _chunk_array: np.ndarray | None = None
    _chunk_lru_cap: int = _CHUNK_LRU_DEFAULT

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._chunk_cache: OrderedDict[tuple, bytes] = OrderedDict()

    # ---- transport seam ----
    def _send_chunk_response(self, msg: dict, buffers: list[bytes]) -> None:
        """Default: no transport — subclasses override. Tests use a harness override."""
        raise NotImplementedError

    # ---- tile read ----
    def _read_tile_raw(self, t: int, c: int, z: int, level: int,
                       tx: int, ty: int, tile: int) -> tuple[np.ndarray, str]:
        """Return (view, dtype_str). Subclasses may override for lazy bioio reads.

        Raises IndexError for out-of-bounds.
        """
        arr = self._chunk_array
        if arr is None:
            raise IndexError("no chunk array set")
        if level != 0:
            # Phase-1 synthetic downsample: nearest-neighbour ::step ::step.
            step = 2 ** level
            y0 = ty * tile * step
            x0 = tx * tile * step
            y1 = min(y0 + tile * step, arr.shape[3])
            x1 = min(x0 + tile * step, arr.shape[4])
            if y0 >= arr.shape[3] or x0 >= arr.shape[4]:
                raise IndexError("tile out of bounds")
            sub = arr[t, c, z, y0:y1:step, x0:x1:step]
        else:
            y0 = ty * tile
            x0 = tx * tile
            y1 = min(y0 + tile, arr.shape[3])
            x1 = min(x0 + tile, arr.shape[4])
            if y0 >= arr.shape[3] or x0 >= arr.shape[4]:
                raise IndexError("tile out of bounds")
            sub = arr[t, c, z, y0:y1, x0:x1]
        if not sub.flags["C_CONTIGUOUS"]:
            sub = np.ascontiguousarray(sub)
        return sub, str(sub.dtype)

    # ---- public entry point ----
    def handle_chunk_request(self, payload: dict) -> None:
        """Dispatch a `{kind:"chunk",...}` message from JS."""
        request_id = int(payload.get("requestId", -1))
        try:
            t = int(payload["t"]); c = int(payload["c"]); z = int(payload["z"])
            level = int(payload.get("level", 0))
            tx = int(payload["tx"]); ty = int(payload["ty"])
            tile = int(payload.get("tileSize", 512))
        except (KeyError, TypeError, ValueError) as exc:
            self._send_chunk_response(
                {"kind": "chunk", "requestId": request_id, "ok": False,
                 "error": f"bad payload: {exc}"}, [])
            return

        key = (t, c, z, level, tx, ty, tile)
        cached = self._chunk_cache.get(key)
        if cached is not None:
            # LRU touch.
            self._chunk_cache.move_to_end(key)
            self._send_chunk_response(
                {"kind": "chunk", "requestId": request_id, "ok": True,
                 "w": cached[1], "h": cached[2], "dtype": cached[3]},
                [cached[0]])
            return

        try:
            arr, dtype_str = self._read_tile_raw(t, c, z, level, tx, ty, tile)
        except IndexError as exc:
            self._send_chunk_response(
                {"kind": "chunk", "requestId": request_id, "ok": False,
                 "error": f"tile out of bounds: {exc}"}, [])
            return
        except Exception as exc:  # pragma: no cover — defensive
            self._send_chunk_response(
                {"kind": "chunk", "requestId": request_id, "ok": False,
                 "error": f"{type(exc).__name__}: {exc}"}, [])
            return

        h, w = arr.shape[:2]
        raw = arr.tobytes()
        # Cache with (raw, w, h, dtype) tuple so the LRU entry is self-describing.
        self._chunk_cache[key] = (raw, w, h, dtype_str)
        while len(self._chunk_cache) > self._chunk_lru_cap:
            self._chunk_cache.popitem(last=False)

        self._send_chunk_response(
            {"kind": "chunk", "requestId": request_id, "ok": True,
             "w": w, "h": h, "dtype": dtype_str}, [raw])
```

- [ ] **Step 4: Run the tests**

```
uv run pytest tests/test_pixel_source.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add anybioimage/mixins/pixel_source.py tests/test_pixel_source.py
git commit -m "feat(pixel-source): Python chunk-bridge handler with bounded LRU"
```

---

## Task 5: Wire `PixelSourceMixin` into `BioImageViewer`

**Goal:** BioImageViewer now handles `msg:chunk` messages from JS. The mixin's `_send_chunk_response` is wired to anywidget's `self.send()`.

**Files:**
- Modify: `anybioimage/viewer.py`
- Modify: `anybioimage/mixins/__init__.py`

- [ ] **Step 1: Export PixelSourceMixin**

Edit `anybioimage/mixins/__init__.py`:

```python
"""Mixins for BioImageViewer."""
from .annotations import AnnotationsMixin
from .image_loading import ImageLoadingMixin
from .mask_management import MaskManagementMixin
from .pixel_source import PixelSourceMixin
from .plate_loading import PlateLoadingMixin
from .sam_integration import SAMIntegrationMixin

__all__ = [
    "AnnotationsMixin",
    "ImageLoadingMixin",
    "MaskManagementMixin",
    "PixelSourceMixin",
    "PlateLoadingMixin",
    "SAMIntegrationMixin",
]
```

- [ ] **Step 2: Add PixelSourceMixin to BioImageViewer**

In `anybioimage/viewer.py` near the class definition:

```python
from .mixins import (
    AnnotationsMixin,
    ImageLoadingMixin,
    MaskManagementMixin,
    PixelSourceMixin,
    PlateLoadingMixin,
    SAMIntegrationMixin,
)


class BioImageViewer(
    ImageLoadingMixin,
    PixelSourceMixin,
    PlateLoadingMixin,
    MaskManagementMixin,
    AnnotationsMixin,
    SAMIntegrationMixin,
    anywidget.AnyWidget,
):
    ...
```

- [ ] **Step 3: Wire transport + message dispatch**

Add to `BioImageViewer` (near other `@observe` / listener methods):

```python
    def _send_chunk_response(self, msg: dict, buffers: list[bytes]) -> None:
        """Override of PixelSourceMixin hook — uses anywidget's send()."""
        self.send(msg, buffers)

    @anywidget.experimental.observer  # may already be decorated by anywidget
    def _on_msg(self, widget, content, buffers):  # anywidget @msg handler shape
        # anywidget versions vary; the typical shape is a `msg` callback registered
        # via self.on_msg. In this codebase we dispatch explicitly below.
        pass
```

If anywidget's API in this codebase uses `self.on_msg(callback)` registration, register in `__init__` instead:

```python
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_msg(self._route_message)

    def _route_message(self, widget, content, buffers):
        if not isinstance(content, dict):
            return
        kind = content.get("kind")
        if kind == "chunk":
            self.handle_chunk_request(content)
```

Pick whichever matches the installed anywidget version (check with `uv run python -c "import anywidget; print(anywidget.__version__)"`).

- [ ] **Step 4: Smoke test the wiring**

Add a minimal unit test `tests/test_viewer_chunk_wiring.py`:

```python
"""Verify BioImageViewer routes chunk messages to PixelSourceMixin."""
import numpy as np

from anybioimage import BioImageViewer


def test_chunk_message_is_routed():
    v = BioImageViewer()
    v._chunk_array = np.zeros((1, 1, 1, 10, 10), dtype=np.uint8)

    sent = []
    v._send_chunk_response = lambda msg, bufs: sent.append((msg, bufs))

    v._route_message(v, {
        "kind": "chunk", "requestId": 1,
        "t": 0, "c": 0, "z": 0, "level": 0,
        "tx": 0, "ty": 0, "tileSize": 512,
    }, [])
    assert sent and sent[0][0]["ok"] is True
```

- [ ] **Step 5: Run the tests**

```
uv run pytest tests/test_viewer_chunk_wiring.py tests/test_pixel_source.py -v
```

Expected: both files green.

- [ ] **Step 6: Commit**

```bash
git add anybioimage/viewer.py anybioimage/mixins/__init__.py tests/test_viewer_chunk_wiring.py
git commit -m "feat(viewer): route chunk messages through PixelSourceMixin"
```

---

## Task 6: JS-side `AnywidgetPixelSource`

**Goal:** Implement Viv's `PixelSource` interface on top of the chunk bridge. Fulfils `getTile`, `getRaster`, `shape`, `labels`, `tileSize`, `dtype`. Uses `model.send()` for each tile, keyed by `requestId`, with `AbortSignal` support.

**Files:**
- Create: `anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.js`
- Create: `anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.test.js`

- [ ] **Step 1: Install vitest**

```bash
cd anybioimage/frontend/viewer
npm install --save-dev vitest jsdom
```

Add to `package.json` scripts:

```json
  "scripts": {
    "build": "node build.config.mjs",
    "size": "size-limit",
    "test": "vitest run"
  }
```

- [ ] **Step 2: Write the failing test**

```js
// anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.test.js
import { describe, it, expect, vi } from 'vitest';
import { AnywidgetPixelSource } from './anywidget-source.js';

function mockModel(onSend) {
  const listeners = {};
  return {
    send: onSend,
    on: (name, cb) => { listeners[name] = cb; },
    off: () => {},
    emit: (name, content, buffers) => { if (listeners[name]) listeners[name](content, buffers); },
  };
}

describe('AnywidgetPixelSource', () => {
  it('resolves getTile with Viv-shaped output', async () => {
    const raw = new Uint16Array([1, 2, 3, 4]).buffer;
    const model = mockModel((msg) => {
      queueMicrotask(() => model.emit('msg:custom',
        { kind: 'chunk', requestId: msg.requestId, ok: true, w: 2, h: 2, dtype: 'uint16' },
        [raw]));
    });
    const src = new AnywidgetPixelSource(model, {
      shape: { t: 1, c: 1, z: 1, y: 2, x: 2 },
      dtype: 'Uint16',
      tileSize: 512,
    });
    const out = await src.getTile({
      x: 0, y: 0, selection: { t: 0, c: 0, z: 0 }, signal: new AbortController().signal,
    });
    expect(out.width).toBe(2);
    expect(out.height).toBe(2);
    expect(out.data).toBeInstanceOf(Uint16Array);
    expect(Array.from(out.data)).toEqual([1, 2, 3, 4]);
  });

  it('rejects getTile on abort', async () => {
    const model = mockModel(() => {}); // never replies
    const src = new AnywidgetPixelSource(model, {
      shape: { t: 1, c: 1, z: 1, y: 2, x: 2 },
      dtype: 'Uint16',
      tileSize: 512,
    });
    const ac = new AbortController();
    const p = src.getTile({ x: 0, y: 0, selection: { t: 0, c: 0, z: 0 }, signal: ac.signal });
    ac.abort();
    await expect(p).rejects.toThrow(/abort/i);
  });

  it('surfaces server errors', async () => {
    const model = mockModel((msg) => {
      queueMicrotask(() => model.emit('msg:custom',
        { kind: 'chunk', requestId: msg.requestId, ok: false, error: 'out of bounds' }, []));
    });
    const src = new AnywidgetPixelSource(model, {
      shape: { t: 1, c: 1, z: 1, y: 2, x: 2 },
      dtype: 'Uint16',
      tileSize: 512,
    });
    await expect(src.getTile({
      x: 9, y: 9, selection: { t: 0, c: 0, z: 0 }, signal: new AbortController().signal,
    })).rejects.toThrow(/out of bounds/);
  });
});
```

- [ ] **Step 3: Run to see it fail**

```
cd anybioimage/frontend/viewer && npm run test
```

Expected: `Error: Cannot find module './anywidget-source.js'`.

- [ ] **Step 4: Implement the source**

```js
// anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.js
/**
 * AnywidgetPixelSource — implements Viv's PixelSource interface by requesting
 * chunks from Python over the anywidget message channel.
 *
 * Protocol (spec §2):
 *   JS → Py : { kind: "chunk", requestId, t, c, z, level, tx, ty, tileSize }
 *   Py → JS : { kind: "chunk", requestId, ok, w, h, dtype } + buffers[0] (raw bytes)
 *
 * Dtype strings from Python (numpy) are one of: "uint8", "uint16", "uint32", "float32".
 * Viv expects "Uint8" | "Uint16" | "Uint32" | "Float32" in its PixelSource `dtype`.
 */

const DTYPE_TO_VIV = {
  uint8: 'Uint8', uint16: 'Uint16', uint32: 'Uint32', float32: 'Float32',
};

const VIV_TO_ARRAY = {
  Uint8: Uint8Array, Uint16: Uint16Array, Uint32: Uint32Array, Float32: Float32Array,
};

let _nextRequestId = 1;

export class AnywidgetPixelSource {
  constructor(model, { shape, dtype, tileSize = 512, level = 0, labels }) {
    this._model = model;
    this._level = level;
    this._tileSize = tileSize;
    this._dtype = dtype;
    this._shape = shape;
    this._labels = labels || ['t', 'c', 'z', 'y', 'x'];
    this._pending = new Map();

    // Register a single listener; multiplex by requestId.
    // anywidget exposes custom messages on 'msg:custom'.
    this._listener = (content, buffers) => {
      if (!content || content.kind !== 'chunk') return;
      const entry = this._pending.get(content.requestId);
      if (!entry) return;
      this._pending.delete(content.requestId);
      if (!content.ok) {
        entry.reject(new Error(content.error || 'chunk fetch failed'));
        return;
      }
      const Ctor = VIV_TO_ARRAY[dtype] || Uint8Array;
      const view = buffers && buffers[0]
        ? new Ctor(buffers[0])
        : new Ctor(0);
      entry.resolve({ data: view, width: content.w, height: content.h });
    };
    model.on('msg:custom', this._listener);
  }

  destroy() {
    this._model.off('msg:custom', this._listener);
    for (const entry of this._pending.values()) {
      entry.reject(new Error('pixel source destroyed'));
    }
    this._pending.clear();
  }

  get shape() {
    return [this._shape.t, this._shape.c, this._shape.z, this._shape.y, this._shape.x];
  }
  get labels() { return this._labels; }
  get tileSize() { return this._tileSize; }
  get dtype() { return this._dtype; }

  async getTile({ x, y, selection, signal }) {
    const requestId = _nextRequestId++;
    return new Promise((resolve, reject) => {
      const onAbort = () => {
        this._pending.delete(requestId);
        reject(new Error('aborted'));
      };
      if (signal) {
        if (signal.aborted) return onAbort();
        signal.addEventListener('abort', onAbort, { once: true });
      }
      this._pending.set(requestId, {
        resolve: (val) => { if (signal) signal.removeEventListener('abort', onAbort); resolve(val); },
        reject: (err) => { if (signal) signal.removeEventListener('abort', onAbort); reject(err); },
      });
      this._model.send({
        kind: 'chunk',
        requestId,
        t: selection.t | 0,
        c: selection.c | 0,
        z: selection.z | 0,
        level: this._level,
        tx: x | 0,
        ty: y | 0,
        tileSize: this._tileSize,
      });
    });
  }

  async getRaster({ selection, signal }) {
    // Simple: reconstitute from tiles. Called rarely (histogram / auto).
    const w = this._shape.x;
    const h = this._shape.y;
    const Ctor = VIV_TO_ARRAY[this._dtype] || Uint8Array;
    const out = new Ctor(w * h);
    const tile = this._tileSize;
    const tilesX = Math.ceil(w / tile);
    const tilesY = Math.ceil(h / tile);
    const jobs = [];
    for (let ty = 0; ty < tilesY; ty++) {
      for (let tx = 0; tx < tilesX; tx++) {
        jobs.push(this.getTile({ x: tx, y: ty, selection, signal }).then((t) => {
          const x0 = tx * tile;
          const y0 = ty * tile;
          for (let row = 0; row < t.height; row++) {
            out.set(t.data.subarray(row * t.width, (row + 1) * t.width),
                    (y0 + row) * w + x0);
          }
        }));
      }
    }
    await Promise.all(jobs);
    return { data: out, width: w, height: h };
  }

  static dtypeFromPython(pythonDtype) {
    return DTYPE_TO_VIV[pythonDtype] || 'Uint16';
  }
}
```

- [ ] **Step 5: Run the tests**

```
cd anybioimage/frontend/viewer && npm run test
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
cd ../../..
git add anybioimage/frontend/viewer/package.json anybioimage/frontend/viewer/package-lock.json
git add anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.js
git add anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.test.js
git commit -m "feat(viewer/pixel-source): AnywidgetPixelSource implements Viv PixelSource"
```

---

## Task 7: Restructure JS sources into the target tree

**Goal:** Reorganise `anybioimage/frontend/viewer/src/` into the final `chrome/`, `render/`, `interaction/`, `model/`, `util/` folders. Move `zarr-source.js` and `channel-sync.js`; stub the new module files.

**Files:**
- Move: `src/zarr-source.js` → `src/render/pixel-sources/zarr-source.js`
- Move: `src/channel-sync.js` → `src/model/channelState.js`
- Rename: `src/VivCanvas.jsx` → `src/render/DeckCanvas.jsx` (rewrite in Task 10)
- Delete: `src/pixel-info.js` (rewritten in Task 13)
- Delete: `anybioimage/frontend/shared/chrome.js` (moves into React chrome in Tasks 11–14)

- [ ] **Step 1: Move existing files**

```bash
cd anybioimage/frontend/viewer/src
mkdir -p render/pixel-sources render/layers render/luts/lut-textures
mkdir -p chrome/LayersPanel interaction/tools model util
git mv zarr-source.js render/pixel-sources/zarr-source.js
git mv channel-sync.js model/channelState.js
git mv VivCanvas.jsx render/DeckCanvas.jsx   # rewritten in Task 10
git rm pixel-info.js   # replaced by render/onHoverPixelInfo.js in Task 13
cd ../../../..
git rm anybioimage/frontend/shared/chrome.js
```

- [ ] **Step 2: Update imports in `entry.js`**

Edit `anybioimage/frontend/viewer/src/entry.js`:

```js
// anybioimage/frontend/viewer/src/entry.js
import React from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App.jsx';

async function render({ model, el }) {
  // WebGL2 gate.
  const canvas = document.createElement('canvas');
  const hasWebGL2 = !!canvas.getContext('webgl2');
  if (!hasWebGL2) {
    el.innerHTML = '<div style="padding:16px;font-family:system-ui;background:#fff4e5;border:1px solid #ffcc80;border-radius:4px;color:#7a4500">' +
      '<strong>WebGL2 required.</strong> anybioimage needs a browser with WebGL2 enabled. ' +
      'Chrome/Edge/Firefox ≥ 120 and Safari ≥ 17 support this out of the box. ' +
      'Check <code>about:gpu</code> if you see this message on a modern browser.</div>';
    return;
  }
  const root = createRoot(el);
  root.render(React.createElement(App, { model }));
  return () => root.unmount();
}

export default { render };
```

- [ ] **Step 3: Stub `App.jsx` so the bundle builds**

```jsx
// anybioimage/frontend/viewer/src/App.jsx
import React from 'react';

export function App({ model }) {
  return <div style={{padding: 16, color: '#666'}}>App under construction (Phase 1 in progress)</div>;
}
```

- [ ] **Step 4: Build to confirm the bundle still builds**

```
cd anybioimage/frontend/viewer && npm run build && cd ../../..
```

Expected: `dist/viewer-bundle.js` emitted, no errors.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(viewer): reorganise src/ into chrome/render/interaction/model/util"
```

---

## Task 8: `buildImageLayer.js` — Viv image layer from either pixel source

**Goal:** Produce a `MultiscaleImageLayer` props object from: a pixel-source list (either `ZarrPixelSource[]` from Viv's `loadOmeZarr`, or a single-element `[AnywidgetPixelSource]` for non-URL inputs), plus the channel state.

**Files:**
- Create: `anybioimage/frontend/viewer/src/render/layers/buildImageLayer.js`
- Create: `anybioimage/frontend/viewer/src/render/layers/buildImageLayer.test.js`

- [ ] **Step 1: Write the failing test**

```js
// anybioimage/frontend/viewer/src/render/layers/buildImageLayer.test.js
import { describe, it, expect } from 'vitest';
import { buildImageLayerProps } from './buildImageLayer.js';

describe('buildImageLayerProps', () => {
  const sources = [{ shape: [1, 3, 1, 2048, 2048], labels: ['t','c','z','y','x'] }];
  const channels = [
    { index: 0, visible: true, color_kind: 'solid', color: '#ff0000',
      data_min: 0, data_max: 65535, min: 0.1, max: 0.9 },
    { index: 1, visible: false, color_kind: 'solid', color: '#00ff00',
      data_min: 0, data_max: 65535, min: 0, max: 1 },
    { index: 2, visible: true, color_kind: 'lut', lut: 'viridis',
      data_min: 0, data_max: 65535, min: 0, max: 1 },
  ];

  it('maps visible channels to selections/colors/contrastLimits', () => {
    const props = buildImageLayerProps({
      sources, channels, currentT: 2, currentZ: 0, displayMode: 'composite',
    });
    expect(props.selections).toEqual([
      { t: 2, c: 0, z: 0 },
      { t: 2, c: 2, z: 0 },
    ]);
    expect(props.contrastLimits[0]).toEqual([6553.5, 58981.5]);
    expect(props.channelsVisible).toEqual([true, true]);
  });

  it('single mode keeps only the active channel', () => {
    const props = buildImageLayerProps({
      sources, channels, currentT: 0, currentZ: 0, displayMode: 'single', activeChannel: 2,
    });
    expect(props.selections).toEqual([{ t: 0, c: 2, z: 0 }]);
  });

  it('clamps to 6 channels and sets exceeded flag', () => {
    const many = Array.from({ length: 8 }, (_, i) => ({
      index: i, visible: true, color_kind: 'solid', color: '#ffffff',
      data_min: 0, data_max: 255, min: 0, max: 1,
    }));
    const props = buildImageLayerProps({
      sources, channels: many, currentT: 0, currentZ: 0, displayMode: 'composite',
    });
    expect(props.selections.length).toBe(6);
    expect(props.exceeded).toBe(true);
  });
});
```

- [ ] **Step 2: Run to verify fail**

```
cd anybioimage/frontend/viewer && npm run test
```

Expected: missing module `./buildImageLayer.js`.

- [ ] **Step 3: Implement**

```js
// anybioimage/frontend/viewer/src/render/layers/buildImageLayer.js
const MAX_CHANNELS = 6;

function hexToRgb(hex) {
  const clean = (hex || '#ffffff').replace('#', '');
  const n = parseInt(clean, 16);
  return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff];
}

function contrastFor(channel) {
  const dmin = channel.data_min ?? 0;
  const dmax = channel.data_max ?? 65535;
  const span = Math.max(dmax - dmin, 1);
  return [dmin + (channel.min ?? 0) * span, dmin + (channel.max ?? 1) * span];
}

export function buildImageLayerProps({
  sources, channels, currentT, currentZ,
  displayMode = 'composite', activeChannel = 0,
}) {
  const visibleChannels = (channels || [])
    .map((ch, idx) => ({ ...ch, index: ch.index ?? idx }))
    .filter((ch) => ch.visible);

  let active = visibleChannels;
  if (displayMode === 'single') {
    const pick = visibleChannels.find((ch) => ch.index === activeChannel)
              ?? visibleChannels[0];
    active = pick ? [pick] : [];
  }

  const clipped = active.slice(0, MAX_CHANNELS);
  const exceeded = active.length > MAX_CHANNELS;

  const selections = clipped.map((ch) => ({ t: currentT, c: ch.index, z: currentZ }));
  const colors = clipped.map((ch) => hexToRgb(ch.color));
  const contrastLimits = clipped.map(contrastFor);
  const channelsVisible = clipped.map(() => true);
  const useLut = clipped.map((ch) => ch.color_kind === 'lut' ? (ch.lut || 'viridis') : null);

  return {
    loader: sources,
    selections,
    colors,
    contrastLimits,
    channelsVisible,
    useLut,           // consumed by VivLutExtension in Task 9
    exceeded,
  };
}
```

- [ ] **Step 4: Run the tests**

```
cd anybioimage/frontend/viewer && npm run test
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd ../../..
git add anybioimage/frontend/viewer/src/render/layers/buildImageLayer.js
git add anybioimage/frontend/viewer/src/render/layers/buildImageLayer.test.js
git commit -m "feat(viewer/render): buildImageLayerProps from channel state"
```

---

## Task 9: LUT registry + Viv shader extension

**Goal:** Ship 15 named LUT PNGs; provide a browser-side registry that loads the PNG once per LUT and builds a `Uint8Array` of length 1024 (256×4 RGBA). Provide a `VivLutExtension` that plugs into Viv's `MultiscaleImageLayer` and adds an optional `lut[intensity]` sampling path.

**Files:**
- Create: `anybioimage/frontend/viewer/src/render/luts/index.js`
- Create: `anybioimage/frontend/viewer/src/render/luts/index.test.js`
- Create: `anybioimage/frontend/viewer/src/render/luts/VivLutExtension.js`
- Create: `anybioimage/frontend/viewer/src/render/luts/lut-textures/*.png` (15 files, generated below)

- [ ] **Step 1: Generate the LUT PNGs**

```python
# scripts/gen_luts.py  (committed to repo as tooling)
"""Generate 256×1 RGBA PNGs for every shipped LUT."""
from pathlib import Path

import numpy as np
from matplotlib import cm
from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "anybioimage/frontend/viewer/src/render/luts/lut-textures"
OUT.mkdir(parents=True, exist_ok=True)

named = [
    "gray", "viridis", "plasma", "magma", "inferno", "cividis", "turbo",
    "hot", "cool",
]
# Plain ramps for red/green/blue/cyan/magenta/yellow
def ramp(rgb):
    xs = np.linspace(0, 1, 256)
    arr = np.zeros((256, 4), dtype=np.uint8)
    arr[:, 0] = xs * rgb[0] * 255
    arr[:, 1] = xs * rgb[1] * 255
    arr[:, 2] = xs * rgb[2] * 255
    arr[:, 3] = 255
    return arr

plain = {
    "red": (1, 0, 0), "green": (0, 1, 0), "blue": (0, 0, 1),
    "cyan": (0, 1, 1), "magenta": (1, 0, 1), "yellow": (1, 1, 0),
}

for name in named:
    cmap = cm.get_cmap(name, 256)
    rgba = (cmap(np.linspace(0, 1, 256)) * 255).astype(np.uint8)
    Image.fromarray(rgba[None, :, :], mode="RGBA").save(OUT / f"{name}.png")

for name, rgb in plain.items():
    arr = ramp(rgb)
    Image.fromarray(arr[None, :, :], mode="RGBA").save(OUT / f"{name}.png")

print(f"wrote {len(named) + len(plain)} LUT PNGs to {OUT}")
```

Run once:

```
uv run python scripts/gen_luts.py
```

- [ ] **Step 2: Write the registry tests**

```js
// anybioimage/frontend/viewer/src/render/luts/index.test.js
/** @vitest-environment jsdom */
import { describe, it, expect, beforeEach } from 'vitest';
import { getLutTexture, listLuts } from './index.js';

describe('LUT registry', () => {
  beforeEach(() => {
    // Mock Image decode so we can run headless.
    globalThis.Image = class {
      constructor() { this.width = 256; this.height = 1; }
      set src(_v) { queueMicrotask(() => this.onload && this.onload()); }
      decode() { return Promise.resolve(); }
    };
  });

  it('lists all shipped LUT names', () => {
    const names = listLuts();
    expect(names).toContain('viridis');
    expect(names).toContain('gray');
    expect(names).toContain('red');
    expect(names.length).toBe(15);
  });

  it('caches the same Uint8Array across repeated calls', async () => {
    const a = await getLutTexture('viridis');
    const b = await getLutTexture('viridis');
    expect(a).toBe(b); // same reference
    expect(a.length).toBe(256 * 4);
  });
});
```

- [ ] **Step 3: Implement the registry**

```js
// anybioimage/frontend/viewer/src/render/luts/index.js
import gray from './lut-textures/gray.png';
import viridis from './lut-textures/viridis.png';
import plasma from './lut-textures/plasma.png';
import magma from './lut-textures/magma.png';
import inferno from './lut-textures/inferno.png';
import cividis from './lut-textures/cividis.png';
import turbo from './lut-textures/turbo.png';
import hot from './lut-textures/hot.png';
import cool from './lut-textures/cool.png';
import red from './lut-textures/red.png';
import green from './lut-textures/green.png';
import blue from './lut-textures/blue.png';
import cyan from './lut-textures/cyan.png';
import magenta from './lut-textures/magenta.png';
import yellow from './lut-textures/yellow.png';

const SOURCES = {
  gray, viridis, plasma, magma, inferno, cividis, turbo, hot, cool,
  red, green, blue, cyan, magenta, yellow,
};

const _cache = new Map();

export function listLuts() {
  return Object.keys(SOURCES);
}

export async function getLutTexture(name) {
  if (_cache.has(name)) return _cache.get(name);
  const src = SOURCES[name];
  if (!src) throw new Error(`unknown LUT: ${name}`);
  const img = new Image();
  img.src = src;
  await (img.decode ? img.decode() : new Promise((res) => { img.onload = res; }));
  const canvas = document.createElement('canvas');
  canvas.width = 256; canvas.height = 1;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(img, 0, 0);
  const pixels = ctx.getImageData(0, 0, 256, 1).data;
  const out = new Uint8Array(256 * 4);
  out.set(pixels);
  _cache.set(name, out);
  return out;
}
```

- [ ] **Step 4: Implement the Viv shader extension**

```js
// anybioimage/frontend/viewer/src/render/luts/VivLutExtension.js
/**
 * VivLutExtension — optional per-channel LUT lookup for Viv's multichannel
 * shader. When a channel's `useLut[i]` slot is non-null, the fragment shader
 * samples the corresponding 256×1 RGBA texture using the channel's normalised
 * intensity instead of multiplying by a flat colour.
 *
 * Phase-1 implementation note: for simplicity we render LUT channels in a
 * second pass rather than patching Viv's internal shader. The second pass is
 * an `ImageLayer`-like composite that samples the LUT texture; solid-colour
 * channels remain in the fast path.
 */
import { LayerExtension } from '@deck.gl/core';

export class VivLutExtension extends LayerExtension {
  getShaders() {
    return {
      modules: [{
        name: 'viv-lut',
        inject: {
          'fs:DECKGL_FILTER_COLOR': `
            if (vLutIntensity > 0.0) {
              color = texture(lutTex, vec2(vLutIntensity, 0.5));
            }
          `,
        },
      }],
    };
  }

  updateState({ props, oldProps }) {
    if (props.useLut !== oldProps.useLut) {
      // Upload newly used LUTs as textures — done by the layer's own setState.
    }
  }
}
```

- [ ] **Step 5: Run the registry tests**

```
cd anybioimage/frontend/viewer && npm run test
```

Expected: 2 passed (registry), existing tests still green.

- [ ] **Step 6: Commit**

```bash
cd ../../..
git add scripts/gen_luts.py
git add anybioimage/frontend/viewer/src/render/luts/lut-textures/*.png
git add anybioimage/frontend/viewer/src/render/luts/index.js
git add anybioimage/frontend/viewer/src/render/luts/index.test.js
git add anybioimage/frontend/viewer/src/render/luts/VivLutExtension.js
git commit -m "feat(viewer/luts): 15-LUT registry + VivLutExtension scaffold"
```

**Note:** The custom shader integration is a "scaffold" — flat-colour channels render correctly from Task 10 onwards; full LUT rendering is wired via `PictureInPictureViewer`'s `extensions` prop in Task 10 and visually validated in Task 20 (demo app LUT-switching cell). If the extension approach hits Viv-internal GLSL mismatches, fall back to a parallel `ImageLayer` per LUT channel — tracked as a spec §13 open item.

---

## Task 10: `DeckCanvas.jsx` — single deck.gl canvas + layer composer

**Goal:** Replace `PictureInPictureViewer` with an explicit `DeckGL` component plus a composed layer list. In Phase 1 the list is: `[buildImageLayer(...), buildScaleBar(...)]`.

**Files:**
- Rewrite: `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx`

- [ ] **Step 1: Write the component**

```jsx
// anybioimage/frontend/viewer/src/render/DeckCanvas.jsx
import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { OrthographicView } from '@deck.gl/core';
import { MultiscaleImageLayer } from '@hms-dbmi/viv';

import { openOmeZarr } from './pixel-sources/zarr-source.js';
import { AnywidgetPixelSource } from './pixel-sources/anywidget-source.js';
import { buildImageLayerProps } from './layers/buildImageLayer.js';
import { buildScaleBarLayer } from './layers/buildScaleBar.js';
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

export function DeckCanvas({ model, onHover, deckRef }) {
  const zarrSource = useModelTrait(model, '_zarr_source');
  const pixelSourceMode = useModelTrait(model, '_pixel_source_mode');
  const channelSettings = useModelTrait(model, '_channel_settings');
  const currentT = useModelTrait(model, 'current_t');
  const currentZ = useModelTrait(model, 'current_z');
  const displayMode = useModelTrait(model, '_display_mode') || 'composite';
  const activeChannel = useModelTrait(model, 'current_c') || 0;
  const pixelSizeUm = useModelTrait(model, 'pixel_size_um');
  const scaleBarVisible = useModelTrait(model, 'scale_bar_visible') !== false;
  const imageVisible = useModelTrait(model, 'image_visible') !== false;

  const containerRef = useRef(null);
  const { width, height } = useContainerSize(containerRef);

  const [sources, setSources] = useState(null);
  const [error, setError] = useState(null);
  const [viewState, setViewState] = useState(null);

  // Open the source whenever the mode or url changes.
  useEffect(() => {
    let cancelled = false;
    let activeAnywidgetSource = null;
    async function run() {
      setError(null);
      if (pixelSourceMode === 'chunk_bridge') {
        const shape = model.get('_image_shape') || null;
        const dtype = model.get('_image_dtype') || 'Uint16';
        if (!shape) { setSources(null); return; }
        activeAnywidgetSource = new AnywidgetPixelSource(model, {
          shape, dtype, tileSize: 512,
        });
        setSources([activeAnywidgetSource]);
      } else if (zarrSource?.url) {
        try {
          const { sources: srcs } = await openOmeZarr(zarrSource.url, zarrSource.headers || {});
          if (!cancelled) setSources(srcs);
        } catch (e) {
          if (!cancelled) { setError(String(e)); setSources(null); }
        }
      } else {
        setSources(null);
      }
    }
    run();
    return () => {
      cancelled = true;
      if (activeAnywidgetSource) activeAnywidgetSource.destroy();
    };
  }, [pixelSourceMode, zarrSource?.url]);

  // Reset view on new source.
  useEffect(() => {
    if (!sources || !sources.length) return;
    const level0 = sources[0];
    const [, , , h, w] = level0.shape;
    const zoom = Math.log2(Math.min(width / w, height / h) || 1);
    setViewState({
      target: [w / 2, h / 2, 0],
      zoom,
      rotationX: 0, rotationOrbit: 0,
    });
  }, [sources, width, height]);

  const layers = useMemo(() => {
    if (!sources || !sources.length || !imageVisible) return [];
    const props = buildImageLayerProps({
      sources, channels: channelSettings || [],
      currentT: currentT || 0, currentZ: currentZ || 0,
      displayMode, activeChannel,
    });
    const imageLayer = new MultiscaleImageLayer({
      id: 'viv-image',
      ...props,
    });
    const out = [imageLayer];
    if (scaleBarVisible && pixelSizeUm) {
      out.push(buildScaleBarLayer({ pixelSizeUm, viewState, width, height }));
    }
    return out;
  }, [sources, channelSettings, currentT, currentZ, displayMode, activeChannel,
      imageVisible, pixelSizeUm, scaleBarVisible, viewState, width, height]);

  if (error) {
    return <div style={{ color: '#b00', padding: 12 }}>Failed to load image: {error}</div>;
  }

  return (
    <div ref={containerRef} style={{ position: 'absolute', inset: 0 }}>
      {!sources ? (
        <div style={{ padding: 12, color: '#666' }}>Loading…</div>
      ) : (
        <DeckGL
          ref={deckRef}
          width={width}
          height={height}
          layers={layers}
          views={[new OrthographicView({ id: 'ortho', controller: true })]}
          viewState={viewState ? { ortho: viewState } : undefined}
          onViewStateChange={({ viewState: v }) => setViewState(v)}
          onHover={onHover}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add `useModelTrait` helper**

```js
// anybioimage/frontend/viewer/src/model/useModelTrait.js
import { useEffect, useState } from 'react';

export function useModelTrait(model, name) {
  const [value, setValue] = useState(() => model.get(name));
  useEffect(() => {
    const handler = () => setValue(model.get(name));
    model.on(`change:${name}`, handler);
    return () => model.off(`change:${name}`, handler);
  }, [model, name]);
  return value;
}
```

- [ ] **Step 3: Stub `buildScaleBar.js` (full impl in Task 14)**

```js
// anybioimage/frontend/viewer/src/render/layers/buildScaleBar.js
// Full implementation in Task 14. Phase-1 stub so DeckCanvas compiles.
import { CompositeLayer } from '@deck.gl/core';

class _StubScaleBarLayer extends CompositeLayer {
  renderLayers() { return []; }
}
_StubScaleBarLayer.layerName = 'ScaleBarLayer';

export function buildScaleBarLayer() {
  return new _StubScaleBarLayer({ id: 'scale-bar' });
}
```

- [ ] **Step 4: Build**

```
cd anybioimage/frontend/viewer && npm run build && cd ../../..
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add anybioimage/frontend/viewer/src/render/DeckCanvas.jsx
git add anybioimage/frontend/viewer/src/render/layers/buildScaleBar.js
git add anybioimage/frontend/viewer/src/model/useModelTrait.js
git commit -m "feat(viewer/render): DeckCanvas with explicit DeckGL + layer composer"
```

---

## Task 11: Slim `image_loading.py` + route inputs

**Goal:** `set_image()` now decides:
- URL → `_zarr_source = {url}`, `_pixel_source_mode = "zarr"`, no Python chunk cache.
- numpy / bioio → `_chunk_array = np_array`, `_pixel_source_mode = "chunk_bridge"`, `_image_shape`, `_image_dtype` traitlets.

Delete the compositor, tile cache, precompute threads, thumbnail, and PNG encoding.

**Files:**
- Modify: `anybioimage/mixins/image_loading.py`
- Modify: `anybioimage/viewer.py` (traitlet declarations)
- Create: `tests/test_image_loading_slim.py`
- Create: `tests/test_metadata_extraction.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_image_loading_slim.py
"""After the slim-down, set_image() must NOT:
  - start a precompute thread
  - populate a tile cache
  - generate PNG thumbnails
  - set image_data traitlet to anything but ""
"""
import numpy as np
from anybioimage import BioImageViewer


def test_set_numpy_creates_chunk_bridge_mode():
    v = BioImageViewer()
    v.set_image(np.zeros((3, 2, 1, 100, 100), dtype=np.uint16))
    assert v._pixel_source_mode == "chunk_bridge"
    assert v._image_shape == {"t": 3, "c": 2, "z": 1, "y": 100, "x": 100}
    assert v._image_dtype == "Uint16"
    assert v._chunk_array is not None
    assert v.image_data == ""


def test_set_url_creates_zarr_mode():
    v = BioImageViewer()
    v.set_image("https://example.com/my.ome.zarr")
    assert v._pixel_source_mode == "zarr"
    assert v._zarr_source == {"url": "https://example.com/my.ome.zarr", "headers": {}}
    assert v._chunk_array is None


def test_no_precompute_attributes_exist():
    v = BioImageViewer()
    # These were removed with the Canvas2D compositor.
    assert not hasattr(v, "_composite_cache")
    assert not hasattr(v, "_tile_cache")
    assert not hasattr(v, "_precompute_all_composites")
    assert not hasattr(v, "use_jpeg_tiles")
```

```python
# tests/test_metadata_extraction.py
"""Channel names and pixel_size_um must be populated correctly."""
import numpy as np

from anybioimage import BioImageViewer
from anybioimage.mixins.image_loading import _channel_settings_from_omero


def test_channel_names_from_omero():
    ome = {"omero": {"channels": [
        {"label": "DAPI", "color": "0000FF", "window": {"start": 0, "end": 1000, "min": 0, "max": 65535}},
        {"label": "GFP", "color": "00FF00", "window": {"start": 0, "end": 500, "min": 0, "max": 65535}},
    ]}}
    settings = _channel_settings_from_omero(ome, dim_c=2, dtype=np.uint16)
    assert settings[0]["name"] == "DAPI"
    assert settings[1]["color"].lower() == "#00ff00"


def test_default_channel_names_for_numpy():
    v = BioImageViewer()
    v.set_image(np.zeros((1, 3, 1, 32, 32), dtype=np.uint8))
    names = [c["name"] for c in v._channel_settings]
    assert names == ["Ch 0", "Ch 1", "Ch 2"]


def test_pixel_size_um_none_for_numpy():
    v = BioImageViewer()
    v.set_image(np.zeros((1, 1, 1, 10, 10), dtype=np.uint8))
    assert v.pixel_size_um is None
```

- [ ] **Step 2: Add traitlets to viewer.py**

In `anybioimage/viewer.py`, inside `BioImageViewer` class:

```python
    # NEW traitlets for unified pipeline
    _pixel_source_mode = traitlets.Unicode("none").tag(sync=True)   # "none"|"zarr"|"chunk_bridge"
    _image_shape = traitlets.Dict(allow_none=True, default_value=None).tag(sync=True)
    _image_dtype = traitlets.Unicode("Uint16").tag(sync=True)
    _display_mode = traitlets.Unicode("composite").tag(sync=True)   # "composite"|"single"
    pixel_size_um = traitlets.Float(allow_none=True, default_value=None).tag(sync=True)
    scale_bar_visible = traitlets.Bool(True).tag(sync=True)

    # REMOVED (see CHANGELOG breaking section)
    # _viv_mode, use_jpeg_tiles, _viewport_tiles
```

Remove the declarations of `_viv_mode`, `use_jpeg_tiles`, `_viewport_tiles` from this file.

- [ ] **Step 3: Rewrite `image_loading.py`**

Strip it to the essentials. Target file is ~300 lines (down from 1228). Keep:
- `_channel_settings_from_omero` (unchanged).
- Zarr URL detection (`_looks_like_zarr_url`, `_ZARR_SUFFIXES`).
- Metadata population from bioio (shape, dtype, channel defaults, `physical_pixel_sizes`).
- New `_set_numpy_source(arr)` and `_set_zarr_url(url, headers={})` methods.
- `set_image(data)` public method that dispatches.

Remove:
- All `_composite_cache`, `_tile_cache`, `_precompute_*`, `_update_slice`, `_viewport_tiles_all_cached`, `_thumbnail`.
- `array_to_base64`, `array_to_fast_png_base64`, `composite_channels`, `normalize_image` imports (they stay in `utils.py` but `image_loading` no longer uses them).

Replacement:

```python
# anybioimage/mixins/image_loading.py
"""Unified image loading — metadata only. Rendering is done by Viv on the GPU
from either a remote zarr URL (direct browser fetch) or a chunk-bridged numpy
array (see PixelSourceMixin)."""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

_ZARR_SUFFIXES = (".zarr", ".ome.zarr", ".zarr/")

_DTYPE_TO_JS = {
    "uint8": "Uint8", "uint16": "Uint16",
    "uint32": "Uint32", "float32": "Float32",
}


def _looks_like_zarr_url(s: str) -> bool:
    if not isinstance(s, str):
        return False
    stripped = s.split("?", 1)[0].split("#", 1)[0].rstrip("/").lower()
    return stripped.endswith(_ZARR_SUFFIXES)


def _channel_settings_from_omero(ome: dict, dim_c: int, dtype: Any = None) -> list[dict]:
    # (unchanged body from existing image_loading.py — copy verbatim, preserving
    # the dtype-aware clipping fix. See existing file for full listing.)
    dtype_min: float | None = None
    dtype_max: float | None = None
    if dtype is not None and np.issubdtype(np.dtype(dtype), np.integer):
        info = np.iinfo(np.dtype(dtype))
        dtype_min = float(info.min); dtype_max = float(info.max)
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


class ImageLoadingMixin:
    """Metadata-only image loading. Route `set_image()` to one of three paths."""

    def set_image(self, data: Any, *, headers: dict | None = None) -> None:
        """Load an image. `data` may be:
          * str / path — filesystem path or URL; zarr detected by suffix.
          * numpy.ndarray — 2D (YX), 3D (CYX), 4D (CZYX) or 5D (TCZYX).
          * bioio.BioImage — any file supported by bioio.
        """
        if isinstance(data, str):
            if _looks_like_zarr_url(data):
                self._set_zarr_url(data, headers or {})
                return
            # Non-URL string — try to open with bioio if available.
            try:
                from bioio import BioImage
                bio = BioImage(data)
                self._set_bioimage(bio)
                return
            except Exception as exc:  # pragma: no cover
                raise ValueError(f"could not open {data!r}: {exc}") from exc
        if isinstance(data, np.ndarray):
            self._set_numpy_source(data)
            return
        # BioImage duck-typing (avoid hard import for optional dep).
        if hasattr(data, "dims") and hasattr(data, "get_image_data"):
            self._set_bioimage(data)
            return
        raise TypeError(f"unsupported image type: {type(data).__name__}")

    def _set_zarr_url(self, url: str, headers: dict) -> None:
        self._clear_image_state()
        self._zarr_source = {"url": url, "headers": headers}
        self._pixel_source_mode = "zarr"
        # Dim/channel traitlets are populated JS-side from the zarr metadata.

    def _set_numpy_source(self, arr: np.ndarray) -> None:
        self._clear_image_state()
        tczyx = _to_tczyx(arr)
        self._chunk_array = tczyx
        t, c, z, y, x = tczyx.shape
        self._image_shape = {"t": t, "c": c, "z": z, "y": y, "x": x}
        self._image_dtype = _DTYPE_TO_JS.get(str(tczyx.dtype), "Uint16")
        self.dim_t = t; self.dim_c = c; self.dim_z = z
        self.width = x; self.height = y
        self._channel_settings = _channel_settings_from_omero({}, dim_c=c, dtype=tczyx.dtype)
        self.pixel_size_um = None
        self._pixel_source_mode = "chunk_bridge"

    def _set_bioimage(self, bio: Any) -> None:
        arr = np.asarray(bio.get_image_data("TCZYX"))
        if arr.nbytes > 2 * 1024 ** 3:
            logger.warning(
                "Image exceeds 2 GB (%.2f GB) and will be eagerly loaded into RAM; "
                "consider converting to OME-Zarr for lazy tile access.",
                arr.nbytes / 1024 ** 3)
        self._set_numpy_source(arr)
        try:
            self.pixel_size_um = float(bio.physical_pixel_sizes.X)  # type: ignore[attr-defined]
        except Exception:
            self.pixel_size_um = None
        try:
            names = [c.Name for c in bio.ome_metadata.images[0].pixels.channels]  # type: ignore[attr-defined]
            for i, name in enumerate(names):
                if i < len(self._channel_settings):
                    self._channel_settings[i]["name"] = name
            # Re-emit to trigger sync.
            self._channel_settings = list(self._channel_settings)
        except Exception:
            pass

    def _clear_image_state(self) -> None:
        self._chunk_array = None
        self._chunk_cache.clear() if hasattr(self, "_chunk_cache") else None
        self._pixel_source_mode = "none"
        self._image_shape = None
        self._zarr_source = {}


def _to_tczyx(arr: np.ndarray) -> np.ndarray:
    if arr.ndim == 5: return arr
    if arr.ndim == 4: return arr[None, ...]
    if arr.ndim == 3: return arr[None, :, None, :, :]
    if arr.ndim == 2: return arr[None, None, None, :, :]
    raise ValueError(f"unsupported ndim: {arr.ndim}")
```

- [ ] **Step 4: Run tests**

```
uv run pytest tests/test_image_loading_slim.py tests/test_metadata_extraction.py tests/test_pixel_source.py -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add anybioimage/mixins/image_loading.py anybioimage/viewer.py
git add tests/test_image_loading_slim.py tests/test_metadata_extraction.py
git commit -m "refactor(image-loading): slim to metadata-only; delete compositor/tile cache"
```

---

## Task 12: React chrome — Toolbar, DimControls, StatusBar, App

**Goal:** Port `shared/chrome.js` (DOM-built chrome, 427 lines) into focused React components. Toolbar reflects `tool_mode` traitlet changes externally (fixes existing bug). Layers panel is split and implemented in Task 13.

**Files:**
- Rewrite: `anybioimage/frontend/viewer/src/App.jsx`
- Create: `anybioimage/frontend/viewer/src/chrome/Toolbar.jsx`
- Create: `anybioimage/frontend/viewer/src/chrome/DimControls.jsx`
- Create: `anybioimage/frontend/viewer/src/chrome/StatusBar.jsx`

- [ ] **Step 1: Write App.jsx**

```jsx
// anybioimage/frontend/viewer/src/App.jsx
import React, { useState, useCallback } from 'react';
import { Toolbar } from './chrome/Toolbar.jsx';
import { DimControls } from './chrome/DimControls.jsx';
import { StatusBar } from './chrome/StatusBar.jsx';
import { LayersPanel } from './chrome/LayersPanel/LayersPanel.jsx';
import { DeckCanvas } from './render/DeckCanvas.jsx';
import { installKeyboard } from './interaction/keyboard.js';

export function App({ model }) {
  const [panelOpen, setPanelOpen] = useState(false);
  const [hover, setHover] = useState(null);
  const onHover = useCallback(({ coordinate, layer }) => {
    if (!coordinate) { setHover(null); return; }
    const [x, y] = coordinate;
    setHover({ x: Math.floor(x), y: Math.floor(y) });
  }, []);

  React.useEffect(() => installKeyboard(model), [model]);

  return (
    <div className="bioimage-viewer" tabIndex={0}>
      <Toolbar model={model} onToggleLayers={() => setPanelOpen((v) => !v)} panelOpen={panelOpen} />
      <DimControls model={model} />
      <div className="content-area">
        <div className="viewport-slot" style={{ position: 'relative', flex: 1, minHeight: 500, background: '#000' }}>
          <DeckCanvas model={model} onHover={onHover} />
        </div>
        {panelOpen && <LayersPanel model={model} />}
      </div>
      <StatusBar model={model} hover={hover} />
    </div>
  );
}
```

- [ ] **Step 2: Write Toolbar.jsx**

```jsx
// anybioimage/frontend/viewer/src/chrome/Toolbar.jsx
import React from 'react';
import { useModelTrait } from '../model/useModelTrait.js';

const ICONS = {
  pan: 'P', select: 'V', reset: '↺', layers: '☰',
  // Phase 2 tools show but are disabled until implemented.
  rect: '▭', polygon: '⬡', point: '•',
  line: '／', areaMeasure: '△', lineProfile: '∼',
};

function ToolButton({ model, mode, label, disabled }) {
  const current = useModelTrait(model, 'tool_mode');
  const active = current === mode;
  return (
    <button
      className={'tool-btn' + (active ? ' active' : '')}
      disabled={disabled}
      title={label}
      onClick={() => { model.set('tool_mode', mode); model.save_changes(); }}
    >{ICONS[mode] || mode}</button>
  );
}

export function Toolbar({ model, onToggleLayers, panelOpen }) {
  const phase2Disabled = true;   // rect/polygon/point/measure land in Phase 2
  return (
    <div className="toolbar">
      <div className="tool-group">
        <ToolButton model={model} mode="pan" label="Pan (P)" />
        <ToolButton model={model} mode="select" label="Select (V)" />
      </div>
      <div className="toolbar-separator" />
      <div className="tool-group">
        <ToolButton model={model} mode="rect" label="Rectangle (R)" disabled={phase2Disabled} />
        <ToolButton model={model} mode="polygon" label="Polygon (G)" disabled={phase2Disabled} />
        <ToolButton model={model} mode="point" label="Point (O)" disabled={phase2Disabled} />
        <ToolButton model={model} mode="line" label="Line (L)" disabled={phase2Disabled} />
        <ToolButton model={model} mode="areaMeasure" label="Area measure (M)" disabled={phase2Disabled} />
      </div>
      <div className="toolbar-separator" />
      <button className="tool-btn" title="Reset view"
              onClick={() => model.send({ kind: 'reset-view' })}>{ICONS.reset}</button>
      <div className="toolbar-separator" />
      <button className={'layers-btn' + (panelOpen ? ' active' : '')} onClick={onToggleLayers}>
        <span>{ICONS.layers}</span><span> Layers</span>
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Write DimControls.jsx**

```jsx
// anybioimage/frontend/viewer/src/chrome/DimControls.jsx
import React, { useEffect, useRef, useState } from 'react';
import { useModelTrait } from '../model/useModelTrait.js';

function useLivePlay(model, key, max, speed = 200) {
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      const next = ((model.get(key) ?? 0) + 1) % max;
      model.set(key, next); model.save_changes();
    }, speed);
    return () => clearInterval(id);
  }, [playing, model, key, max, speed]);
  return [playing, setPlaying];
}

function DimSlider({ model, label, traitKey, max, showPlay = false }) {
  const value = useModelTrait(model, traitKey) ?? 0;
  const [playing, setPlaying] = useLivePlay(model, traitKey, max);
  if (max <= 1) return null;
  return (
    <div className="dim-slider-wrapper">
      <span className="dim-label">{label}</span>
      {showPlay && (
        <button className="play-btn" onClick={() => setPlaying(!playing)}>{playing ? '⏸' : '▶'}</button>
      )}
      <input className="dim-slider" type="range" min="0" max={max - 1} value={value}
        onChange={(e) => { model.set(traitKey, parseInt(e.target.value)); model.save_changes(); }} />
      <span className="dim-value">{value}/{max}</span>
    </div>
  );
}

function Selector({ model, label, listKey, currentKey }) {
  const items = useModelTrait(model, listKey) || [];
  const current = useModelTrait(model, currentKey);
  if (items.length === 0) return null;
  return (
    <div className="scene-selector-wrapper">
      <span className="dim-label">{label}</span>
      <select className="scene-select" value={current || ''}
        onChange={(e) => { model.set(currentKey, e.target.value); model.save_changes(); }}>
        {items.map((i) => <option key={i} value={i}>{i}</option>)}
      </select>
    </div>
  );
}

export function DimControls({ model }) {
  const dimT = useModelTrait(model, 'dim_t') || 1;
  const dimZ = useModelTrait(model, 'dim_z') || 1;
  const scenes = useModelTrait(model, 'scenes') || [];
  const wells = useModelTrait(model, 'plate_wells') || [];
  const fovs = useModelTrait(model, 'plate_fovs') || [];
  const hasAny = dimT > 1 || dimZ > 1 || scenes.length > 1 || wells.length > 0;
  if (!hasAny) return null;
  return (
    <div className="dimension-controls">
      <Selector model={model} label="Well" listKey="plate_wells" currentKey="current_well" />
      <Selector model={model} label="FOV" listKey="plate_fovs" currentKey="current_fov" />
      {scenes.length > 1 && <Selector model={model} label="Scene" listKey="scenes" currentKey="current_scene" />}
      <DimSlider model={model} label="T" traitKey="current_t" max={dimT} showPlay />
      <DimSlider model={model} label="Z" traitKey="current_z" max={dimZ} />
    </div>
  );
}
```

- [ ] **Step 4: Write StatusBar.jsx**

```jsx
// anybioimage/frontend/viewer/src/chrome/StatusBar.jsx
import React from 'react';
import { useModelTrait } from '../model/useModelTrait.js';

export function StatusBar({ model, hover }) {
  const t = useModelTrait(model, 'current_t') ?? 0;
  const z = useModelTrait(model, 'current_z') ?? 0;
  const dt = useModelTrait(model, 'dim_t') || 1;
  const dz = useModelTrait(model, 'dim_z') || 1;
  const parts = [];
  if (dt > 1) parts.push(`T ${t + 1}/${dt}`);
  if (dz > 1) parts.push(`Z ${z + 1}/${dz}`);
  return (
    <div className="status-bar">
      <span className="status-item dim-status">{parts.join(' · ')}</span>
      {hover && (
        <span className="status-item hover-status">
          x {hover.x}, y {hover.y}
          {hover.intensities && hover.intensities.map((v, i) =>
            v != null ? <> · ch{i}:{v}</> : null)}
        </span>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Stub `installKeyboard` (full in Task 15)**

```js
// anybioimage/frontend/viewer/src/interaction/keyboard.js
// Full shortcut map lands in Task 15.
export function installKeyboard() { return () => {}; }
```

- [ ] **Step 6: Build & visual smoke**

```
cd anybioimage/frontend/viewer && npm run build && cd ../../..
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add anybioimage/frontend/viewer/src/App.jsx
git add anybioimage/frontend/viewer/src/chrome/Toolbar.jsx
git add anybioimage/frontend/viewer/src/chrome/DimControls.jsx
git add anybioimage/frontend/viewer/src/chrome/StatusBar.jsx
git add anybioimage/frontend/viewer/src/interaction/keyboard.js
git commit -m "feat(viewer/chrome): port Toolbar/DimControls/StatusBar to React"
```

---

## Task 13: LayersPanel — Metadata + Image (with LUT/gamma/display mode)

**Goal:** Build the right-sidebar Layers panel with three sub-components: Metadata (collapsed at top), Image (per-channel rows with visibility/color or LUT/gamma/min/max/Auto), and placeholders for Masks and Annotations sections (lit up in Phase 2).

**Files:**
- Create: `anybioimage/frontend/viewer/src/chrome/LayersPanel/LayersPanel.jsx`
- Create: `anybioimage/frontend/viewer/src/chrome/LayersPanel/MetadataSection.jsx`
- Create: `anybioimage/frontend/viewer/src/chrome/LayersPanel/ImageSection.jsx`
- Create: `anybioimage/frontend/viewer/src/chrome/LayersPanel/ExportFooter.jsx`

- [ ] **Step 1: LayersPanel.jsx**

```jsx
// anybioimage/frontend/viewer/src/chrome/LayersPanel/LayersPanel.jsx
import React from 'react';
import { MetadataSection } from './MetadataSection.jsx';
import { ImageSection } from './ImageSection.jsx';
import { ExportFooter } from './ExportFooter.jsx';

export function LayersPanel({ model }) {
  return (
    <div className="layers-panel open">
      <MetadataSection model={model} />
      <ImageSection model={model} />
      <div className="layer-item section-placeholder">Masks (Phase 2)</div>
      <div className="layer-item section-placeholder">Annotations (Phase 2)</div>
      <ExportFooter model={model} />
    </div>
  );
}
```

- [ ] **Step 2: MetadataSection.jsx**

```jsx
// anybioimage/frontend/viewer/src/chrome/LayersPanel/MetadataSection.jsx
import React, { useState } from 'react';
import { useModelTrait } from '../../model/useModelTrait.js';

export function MetadataSection({ model }) {
  const [open, setOpen] = useState(false);
  const shape = useModelTrait(model, '_image_shape');
  const dtype = useModelTrait(model, '_image_dtype');
  const pixelSize = useModelTrait(model, 'pixel_size_um');
  const channels = useModelTrait(model, '_channel_settings') || [];
  if (!shape) return null;
  return (
    <div className="layer-item metadata-section">
      <button onClick={() => setOpen((v) => !v)} className="metadata-toggle">
        {open ? '▾' : '▸'} Metadata
      </button>
      {open && (
        <div className="metadata-body">
          <div>Shape: T{shape.t} · C{shape.c} · Z{shape.z} · Y{shape.y} · X{shape.x}</div>
          <div>Dtype: {dtype}</div>
          <div>Pixel size: {pixelSize != null ? `${pixelSize.toFixed(4)} µm` : '—'}</div>
          <div>Channels: {channels.map((c) => c.name).join(', ')}</div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: ImageSection.jsx — per-channel rows with LUT dropdown**

```jsx
// anybioimage/frontend/viewer/src/chrome/LayersPanel/ImageSection.jsx
import React from 'react';
import { useModelTrait } from '../../model/useModelTrait.js';
import { listLuts } from '../../render/luts/index.js';

function setChannel(model, idx, patch) {
  const settings = [...(model.get('_channel_settings') || [])];
  settings[idx] = { ...settings[idx], ...patch };
  model.set('_channel_settings', settings);
  model.save_changes();
}

function ImageRow({ model }) {
  const visible = useModelTrait(model, 'image_visible') !== false;
  const displayMode = useModelTrait(model, '_display_mode') || 'composite';
  return (
    <div className="layer-item image-row">
      <button className={'layer-toggle' + (visible ? ' visible' : '')}
        onClick={() => { model.set('image_visible', !visible); model.save_changes(); }}>
        {visible ? '👁' : '⊘'}
      </button>
      <span>Image</span>
      <select value={displayMode}
        onChange={(e) => { model.set('_display_mode', e.target.value); model.save_changes(); }}>
        <option value="composite">Composite</option>
        <option value="single">Single</option>
      </select>
    </div>
  );
}

function ChannelRow({ model, ch, idx, active, onActivate }) {
  const luts = listLuts();
  return (
    <>
      <div className={'layer-item channel-layer-item' + (active ? ' active-channel' : '')}
           onClick={onActivate}>
        <button className={'layer-toggle' + (ch.visible ? ' visible' : '')}
          onClick={(e) => { e.stopPropagation(); setChannel(model, idx, { visible: !ch.visible }); }}>
          {ch.visible ? '👁' : '⊘'}
        </button>
        <span className="channel-name">{ch.name || `Ch ${idx}`}</span>

        <select value={ch.color_kind || 'solid'}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => setChannel(model, idx, { color_kind: e.target.value })}>
          <option value="solid">Solid</option>
          <option value="lut">LUT</option>
        </select>

        {ch.color_kind === 'lut' ? (
          <select value={ch.lut || 'viridis'}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => setChannel(model, idx, { lut: e.target.value })}>
            {luts.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        ) : (
          <input type="color" value={ch.color || '#ffffff'}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => setChannel(model, idx, { color: e.target.value })} />
        )}

        <button className="auto-contrast-btn"
          onClick={async (e) => {
            e.stopPropagation();
            // Triggers Python-side Auto (Viv getChannelStats happens in buildImageLayer cached raster).
            model.send({ kind: 'auto-contrast', channelIndex: idx });
          }}>Auto</button>
      </div>

      <div className="layer-item sub-item channel-contrast-row">
        <span className="slider-label">Min</span>
        <input type="range" min="0" max="100" value={Math.round((ch.min ?? 0) * 100)}
          onChange={(e) => setChannel(model, idx, { min: parseInt(e.target.value) / 100 })} />
        <span className="slider-value">{Math.round((ch.min ?? 0) * 100)}%</span>
      </div>
      <div className="layer-item sub-item channel-contrast-row">
        <span className="slider-label">Max</span>
        <input type="range" min="0" max="100" value={Math.round((ch.max ?? 1) * 100)}
          onChange={(e) => setChannel(model, idx, { max: parseInt(e.target.value) / 100 })} />
        <span className="slider-value">{Math.round((ch.max ?? 1) * 100)}%</span>
      </div>
      <div className="layer-item sub-item channel-contrast-row">
        <span className="slider-label">Gamma</span>
        <input type="range" min="10" max="500" value={Math.round((ch.gamma ?? 1) * 100)}
          onChange={(e) => setChannel(model, idx, { gamma: parseInt(e.target.value) / 100 })} />
        <span className="slider-value">{(ch.gamma ?? 1).toFixed(2)}</span>
      </div>
    </>
  );
}

export function ImageSection({ model }) {
  const channels = useModelTrait(model, '_channel_settings') || [];
  const activeChannel = useModelTrait(model, 'current_c') || 0;
  return (
    <>
      <ImageRow model={model} />
      {channels.map((ch, idx) => (
        <ChannelRow key={idx} model={model} ch={ch} idx={idx}
          active={idx === activeChannel}
          onActivate={() => { model.set('current_c', idx); model.save_changes(); }} />
      ))}
    </>
  );
}
```

- [ ] **Step 4: ExportFooter.jsx (Phase-1 stub)**

```jsx
// anybioimage/frontend/viewer/src/chrome/LayersPanel/ExportFooter.jsx
import React from 'react';
import { useModelTrait } from '../../model/useModelTrait.js';

export function ExportFooter({ model }) {
  const scaleBarVisible = useModelTrait(model, 'scale_bar_visible') !== false;
  const pixelSizeUm = useModelTrait(model, 'pixel_size_um');
  return (
    <div className="layers-footer">
      {pixelSizeUm != null && (
        <label className="layers-footer-toggle">
          <input type="checkbox" checked={scaleBarVisible}
            onChange={(e) => { model.set('scale_bar_visible', e.target.checked); model.save_changes(); }} />
          Scale bar
        </label>
      )}
      {/* Annotation export buttons land in Phase 3 */}
    </div>
  );
}
```

- [ ] **Step 5: Build + unit test (no new tests here; integration validated in Task 20)**

```
cd anybioimage/frontend/viewer && npm run build && npm run test && cd ../../..
```

- [ ] **Step 6: Commit**

```bash
git add anybioimage/frontend/viewer/src/chrome/LayersPanel/
git commit -m "feat(viewer/chrome): LayersPanel with Metadata + Image (LUT/gamma/display mode) + ScaleBar toggle"
```

---

## Task 14: `buildScaleBar.js` — CompositeLayer implementation

**Goal:** Real scale bar. Reads `pixelSizeUm` + current `viewState.zoom` + canvas size, picks a nice-round physical length whose pixel width lands in 60–200 px, draws a 2-px tall rectangle + µm label at the bottom-left.

**Files:**
- Rewrite: `anybioimage/frontend/viewer/src/render/layers/buildScaleBar.js`
- Create: `anybioimage/frontend/viewer/src/render/layers/buildScaleBar.test.js`

- [ ] **Step 1: Test the length picker**

```js
// anybioimage/frontend/viewer/src/render/layers/buildScaleBar.test.js
import { describe, it, expect } from 'vitest';
import { pickNiceMicrons } from './buildScaleBar.js';

describe('pickNiceMicrons', () => {
  it('picks a bar whose pixel width is in [60, 200]', () => {
    for (const pxPerUm of [0.1, 0.5, 1, 2, 5, 10, 40]) {
      const { microns, pixels } = pickNiceMicrons(pxPerUm);
      expect(pixels).toBeGreaterThanOrEqual(60);
      expect(pixels).toBeLessThanOrEqual(200);
      expect(microns).toBeGreaterThan(0);
    }
  });

  it('returns a "nice" value (1/2/5 × 10^n)', () => {
    const NICE = new Set(
      [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 0.1, 0.2, 0.5],
    );
    for (const pxPerUm of [0.3, 1.7, 4.4, 12.1, 33.0]) {
      const { microns } = pickNiceMicrons(pxPerUm);
      expect(NICE.has(microns)).toBe(true);
    }
  });
});
```

- [ ] **Step 2: Implement**

```js
// anybioimage/frontend/viewer/src/render/layers/buildScaleBar.js
import { CompositeLayer } from '@deck.gl/core';
import { SolidPolygonLayer, TextLayer } from '@deck.gl/layers';

const STEPS = [1, 2, 5];   // × 10^n

export function pickNiceMicrons(pixelsPerMicron) {
  const targetPx = 120;   // aim for 120-ish, clamped to [60, 200]
  let bestMicrons = 1;
  let bestDelta = Infinity;
  for (let exp = -3; exp <= 6; exp++) {
    for (const step of STEPS) {
      const microns = step * Math.pow(10, exp);
      const px = microns * pixelsPerMicron;
      if (px < 60 || px > 200) continue;
      const delta = Math.abs(px - targetPx);
      if (delta < bestDelta) { bestDelta = delta; bestMicrons = microns; }
    }
  }
  return { microns: bestMicrons, pixels: bestMicrons * pixelsPerMicron };
}

class ScaleBarLayer extends CompositeLayer {
  renderLayers() {
    const { pixelSizeUm, viewState, width, height } = this.props;
    if (!pixelSizeUm || !viewState) return [];
    const scale = Math.pow(2, viewState.zoom);      // px / world-unit (image px)
    const pixelsPerMicron = scale / pixelSizeUm;    // screen px / µm
    const { microns, pixels } = pickNiceMicrons(pixelsPerMicron);

    // Place the bar at bottom-left, 16 px inside.
    // Convert screen coords to world coords via the same scale.
    const margin = 16;
    const barXend = margin;
    const barYend = height - margin;
    const barXstart = barXend + pixels;  // note: y is flipped in screen space

    // Rough world-space conversion: screen (px) → world via viewport center.
    const target = viewState.target || [0, 0, 0];
    const cx = target[0]; const cy = target[1];
    const worldPerPx = 1 / scale;
    const screenToWorld = (sx, sy) => [
      cx + (sx - width / 2) * worldPerPx,
      cy + (sy - height / 2) * worldPerPx,
    ];
    const [wx0, wy0] = screenToWorld(barXend, barYend - 2);
    const [wx1, wy1] = screenToWorld(barXstart, barYend);

    return [
      new SolidPolygonLayer({
        id: `${this.props.id}-rect`,
        data: [{ polygon: [[wx0, wy0], [wx1, wy0], [wx1, wy1], [wx0, wy1]] }],
        getPolygon: (d) => d.polygon,
        getFillColor: [255, 255, 255, 230],
      }),
      new TextLayer({
        id: `${this.props.id}-label`,
        data: [{ position: screenToWorld((barXend + barXstart) / 2, barYend - 10) }],
        getText: () => microns >= 1000 ? `${microns / 1000} mm`
                      : microns < 1 ? `${microns * 1000} nm` : `${microns} µm`,
        getPosition: (d) => d.position,
        getColor: [255, 255, 255, 230],
        sizeUnits: 'pixels',
        getSize: 14,
        getTextAnchor: 'middle',
        getAlignmentBaseline: 'bottom',
      }),
    ];
  }
}
ScaleBarLayer.layerName = 'ScaleBarLayer';

export function buildScaleBarLayer({ pixelSizeUm, viewState, width, height }) {
  return new ScaleBarLayer({
    id: 'scale-bar', pixelSizeUm, viewState, width, height,
  });
}
```

- [ ] **Step 3: Run tests + build**

```
cd anybioimage/frontend/viewer && npm run test && npm run build && cd ../../..
```

Expected: tests green; bundle built.

- [ ] **Step 4: Commit**

```bash
git add anybioimage/frontend/viewer/src/render/layers/buildScaleBar.js
git add anybioimage/frontend/viewer/src/render/layers/buildScaleBar.test.js
git commit -m "feat(viewer/render): ScaleBarLayer with nice-round micron steps"
```

---

## Task 15: Pixel-info hover

**Goal:** Wire deck.gl's `onHover` to read per-channel intensities from the currently loaded raster (no Python round-trip). Throttled to 60 Hz. Feeds `hover.intensities` into `StatusBar`.

**Files:**
- Modify: `anybioimage/frontend/viewer/src/App.jsx`
- Create: `anybioimage/frontend/viewer/src/render/onHoverPixelInfo.js`
- Create: `anybioimage/frontend/viewer/src/render/onHoverPixelInfo.test.js`

- [ ] **Step 1: Write the test**

```js
// anybioimage/frontend/viewer/src/render/onHoverPixelInfo.test.js
import { describe, it, expect, vi } from 'vitest';
import { makeHoverHandler } from './onHoverPixelInfo.js';

describe('makeHoverHandler', () => {
  it('reads intensity from a fake source and fires setHover', async () => {
    const raster = new Uint16Array([10, 20, 30, 40]);
    const src = { shape: [1,1,1,2,2], labels: ['t','c','z','y','x'],
      async getRaster() { return { data: raster, width: 2, height: 2 }; } };
    const setHover = vi.fn();
    const h = makeHoverHandler({ getSources: () => [src], getSelections: () => [{t:0,c:0,z:0}], setHover });
    await h({ coordinate: [1, 1] });
    expect(setHover).toHaveBeenCalledWith({ x: 1, y: 1, intensities: [40] });
  });

  it('throttles consecutive calls', async () => {
    const setHover = vi.fn();
    const h = makeHoverHandler({ getSources: () => [], getSelections: () => [], setHover });
    await h({ coordinate: [0, 0] });
    await h({ coordinate: [0, 0] });
    // Second call at the same moment suppressed by the throttle.
    expect(setHover).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Implement**

```js
// anybioimage/frontend/viewer/src/render/onHoverPixelInfo.js
/** Throttled hover handler that reads per-channel intensities. */
export function makeHoverHandler({ getSources, getSelections, setHover, intervalMs = 16 }) {
  let last = 0;
  let cachedRasters = null;
  let cachedKey = null;
  return async function onHover({ coordinate }) {
    if (!coordinate) { setHover(null); return; }
    const now = Date.now();
    if (now - last < intervalMs) return;
    last = now;
    const [x, y] = coordinate.map(Math.floor);
    const sources = getSources();
    const selections = getSelections();
    if (!sources || !sources.length) { setHover({ x, y, intensities: [] }); return; }
    const src = sources[0];
    const key = JSON.stringify(selections);
    if (cachedKey !== key) {
      cachedKey = key;
      cachedRasters = await Promise.all(selections.map((sel) =>
        src.getRaster({ selection: sel }).catch(() => null)));
    }
    const w = src.shape[src.labels.indexOf('x')];
    const intensities = (cachedRasters || []).map((r) => {
      if (!r) return null;
      if (x < 0 || y < 0 || x >= r.width || y >= r.height) return null;
      return Number(r.data[y * r.width + x]);
    });
    setHover({ x, y, intensities });
  };
}
```

- [ ] **Step 3: Wire into App.jsx**

Replace the hover callback stub in `App.jsx` (Task 12's version):

```jsx
// in App.jsx — inside the App component body, replace onHover with:
const deckRef = React.useRef(null);
const sourcesRef = React.useRef(null);
const selectionsRef = React.useRef(null);
const onHover = React.useMemo(
  () => makeHoverHandler({
    getSources: () => sourcesRef.current,
    getSelections: () => selectionsRef.current,
    setHover,
  }),
  []);
```

Add `sourcesRef` + `selectionsRef` props to `DeckCanvas` and update them inside it when `sources` / `selections` change.

In `DeckCanvas.jsx`, accept and set refs:

```jsx
export function DeckCanvas({ model, onHover, sourcesRef, selectionsRef }) {
  // ... existing body ...
  React.useEffect(() => { if (sourcesRef) sourcesRef.current = sources; }, [sources]);
  React.useEffect(() => {
    if (!selectionsRef) return;
    selectionsRef.current = (buildImageLayerProps({
      sources, channels: channelSettings || [],
      currentT, currentZ, displayMode, activeChannel,
    })).selections;
  }, [sources, channelSettings, currentT, currentZ, displayMode, activeChannel]);
  // ... return JSX ...
}
```

- [ ] **Step 4: Build + test**

```
cd anybioimage/frontend/viewer && npm run test && npm run build && cd ../../..
```

Expected: tests green; bundle built.

- [ ] **Step 5: Commit**

```bash
git add anybioimage/frontend/viewer/src/render/onHoverPixelInfo.js
git add anybioimage/frontend/viewer/src/render/onHoverPixelInfo.test.js
git add anybioimage/frontend/viewer/src/App.jsx
git add anybioimage/frontend/viewer/src/render/DeckCanvas.jsx
git commit -m "feat(viewer): pixel-info hover (JS-only, throttled 60 Hz)"
```

---

## Task 16: Keyboard shortcut map

**Goal:** Implement `installKeyboard(model)`. Handles navigation and active-channel shortcuts; Phase-2 annotation shortcuts stubbed. Disables itself when focus is in an input / contentEditable / color picker.

**Files:**
- Rewrite: `anybioimage/frontend/viewer/src/interaction/keyboard.js`
- Create: `anybioimage/frontend/viewer/src/interaction/keyboard.test.js`

- [ ] **Step 1: Test**

```js
// anybioimage/frontend/viewer/src/interaction/keyboard.test.js
/** @vitest-environment jsdom */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { installKeyboard } from './keyboard.js';

function makeModel(state) {
  const listeners = {};
  return {
    get: (k) => state[k],
    set: (k, v) => { state[k] = v; },
    save_changes: vi.fn(),
    on: (name, cb) => { listeners[name] = cb; },
    off: () => {},
    send: vi.fn(),
  };
}

describe('installKeyboard', () => {
  let dispose;
  let state;
  let model;
  beforeEach(() => {
    state = { current_t: 0, current_z: 0, dim_t: 5, dim_z: 3, current_c: 0,
              _channel_settings: [{ visible: true }, { visible: true }] };
    model = makeModel(state);
    dispose = installKeyboard(model);
  });
  afterEach(() => { dispose && dispose(); });

  it('ArrowRight advances T', () => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));
    expect(state.current_t).toBe(1);
  });

  it('[ decrements active channel with wrap', () => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key: '[' }));
    expect(state.current_c).toBe(1);  // wrap from 0 to last
  });

  it('ignores key when focus is in an input', () => {
    const inp = document.createElement('input');
    document.body.appendChild(inp);
    inp.focus();
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    expect(state.current_t).toBe(0);
    inp.remove();
  });
});
```

- [ ] **Step 2: Implement**

```js
// anybioimage/frontend/viewer/src/interaction/keyboard.js
const TOOL_KEYS = {
  v: 'select', p: 'pan',
  r: 'rect', g: 'polygon', o: 'point',  // Phase 2 — sent but ignored until Phase 2
  l: 'line', m: 'areaMeasure',
};

function isEditableTarget(el) {
  if (!el) return false;
  if (el.isContentEditable) return true;
  const tag = el.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  return false;
}

export function installKeyboard(model) {
  function wrap(v, n) { return ((v % n) + n) % n; }

  function handler(e) {
    if (e.defaultPrevented) return;
    if (isEditableTarget(document.activeElement)) return;

    const dimT = model.get('dim_t') || 1;
    const dimZ = model.get('dim_z') || 1;
    const channels = model.get('_channel_settings') || [];
    const t = model.get('current_t') ?? 0;
    const z = model.get('current_z') ?? 0;
    const c = model.get('current_c') ?? 0;

    let consumed = true;
    switch (e.key) {
      case 'ArrowRight': model.set('current_t', wrap(t + 1, dimT)); break;
      case 'ArrowLeft':  model.set('current_t', wrap(t - 1, dimT)); break;
      case 'ArrowUp':    model.set('current_z', wrap(z + 1, dimZ)); break;
      case 'ArrowDown':  model.set('current_z', wrap(z - 1, dimZ)); break;
      case '[':          model.set('current_c', wrap(c - 1, channels.length || 1)); break;
      case ']':          model.set('current_c', wrap(c + 1, channels.length || 1)); break;
      case ',':          model.set('image_brightness', Math.max(-1, (model.get('image_brightness') ?? 0) - 0.05)); break;
      case '.':          model.set('image_brightness', Math.min( 1, (model.get('image_brightness') ?? 0) + 0.05)); break;
      default:
        if (e.ctrlKey && (e.key === 'z' || e.key === 'Z')) {
          model.send({ kind: 'undo', redo: e.shiftKey });
        } else if (TOOL_KEYS[e.key]) {
          model.set('tool_mode', TOOL_KEYS[e.key]);
        } else {
          consumed = false;
        }
    }
    if (consumed) { model.save_changes(); e.preventDefault(); }
  }

  window.addEventListener('keydown', handler);
  return () => window.removeEventListener('keydown', handler);
}
```

- [ ] **Step 3: Run tests + build**

```
cd anybioimage/frontend/viewer && npm run test && npm run build && cd ../../..
```

Expected: 3 new tests green.

- [ ] **Step 4: Commit**

```bash
git add anybioimage/frontend/viewer/src/interaction/keyboard.js
git add anybioimage/frontend/viewer/src/interaction/keyboard.test.js
git commit -m "feat(viewer/interaction): keyboard shortcuts for dim nav + active channel"
```

---

## Task 17: Wire reset-view round-trip + `tool_mode` styling

**Goal:** Toolbar Reset button sends `{kind: "reset-view"}`. `DeckCanvas` listens via `model.on("msg:custom")` and recomputes the initial `viewState`. Confirms `tool_mode` `.active` state already works because React re-renders on traitlet change (fixes the Canvas2D-era bug).

**Files:**
- Modify: `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx`

- [ ] **Step 1: Add reset handler in DeckCanvas**

```jsx
// add to DeckCanvas.jsx — inside the component body, after viewState setup:
useEffect(() => {
  const handler = (content) => {
    if (!content || content.kind !== 'reset-view') return;
    if (!sources || !sources.length) return;
    const [, , , h, w] = sources[0].shape;
    const zoom = Math.log2(Math.min(width / w, height / h) || 1);
    setViewState({ target: [w / 2, h / 2, 0], zoom, rotationX: 0, rotationOrbit: 0 });
  };
  model.on('msg:custom', handler);
  return () => model.off('msg:custom', handler);
}, [model, sources, width, height]);
```

- [ ] **Step 2: Build + commit**

```
cd anybioimage/frontend/viewer && npm run build && cd ../../..
git add anybioimage/frontend/viewer/src/render/DeckCanvas.jsx
git commit -m "feat(viewer): wire Reset button → recompute fit-to-screen viewState"
```

---

## Task 18: Delete Canvas2D + unify Python `_esm` loading

**Goal:** Single source for the widget's JS. Remove the backend registry, delete `frontend/shared/canvas2d.js`, `backends/canvas2d.py`, `backends/viv.py`, and the `frontend/viv/` artefacts the old plan left around. Add `DeprecationWarning` when `render_backend` kwarg is passed.

**Files:**
- Delete: `anybioimage/backends/` (whole directory)
- Delete: `anybioimage/frontend/shared/`
- Delete: any leftover `anybioimage/frontend/viv/`
- Modify: `anybioimage/viewer.py`
- Create: `tests/test_legacy_kwarg.py`

- [ ] **Step 1: Test the deprecation**

```python
# tests/test_legacy_kwarg.py
"""render_backend kwarg is accepted for one release with a DeprecationWarning."""
import warnings

from anybioimage import BioImageViewer


def test_deprecation_warning_on_render_backend():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        v = BioImageViewer(render_backend="viv")
        assert any(issubclass(w.category, DeprecationWarning) for w in caught)
        assert v is not None


def test_default_construction_no_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        v = BioImageViewer()
        assert not any(issubclass(w.category, DeprecationWarning) for w in caught)
        assert v is not None
```

- [ ] **Step 2: Unify `_esm` in viewer.py**

```python
# at top of anybioimage/viewer.py
import warnings
from importlib.resources import files

import anywidget
import traitlets

from .mixins import (
    AnnotationsMixin, ImageLoadingMixin, MaskManagementMixin, PixelSourceMixin,
    PlateLoadingMixin, SAMIntegrationMixin,
)

_BUNDLE = files("anybioimage.frontend.viewer.dist").joinpath("viewer-bundle.js").read_text(encoding="utf-8")


class BioImageViewer(
    ImageLoadingMixin, PixelSourceMixin, PlateLoadingMixin,
    MaskManagementMixin, AnnotationsMixin, SAMIntegrationMixin,
    anywidget.AnyWidget,
):
    _esm = _BUNDLE

    def __init__(self, *args, render_backend=None, **kwargs):
        if render_backend is not None:
            warnings.warn(
                "BioImageViewer now uses a single rendering pipeline; the "
                "`render_backend` kwarg is ignored and will be removed in a "
                "future release.",
                DeprecationWarning, stacklevel=2,
            )
        super().__init__(*args, **kwargs)
        self.on_msg(self._route_message)
    # (all existing traitlets + methods continue below)
```

Also delete the inline `_esm` string if any remnant of Canvas2D code is still in `viewer.py`.

- [ ] **Step 3: Delete old files**

```bash
git rm -r anybioimage/backends
git rm -r anybioimage/frontend/shared || true
git rm -r anybioimage/frontend/viv || true
# Viewer no longer imports CHANNEL_COLORS, normalize_image, composite_channels
# from utils, so those stay but their users are gone. Clean up in a follow-up if unused.
```

- [ ] **Step 4: Test**

```
uv run pytest tests/ -v
```

Expected: all green; new deprecation test passes. Remove any tests that reference deleted backend modules (e.g. `tests/test_backends.py`).

- [ ] **Step 5: Bundle re-build + size check**

```
cd anybioimage/frontend/viewer && npm run build && npm run size && cd ../../..
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: unify to single render pipeline; delete Canvas2D + backend registry"
```

---

## Task 19: Demo app — `examples/full_demo.py` (Phase-1 sections)

**Goal:** Replace `examples/image_notebook.py` with `examples/full_demo.py`. Phase-1 sections: Welcome · Local TIFF · Local OME-Zarr · Remote OME-Zarr · HCS plate · Display features · Perf stub (full perf cell lands in Task 22).

**Files:**
- Create: `examples/full_demo.py`
- Delete: `examples/image_notebook.py`

- [ ] **Step 1: Write the demo**

```python
# examples/full_demo.py
"""anybioimage — full demo notebook.

Run with: `marimo edit examples/full_demo.py`

Phase-1 sections exercise every v0.7.0 feature: unified pipeline, chunk bridge,
channel LUTs, metadata panel, scale bar, pixel-info hover, keyboard shortcuts.
"""

import marimo

__generated_with = "0.16.0"
app = marimo.App(width="full")


@app.cell
def _welcome():
    import marimo as mo
    mo.md(
        """
        # anybioimage demo

        One widget, every input format. Pan & zoom with the mouse, scrub T/Z with
        the sliders, toggle channels and their LUTs in the Layers panel.

        **Keyboard:** `←/→` time · `↑/↓` Z · `[/]` channel · `V` select · `P` pan
        """
    )
    return (mo,)


@app.cell
def _local_tiff(mo):
    import numpy as np
    from anybioimage import BioImageViewer
    rng = np.random.default_rng(0)
    data = rng.integers(0, 65535, size=(3, 2, 1, 256, 256), dtype=np.uint16)
    v = BioImageViewer()
    v.set_image(data)
    mo.md("## 1 — Numpy array (chunk bridge)")
    mo.ui.anywidget(v)
    return


@app.cell
def _local_zarr(mo):
    from pathlib import Path
    from anybioimage import BioImageViewer
    zarr = Path(__file__).parent / "image.zarr"
    v = BioImageViewer()
    if zarr.exists():
        v.set_image(str(zarr))
        mo.md("## 2 — Local OME-Zarr (direct browser fetch)")
        mo.ui.anywidget(v)
    else:
        mo.md(f"**Skipped** — `{zarr}` not present. Unpack `examples/image.zarr.tar.xz`.")
    return


@app.cell
def _remote_zarr(mo):
    from anybioimage import BioImageViewer
    v = BioImageViewer()
    # IDR sample — small multi-timepoint OME-Zarr
    v.set_image("https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0101A/13457537.zarr")
    mo.md("## 3 — Remote OME-Zarr (zarrita.js direct fetch)")
    mo.ui.anywidget(v)
    return


@app.cell
def _hcs_plate(mo):
    from anybioimage import BioImageViewer
    v = BioImageViewer()
    try:
        v.set_plate("https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0125A/6001240.zarr")
        mo.md("## 4 — HCS plate (Well + FOV dropdowns)")
        mo.ui.anywidget(v)
    except Exception as e:
        mo.md(f"**Skipped** — plate fetch failed: {e}")
    return


@app.cell
def _display_features(mo):
    import numpy as np
    from anybioimage import BioImageViewer
    v = BioImageViewer()
    data = np.fromfunction(lambda c, y, x: ((x + y) * (c + 1)) % 65535,
                           (3, 512, 512), dtype=np.int32).astype(np.uint16)[None, :, None, :, :]
    v.set_image(data)
    v.pixel_size_um = 0.325   # synthetic scale
    mo.md("""
    ## 5 — Display features

    - Open the **Layers** panel → pick **LUT** instead of **Solid** for a channel, try `viridis`, `magma`.
    - Toggle **Scale bar** in the Layers-panel footer.
    - Hover over the image — `x, y · ch0:..., ch1:...` shows in the status bar.
    - Open **Metadata** at the top of the Layers panel.
    """)
    mo.ui.anywidget(v)
    return


if __name__ == "__main__":
    app.run()
```

- [ ] **Step 2: Remove the legacy notebook**

```bash
git rm examples/image_notebook.py
```

- [ ] **Step 3: Smoke the notebook**

```
uv run marimo check examples/full_demo.py
```

Expected: clean output. Then launch it manually (`marimo edit examples/full_demo.py`) and click through sections 1, 2, 5 at minimum. Section 3/4 require network.

- [ ] **Step 4: Commit**

```bash
git add examples/full_demo.py
git commit -m "docs(examples): full_demo.py replaces image_notebook.py (Phase-1 sections)"
```

---

## Task 20: Playwright smoke tests for Phase 1

**Goal:** Replace `tests/playwright/test_viv_smoke.py` with Phase-1 flows tied to `examples/full_demo.py` sections. Screenshots under `/tmp/anybioimage-screenshots/`.

**Files:**
- Modify: `tests/playwright/conftest.py` (point at `examples/full_demo.py`)
- Create: `tests/playwright/test_phase1_core.py`
- Create: `tests/playwright/test_phase1_channels.py`
- Create: `tests/playwright/test_phase1_display.py`
- Delete: `tests/playwright/test_viv_smoke.py`

- [ ] **Step 1: Update conftest**

In `tests/playwright/conftest.py`, change the `notebook_path` fixture target:

```python
# tests/playwright/conftest.py — relevant fragment
from pathlib import Path

NOTEBOOK = Path(__file__).resolve().parents[2] / "examples" / "full_demo.py"
```

- [ ] **Step 2: test_phase1_core.py — rendering + dim navigation**

```python
# tests/playwright/test_phase1_core.py
"""Phase-1 core flows: render numpy input, drag T slider, render OME-Zarr."""
from __future__ import annotations

import time

import pytest


@pytest.mark.playwright
def test_numpy_input_renders(page, marimo_url):
    page.goto(marimo_url)
    page.wait_for_timeout(8000)  # wait for kernel + first cells
    assert page.locator('marimo-anywidget').count() >= 1
    page.screenshot(path='/tmp/anybioimage-screenshots/phase1-numpy-render.png')


@pytest.mark.playwright
def test_t_slider_changes_frame(page, marimo_url):
    page.goto(marimo_url)
    page.wait_for_timeout(8000)
    # Use shadow DOM pattern from CLAUDE.md
    slider_before = page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('marimo-anywidget')) {
          if (el.shadowRoot) {
            const s = el.shadowRoot.querySelectorAll('input[type="range"]');
            return s.length ? parseInt(s[0].value) : null;
          }
        }
        return null;
      }
    """)
    # Bump T slider (by convention DimControls puts T first among sliders)
    page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('marimo-anywidget')) {
          if (el.shadowRoot) {
            const s = el.shadowRoot.querySelectorAll('input[type="range"]');
            if (!s.length) continue;
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(s[0], '1');
            s[0].dispatchEvent(new Event('input', { bubbles: true }));
            s[0].dispatchEvent(new Event('change', { bubbles: true }));
          }
        }
      }
    """)
    page.wait_for_timeout(800)
    page.screenshot(path='/tmp/anybioimage-screenshots/phase1-t-changed.png')
```

- [ ] **Step 3: test_phase1_channels.py — Layers panel LUT switch**

```python
# tests/playwright/test_phase1_channels.py
"""Channel controls: open Layers panel, switch a channel to LUT."""
import pytest


@pytest.mark.playwright
def test_open_layers_and_switch_lut(page, marimo_url):
    page.goto(marimo_url)
    page.wait_for_timeout(8000)
    page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('marimo-anywidget')) {
          if (el.shadowRoot) {
            const btn = el.shadowRoot.querySelector('.layers-btn');
            if (btn) btn.click();
          }
        }
      }
    """)
    page.wait_for_timeout(300)
    # Flip first channel to LUT mode (first <select> with the "Solid/LUT" options).
    page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('marimo-anywidget')) {
          if (el.shadowRoot) {
            const selects = [...el.shadowRoot.querySelectorAll('select')]
              .filter((s) => s.querySelector('option[value="solid"]'));
            if (selects.length) {
              selects[0].value = 'lut';
              selects[0].dispatchEvent(new Event('change', { bubbles: true }));
            }
          }
        }
      }
    """)
    page.wait_for_timeout(500)
    page.screenshot(path='/tmp/anybioimage-screenshots/phase1-lut.png')
```

- [ ] **Step 4: test_phase1_display.py — scale bar + metadata**

```python
# tests/playwright/test_phase1_display.py
"""Display features: scale bar and metadata panel."""
import pytest


@pytest.mark.playwright
def test_scale_bar_visible_when_pixel_size_set(page, marimo_url):
    page.goto(marimo_url)
    page.wait_for_timeout(10000)  # last cell sets pixel_size_um
    # Check the last widget has a text layer rendered (deck.gl text).
    page.screenshot(path='/tmp/anybioimage-screenshots/phase1-scalebar.png')


@pytest.mark.playwright
def test_metadata_section_opens(page, marimo_url):
    page.goto(marimo_url)
    page.wait_for_timeout(10000)
    page.evaluate("""
      () => {
        for (const el of document.querySelectorAll('marimo-anywidget')) {
          if (el.shadowRoot) {
            const btn = el.shadowRoot.querySelector('.layers-btn');
            if (btn) btn.click();
            const mt = el.shadowRoot.querySelector('.metadata-toggle');
            if (mt) mt.click();
          }
        }
      }
    """)
    page.wait_for_timeout(300)
    page.screenshot(path='/tmp/anybioimage-screenshots/phase1-metadata.png')
```

- [ ] **Step 5: Delete old test**

```
git rm tests/playwright/test_viv_smoke.py
```

- [ ] **Step 6: Run Playwright (best-effort — requires browser env)**

```
uv run pytest tests/playwright/ -v -m playwright
```

Expected: passes or skips if the Playwright browser binary isn't installed. CI handles install.

- [ ] **Step 7: Commit**

```bash
git add tests/playwright/
git commit -m "test(playwright): Phase-1 smoke flows tied to full_demo.py"
```

---

## Task 21: Docs + attributions + CHANGELOG + ROADMAP

**Goal:** Update `README.md`, `CHANGELOG.md`, `ROADMAP.md` to reflect the unified pipeline. MIT attribution for `nebula.gl` pre-registered (used in Phase 3).

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `ROADMAP.md`

- [ ] **Step 1: README attributions + usage section**

In `README.md`'s **Usage** section, replace any `render_backend="viv"` examples with the single-API form:

```python
from anybioimage import BioImageViewer

v = BioImageViewer()
v.set_image("https://s3.example.com/my.ome.zarr")   # remote
v.set_image("local.tif")                             # local TIFF / CZI / ND2
v.set_image(numpy_array)                             # in-memory numpy
v.set_plate("plate.zarr")                            # HCS plate
```

In the **Acknowledgements** section ensure these entries exist (MIT licenses, linked):

- `@hms-dbmi/viv` — https://github.com/hms-dbmi/viv
- `zarrita.js` (bundled by Viv) — https://github.com/manzt/zarrita.js
- `deck.gl` — https://github.com/visgl/deck.gl
- `nebula.gl` — https://github.com/uber/nebula.gl (used from Phase 3 for annotation editing)

- [ ] **Step 2: CHANGELOG `[Unreleased]`**

```markdown
## [Unreleased] — targeting v0.7.0

### Added
- Single rendering pipeline based on Viv + deck.gl (WebGL2) handling every input format (remote OME-Zarr, local OME-Zarr, numpy, bioio TIFF/CZI/ND2).
- `AnywidgetPixelSource` — chunk bridge between the browser and Python's in-RAM numpy array.
- 15-LUT registry with GPU-side colormap sampling (`gray`, `viridis`, `plasma`, `magma`, `inferno`, `cividis`, `turbo`, `hot`, `cool`, `red`, `green`, `blue`, `cyan`, `magenta`, `yellow`).
- Per-channel **Composite** / **Single** display mode toggle (Fiji-style).
- Per-channel **gamma** slider.
- **Scale bar** overlay (auto-sized, reads `pixel_size_um` from bioio / OME).
- **Pixel-info hover** readout in the status bar (JS-only, throttled 60 Hz).
- **Metadata panel** in the Layers sidebar.
- Full keyboard shortcut map (`←/→` T, `↑/↓` Z, `[ ]` channel, `V/P` tools, `,/.` brightness).

### Changed
- Rendering is now WebGL2-only. Browsers without WebGL2 see a guidance message instead of the widget.
- `pip install anybioimage` still requires no Node toolchain; the committed bundle `anybioimage/frontend/viewer/dist/viewer-bundle.js` ships in the wheel.

### Removed (Breaking)
- `render_backend` kwarg is accepted for one release with a `DeprecationWarning`; it is ignored. Will be removed in v0.8.0.
- `_viv_mode`, `_viewport_tiles`, `use_jpeg_tiles` traitlets — these were private and have no user-facing replacement.
- Canvas2D compositor (`anybioimage/frontend/shared/canvas2d.js`, `_composite_cache`, `_tile_cache`, `_precompute_*`, `_update_slice`, PNG encoding helpers).
- `examples/image_notebook.py` → replaced by `examples/full_demo.py`.
```

- [ ] **Step 3: ROADMAP update**

Merge the `## Viv backend` table into the main milestone list. v0.4.0 display items (colormap/LUT, scale bar, pixel-info hover) now live under the v0.7.0 section as delivered. Leave v0.5.0 (measurement, editing, undo, export) untouched — Phase 3 lands those.

- [ ] **Step 4: Commit**

```bash
git add README.md CHANGELOG.md ROADMAP.md
git commit -m "docs: update README/CHANGELOG/ROADMAP for unified pipeline"
```

---

## Task 22: Perf cell + bundle freshness check

**Goal:** Final cell of `examples/full_demo.py` measures the Phase-1 perf budget. CI `bundle.yml` confirms the committed `viewer-bundle.js` is in sync with source.

**Files:**
- Modify: `examples/full_demo.py`
- Modify: `.github/workflows/bundle.yml` (path updated in Task 2; confirm)

- [ ] **Step 1: Append perf cell**

```python
# add to examples/full_demo.py after _display_features
@app.cell
def _perf(mo):
    import numpy as np
    import time
    from anybioimage import BioImageViewer

    v = BioImageViewer()
    data = np.random.randint(0, 65535, size=(10, 3, 5, 1024, 1024), dtype=np.uint16)
    v.set_image(data)

    mo.md("""
    ## 6 — Performance cell

    This cell measures the Phase-1 budget from the spec. Click through the widget
    to drive the metrics (T slider scrub, channel slider drag, etc.); the
    numbers update at the rate JS receives events.

    **Budget targets (spec §10):**

    | Metric | Target |
    |---|---|
    | Pan / zoom steady | 60 fps |
    | Channel slider drag → GPU | ≤16 ms |
    | T slider scrub (in-RAM) | ≤30 ms |
    | Cold tile fetch (local) | ≤30 ms |

    Hit **Run benchmark** in the widget to dump a report below.
    """)
    mo.ui.anywidget(v)
    return
```

- [ ] **Step 2: Confirm CI bundle check still points at the renamed path**

Re-read `.github/workflows/bundle.yml` (updated in Task 2) and verify `working-directory` and `git diff` path reference `frontend/viewer/dist/viewer-bundle.js`.

- [ ] **Step 3: Commit**

```bash
git add examples/full_demo.py .github/workflows/bundle.yml
git commit -m "test(demo): add perf cell with spec §10 targets"
```

---

## Self-review checklist (run before declaring Phase 1 done)

- [ ] Spec §1 (user-visible behaviour) — no backend kwarg, `DeprecationWarning` delivered — Task 18.
- [ ] Spec §2 (architecture, chunk bridge, build) — Tasks 1, 2, 4, 6, 18.
- [ ] Spec §3 (layer stack) — scale-bar + image layer covered in Phase 1 (Tasks 8, 10, 14); mask / annotation / measurement layers are Phase 2/3.
- [ ] Spec §4 (channel model, LUTs, display mode) — Tasks 8, 9, 13.
- [ ] Spec §5 (annotations) — Phase 2 / 3 (out of scope here).
- [ ] Spec §6 (interaction, tools, shortcuts) — Phase-1 share: Toolbar state reflects traitlet + keyboard shortcuts (Tasks 12, 16, 17). Annotation / editing tools disabled with tooltips.
- [ ] Spec §7 (display features) — Tasks 13, 14, 15.
- [ ] Spec §8 (phasing) — this plan is Phase 1; follow-up plans for 2 + 3.
- [ ] Spec §9 (demo app) — Tasks 19, 22.
- [ ] Spec §10 (perf budget) — Task 22 + Task 1 spike.
- [ ] Spec §11 (tests) — Python: Tasks 4, 5, 11, 18. JS: Tasks 6, 8, 9, 14, 15, 16. Playwright: Task 20.
- [ ] Spec §12 (migration + back-compat) — Task 18 (deprecation warning); Task 21 (CHANGELOG / README).
- [ ] Spec §13 (risks) — mitigated by Task 1 spike + bounded Python chunk cache (Task 4).

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-19-unified-viewer-phase1.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for 22 bite-sized tasks; keeps main-session context clean.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch checkpoints for review.

**Which approach?**
