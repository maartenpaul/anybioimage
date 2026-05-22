# BioImageViewer — Phase 2.5 Hardening + Integration Test Tier — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**This is Phase 2.5 of 3.** It sits between the Phase 2 "Annotate MVP" and the Phase 3 editing/measurement/undo/export work. Phase 3 is blocked on the Phase 2.5 acceptance gate landing green.

**Goal (Phase 2.5):** Harden the unified viewer to ship-quality. Root-cause-fix the correctness, performance, isolation, and UX-polish issues surfaced during the Phase-2 browser run. Install a durable integration-test tier (`tests/integration/`) so future regressions fail a test rather than a user report.

**Guiding principle:** "Doing business" — no shortcut patches, no silenced warnings, no `xfail` to hide a failure, no TODO comments hiding known issues. Every perf fix ships with measured before/after numbers. Every correctness fix ships with a failing-then-passing integration test.

**Architecture:** Phase 2.5 is purely additive + refactor on top of the Phase 2 codebase. Three new concerns are introduced:
1. A `src/util/perf.js` instrumentation module, gated by `window.__ANYBIOIMAGE_PERF`, wired into four hot paths.
2. A third testing tier under `tests/integration/`, driven by Playwright + marimo, reading model traitlets back through `wait_for_ready` and asserting perf budgets.
3. UX polish components (`chrome/icons.js`, `chrome/NumericInput.jsx`) and scoped-per-widget keyboard handling.

**Tech Stack:** Python anywidget + traitlets · React 18 · `@deck.gl/layers` · `@hms-dbmi/viv` 0.17 · esbuild · `vitest` (JS unit) · `pytest` (Python unit) · Playwright (integration tier) · `performance.now()` + `PerformanceObserver` (perf instrumentation).

**Spec:** [docs/superpowers/specs/2026-04-19-phase2-5-hardening-design.md](../specs/2026-04-19-phase2-5-hardening-design.md) — sections referenced as `[spec §N]`. Phase 2.5 covers all 11 spec sections.

---

## Starting point

Phase 2 has merged into `feature/viv-backend`. The widget renders images, annotations (rect / polygon / point), mask overlays via `BitmapLayer`, SAM-hookup; `InteractionController` is wired; `LayersPanel` has `MasksSection` and `AnnotationsSection`; `examples/full_demo.py` walks through sections 1–8. But:

- `InteractionController._ctx = { model, controller: this }` does not expose `pickObject` — Select tool is broken.
- `installKeyboard(model)` attaches to `window` — two widgets on a page fight each other.
- Remote OME-Zarr input loads the pixel-source but the canvas stays black; root cause unknown.
- Monolithic `layers` useMemo rebuilds all layers on every `_channel_settings` change.
- No pre-fetch on T/Z scrub settle.
- Toolbar buttons display single-letter text (P / V / ▭ / ⬡ / •).
- Channel min/max sliders have no numeric entry; gamma has no reset button.
- Play button always visible, no perf gating.
- Min/max shown as `%` only.
- No integration tests — Playwright tier in `tests/playwright/` is smoke-screenshot only.

Each task starts from the previous task's end state on `feature/viv-backend`. Commits accumulate on that branch until Phase 2.5 is ready to merge.

---

## File structure (Phase 2.5)

**New files:**

- `anybioimage/frontend/viewer/src/util/perf.js` — instrumentation primitives (`mark`, `measure`, `trace`, `getPerfReport`, `clearPerf`)
- `anybioimage/frontend/viewer/src/util/perf.test.js`
- `anybioimage/frontend/viewer/src/chrome/icons.js` — named SVG exports for Pan, Select, Rect, Polygon, Point, Line, AreaMeasure, Reset, Layers, Play, Pause
- `anybioimage/frontend/viewer/src/chrome/NumericInput.jsx` — reusable numeric-entry widget
- `anybioimage/frontend/viewer/src/chrome/NumericInput.test.jsx`
- `tests/integration/__init__.py`
- `tests/integration/conftest.py` — marimo server + playwright browser + widget-ready fixture
- `tests/integration/fixtures/__init__.py`
- `tests/integration/fixtures/demo_small.py` — minimal marimo notebook loaded by integration tests
- `tests/integration/fixtures/demo_two_widgets.py` — two viewers for keyboard isolation test
- `tests/integration/fixtures/demo_remote_zarr.py` — loads remote OME-Zarr URL
- `tests/integration/helpers/__init__.py`
- `tests/integration/helpers/widget.py` — `wait_for_ready`, `get_trait`, `set_trait`, `WidgetHandle`
- `tests/integration/helpers/pixels.py` — `sample_canvas`, `assert_non_black`, `read_pixels_at`
- `tests/integration/test_harness_smoke.py` — one trivial passing test proving the harness works
- `tests/integration/test_select_picks.py`
- `tests/integration/test_keyboard_isolation.py`
- `tests/integration/test_remote_zarr_renders.py`
- `tests/integration/test_channel_toggle_perf.py`
- `tests/integration/test_t_scrub_perf.py`
- `tests/integration/test_z_scrub_perf.py`
- `tests/integration/test_console_hygiene.py`
- `docs/superpowers/notes/widget-isolation-audit.md` — audit report (Task 5)
- `docs/superpowers/notes/phase2-5-perf-baseline.md` — baseline numbers (Task 8)

**Modified files:**

- `anybioimage/frontend/viewer/src/interaction/InteractionController.js` — add `setContext(extra)` method; wrap `handlePointerEvent` with `trace("interaction:<phase>", ...)`.
- `anybioimage/frontend/viewer/src/interaction/keyboard.js` — signature changes to `installKeyboard(model, containerEl)`; listener attaches to `containerEl`.
- `anybioimage/frontend/viewer/src/App.jsx` — pass the `.bioimage-viewer` root `div` into `installKeyboard`; `tabIndex={0}` already present; call `controller.setContext({ pickObject })` wired via DeckCanvas prop.
- `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx` — calls `controller.setContext({ pickObject })` once on mount; splits monolithic `layers` useMemo into per-layer memos; calls `source.prefetch({ t, z, halfWindow: 1 })` on scrub settle.
- `anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.js` — adds `prefetch({ t, z, halfWindow })` method; `getTile` wrapped with `trace("pixelSource:getTile", ...)`.
- `anybioimage/frontend/viewer/src/render/layers/buildImageLayer.js` — wrap body in `trace("buildImageLayerProps", ...)`.
- `anybioimage/frontend/viewer/src/chrome/Toolbar.jsx` — icons from `icons.js`; every button carries `aria-label` + `title` with shortcut.
- `anybioimage/frontend/viewer/src/chrome/DimControls.jsx` — play button: hidden when `dim_t <= 1`; disabled-with-tooltip until `scrub_perf_verified` flips true; use `icons.js` play/pause.
- `anybioimage/frontend/viewer/src/chrome/LayersPanel/ImageSection.jsx` — channel rows use `NumericInput` for min/max/gamma; "1" reset button beside gamma; "%" toggle per channel; data-value display default.
- `anybioimage/viewer.py` — add `_render_ready` (Bool, sync, default False) and `scrub_perf_verified` (Bool, sync, default False) traitlets; add `verify_scrub_perf()` helper method.
- `pyproject.toml` — add `integration` pytest marker.
- `.github/workflows/ci.yml` — new `integration` job with Playwright browser install.
- `CHANGELOG.md` — Phase 2.5 additions.

**Deletions:** none. Phase 2.5 is purely additive + refactor.

---

## Conventions

- **Every code step shows the full code.** No `...`, no "similar to X", no placeholders.
- **TDD on Python and JS units** (pytest + vitest). Integration tests are the third tier — also written first, then fail, then fix, then pass. No `xfail` on integration tests.
- **Commits are bite-sized**, one conventional-prefixed commit per logical change (`feat`, `refactor`, `build`, `test`, `docs`, `chore`, `ci`, `perf`, `fix`).
- **Each task ends with a commit.** Intermediate steps inside a task may include `git add` of partial files; the final step of the task is always a `git commit`.
- **Python tests:** `uv run pytest tests/ -v --ignore=tests/integration --ignore=tests/playwright`
- **JS tests:** `cd anybioimage/frontend/viewer && npm run test`
- **Integration tests:** `uv run pytest tests/integration/ -v -m integration`
- **Bundle build:** `cd anybioimage/frontend/viewer && npm run build`
- **Bundle size check:** `cd anybioimage/frontend/viewer && npm run size`
- **Worktree:** all work happens in `.worktrees/viv-backend` on branch `feature/viv-backend`.
- **Perf commit messages** include before/after p95 in the body — commits without numbers on perf-relevant work are invalid.

---

## Task 1: `util/perf.js` + tests + first instrumentation point

**Goal:** Land the perf instrumentation primitives end-to-end. The final step wires `buildImageLayerProps` through `trace()` to prove the whole path works: flag-gated, ring-buffered, percentile-computed. [spec §3]

**Files:**
- Create: `anybioimage/frontend/viewer/src/util/perf.js`
- Create: `anybioimage/frontend/viewer/src/util/perf.test.js`
- Modify: `anybioimage/frontend/viewer/src/render/layers/buildImageLayer.js`

- [ ] **Step 1: Write the failing vitest**

Create `anybioimage/frontend/viewer/src/util/perf.test.js`:

```js
// anybioimage/frontend/viewer/src/util/perf.test.js
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { mark, measure, trace, getPerfReport, clearPerf } from './perf.js';

describe('perf.js', () => {
  beforeEach(() => {
    clearPerf();
    globalThis.window = globalThis.window || {};
    globalThis.window.__ANYBIOIMAGE_PERF = true;
  });

  afterEach(() => {
    globalThis.window.__ANYBIOIMAGE_PERF = false;
    clearPerf();
  });

  it('no-ops when the flag is off', () => {
    globalThis.window.__ANYBIOIMAGE_PERF = false;
    mark('a'); mark('b');
    measure('ab', 'a', 'b');
    expect(getPerfReport()).toEqual({});
  });

  it('records a measurement when the flag is on', () => {
    mark('start');
    // Busy-wait a hair so duration > 0.
    const t0 = performance.now();
    while (performance.now() - t0 < 1) { /* spin 1 ms */ }
    mark('end');
    measure('busy', 'start', 'end');
    const r = getPerfReport();
    expect(r.busy).toBeDefined();
    expect(r.busy.count).toBe(1);
    expect(r.busy.mean).toBeGreaterThan(0);
  });

  it('trace() wraps a sync fn and records duration', () => {
    const out = trace('op', () => 42);
    expect(out).toBe(42);
    const r = getPerfReport();
    expect(r.op.count).toBe(1);
  });

  it('trace() wraps an async fn and records duration', async () => {
    const out = await trace('async-op', async () => {
      await new Promise((r) => setTimeout(r, 2));
      return 'ok';
    });
    expect(out).toBe('ok');
    const r = getPerfReport();
    expect(r['async-op'].count).toBe(1);
    expect(r['async-op'].mean).toBeGreaterThan(0);
  });

  it('trace() records even if the wrapped fn throws', () => {
    expect(() => trace('boom', () => { throw new Error('x'); })).toThrow('x');
    const r = getPerfReport();
    expect(r.boom.count).toBe(1);
  });

  it('computes p50 / p95 / p99 over many samples', () => {
    for (let i = 1; i <= 100; i++) {
      trace('linear', () => {
        const t0 = performance.now();
        while (performance.now() - t0 < i * 0.1) { /* spin */ }
      });
    }
    const r = getPerfReport();
    expect(r.linear.count).toBe(100);
    expect(r.linear.p50).toBeLessThan(r.linear.p95);
    expect(r.linear.p95).toBeLessThan(r.linear.p99 + 0.001);
  });

  it('ring buffer retains at most 1000 entries per label', () => {
    for (let i = 0; i < 1200; i++) {
      trace('bounded', () => {});
    }
    const r = getPerfReport();
    expect(r.bounded.count).toBe(1000);
  });

  it('clearPerf() drops all records', () => {
    trace('x', () => {});
    clearPerf();
    expect(getPerfReport()).toEqual({});
  });
});
```

- [ ] **Step 2: Run, expect fail**

```
cd anybioimage/frontend/viewer && npm run test -- src/util/perf.test.js
```

Expected: module not found / import error.

- [ ] **Step 3: Implement `util/perf.js`**

Create `anybioimage/frontend/viewer/src/util/perf.js`:

```js
// anybioimage/frontend/viewer/src/util/perf.js
/**
 * Perf instrumentation — always compiled, no-op unless window.__ANYBIOIMAGE_PERF is true.
 *
 * API (spec §3):
 *   mark(name)              — records a timestamp keyed by name.
 *   measure(label, a, b)    — records duration (in ms) between marks a and b under label.
 *   trace(label, fn)        — wraps a sync or async fn; records its wall-clock duration.
 *   getPerfReport()         — { [label]: { count, mean, p50, p95, p99 } }
 *   clearPerf()             — drops all recorded data.
 *
 * Storage: per-label ring buffer of the last 1000 durations.
 * Ordering: percentiles are sorted-copy of the ring at report-time, so mark/measure calls stay O(1).
 */

const MAX_SAMPLES = 1000;
const _marks = new Map();       // name → timestamp (ms)
const _rings = new Map();       // label → number[] (ring buffer of durations ms)

function enabled() {
  return typeof window !== 'undefined' && window.__ANYBIOIMAGE_PERF === true;
}

function now() {
  return (typeof performance !== 'undefined' && performance.now)
    ? performance.now()
    : Date.now();
}

function push(label, duration) {
  let ring = _rings.get(label);
  if (!ring) { ring = []; _rings.set(label, ring); }
  ring.push(duration);
  if (ring.length > MAX_SAMPLES) ring.splice(0, ring.length - MAX_SAMPLES);
}

export function mark(name) {
  if (!enabled()) return;
  _marks.set(name, now());
}

export function measure(label, startMark, endMark) {
  if (!enabled()) return;
  const a = _marks.get(startMark);
  const b = _marks.get(endMark);
  if (a == null || b == null) return;
  push(label, b - a);
}

export function trace(label, fn) {
  if (!enabled()) return fn();
  const t0 = now();
  let out;
  try {
    out = fn();
  } catch (err) {
    push(label, now() - t0);
    throw err;
  }
  if (out && typeof out.then === 'function') {
    return out.then(
      (val) => { push(label, now() - t0); return val; },
      (err) => { push(label, now() - t0); throw err; },
    );
  }
  push(label, now() - t0);
  return out;
}

function percentile(sorted, p) {
  if (sorted.length === 0) return 0;
  const idx = Math.min(sorted.length - 1, Math.floor(sorted.length * p));
  return sorted[idx];
}

export function getPerfReport() {
  const out = {};
  for (const [label, ring] of _rings.entries()) {
    if (ring.length === 0) continue;
    const sorted = ring.slice().sort((a, b) => a - b);
    let sum = 0;
    for (const v of sorted) sum += v;
    out[label] = {
      count: sorted.length,
      mean: sum / sorted.length,
      p50: percentile(sorted, 0.50),
      p95: percentile(sorted, 0.95),
      p99: percentile(sorted, 0.99),
    };
  }
  return out;
}

export function clearPerf() {
  _marks.clear();
  _rings.clear();
}
```

- [ ] **Step 4: Re-run vitest**

```
cd anybioimage/frontend/viewer && npm run test -- src/util/perf.test.js
```

Expected: all 8 tests pass.

- [ ] **Step 5: Wire `buildImageLayerProps` through trace**

Modify `anybioimage/frontend/viewer/src/render/layers/buildImageLayer.js`:

```js
import { AdditiveColormapExtension, MAX_CHANNELS } from '@hms-dbmi/viv';
import { trace } from '../../util/perf.js';

// Stateless; one shared instance avoids tearing down deck.gl's GPU pipeline
// on every channel-setting change.
const ADDITIVE_COLORMAP_EXT = new AdditiveColormapExtension();

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

export function buildImageLayerProps(args) {
  return trace('buildImageLayerProps', () => _build(args));
}

function _build({
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

  const selections = clipped.map((ch) => ({ t: currentT, c: ch.index, z: currentZ }));
  const colors = clipped.map((ch) => hexToRgb(ch.color));
  const contrastLimits = clipped.map(contrastFor);
  const channelsVisible = clipped.map(() => true);

  const lutChannel = clipped.find((ch) => ch.color_kind === 'lut');

  // Only override Viv's default extension when we actually want a colormap.
  // Passing `extensions: undefined` overrides the default array with undefined
  // and breaks MultiscaleImageLayer initialization ("extensions is not iterable").
  const props = {
    loader: sources,
    selections,
    colors,
    contrastLimits,
    channelsVisible,
  };
  if (lutChannel) {
    props.extensions = [ADDITIVE_COLORMAP_EXT];
    props.colormap = lutChannel.lut || 'viridis';
  }
  return props;
}
```

- [ ] **Step 6: Build the bundle + rerun all JS tests**

```
cd anybioimage/frontend/viewer && npm run test && npm run build
```

Expected: all unit tests green; bundle builds.

- [ ] **Step 7: Commit**

```bash
git add anybioimage/frontend/viewer/src/util/perf.js \
        anybioimage/frontend/viewer/src/util/perf.test.js \
        anybioimage/frontend/viewer/src/render/layers/buildImageLayer.js \
        anybioimage/frontend/viewer/dist/viewer-bundle.js
git commit -m "feat(perf): add util/perf.js + trace buildImageLayerProps [spec §3]

- Ring-buffered (1000 per label) perf instrumentation.
- Gated by window.__ANYBIOIMAGE_PERF; no-op otherwise.
- trace() handles sync + async fns + throwing fns.
- First consumer: buildImageLayerProps emits 'buildImageLayerProps' label."
```

---

## Task 2: Integration-test scaffold + `_render_ready` traitlet + harness smoke test

**Goal:** Land the `tests/integration/` directory with its fixtures, helpers, pytest marker, CI job, and one trivial integration test that proves the harness works end-to-end. Add the `_render_ready` traitlet on the Python side and flip it to True from JS on first successful Viv raster render. [spec §4, §5.3]

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/conftest.py`
- Create: `tests/integration/fixtures/__init__.py`
- Create: `tests/integration/fixtures/demo_small.py`
- Create: `tests/integration/helpers/__init__.py`
- Create: `tests/integration/helpers/widget.py`
- Create: `tests/integration/helpers/pixels.py`
- Create: `tests/integration/test_harness_smoke.py`
- Modify: `pyproject.toml`
- Modify: `anybioimage/viewer.py`
- Modify: `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Add `integration` pytest marker to `pyproject.toml`**

Edit `pyproject.toml`, replace the `[tool.pytest.ini_options]` block:

```toml
[tool.pytest.ini_options]
markers = [
    "playwright: marks tests as Playwright browser tests (requires marimo server + browser)",
    "integration: marks tests as end-to-end integration tests (marimo server + browser; asserts via traitlets)",
]
```

- [ ] **Step 2: Add `_render_ready` + `scrub_perf_verified` traitlets to `viewer.py`**

Edit `anybioimage/viewer.py` — insert new traitlets after the existing `scale_bar_visible` declaration (around line 167, before `_esm = _BUNDLE`):

```python
    # Phase 2.5 — integration-test handshake [spec §2, §5.3].
    # JS flips _render_ready to True on first successful raster render; test
    # fixtures block on it before reading model state.
    _render_ready = traitlets.Bool(False).tag(sync=True)

    # Phase 2.5 — play-button gating [spec §7.4].
    # Only flipped to True after `verify_scrub_perf()` runs and the T-scrub
    # integration test passes on this machine.
    scrub_perf_verified = traitlets.Bool(False).tag(sync=True)
```

- [ ] **Step 3: Flip `_render_ready` from JS once the first image layer renders**

Edit `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx` — keep every existing line; right after the `imageLayerProps` useMemo (around line 117), add a render-ready signal effect:

```jsx
  const imageLayerProps = useMemo(() => {
    if (!sources || !sources.length) return null;
    return buildImageLayerProps({
      sources, channels: channelSettings || [],
      currentT: currentT || 0, currentZ: currentZ || 0,
      displayMode, activeChannel,
    });
  }, [sources, channelSettings, currentT, currentZ, displayMode, activeChannel]);

  // _render_ready: flipped True once we have both a valid image-layer prop set
  // AND a non-null viewState (the canvas has rendered a frame). Fixtures block
  // on this trait via wait_for_ready(). Flip-once semantics — don't churn it
  // on every re-render.
  useEffect(() => {
    if (imageLayerProps && viewState && !model.get('_render_ready')) {
      model.set('_render_ready', true);
      model.save_changes();
    }
  }, [imageLayerProps, viewState, model]);
```

- [ ] **Step 4: Create fixtures package**

Create `tests/integration/__init__.py` (empty file — just to make it a package):

```python
```

Create `tests/integration/fixtures/__init__.py`:

```python
```

Create `tests/integration/helpers/__init__.py`:

```python
```

- [ ] **Step 5: Minimal marimo notebook fixture**

Create `tests/integration/fixtures/demo_small.py`:

```python
"""Minimal integration-test notebook — one viewer, one in-RAM image.

Loaded by the `marimo_server` fixture in conftest.py. The notebook must
expose a `viewer` symbol at module scope so helpers can reach it via
marimo's inspector API.
"""
import marimo

__generated_with = "0.19.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import numpy as np
    from anybioimage import BioImageViewer

    rng = np.random.default_rng(42)
    # 3 channels × 256 × 256 uint16 — small enough to render fast, big
    # enough to have non-black pixels.
    img = rng.integers(10000, 50000, size=(1, 3, 1, 256, 256), dtype=np.uint16)

    viewer = BioImageViewer()
    viewer.set_image(img)
    return (viewer,)


@app.cell
def _(mo, viewer):
    mo.ui.anywidget(viewer)
    return


if __name__ == "__main__":
    app.run()
```

- [ ] **Step 6: conftest.py with session-scoped marimo + browser fixtures**

Create `tests/integration/conftest.py`:

```python
"""Integration-test harness — marimo + playwright + widget-ready gating.

This is the third testing tier [spec §4]:
  - tests/            — pytest (headless, no browser)
  - tests/playwright/ — smoke screenshots (existing)
  - tests/integration/— THIS: real gestures, asserts via traitlets + pixel reads

Fixtures (session):
  marimo_server  → URL of a running marimo server loading fixtures/demo_small.py
  browser        → Playwright chromium

Fixtures (function):
  page           → fresh page + console error collector
  widget         → WidgetHandle wrapping (page, model-accessor helpers)
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _pick_port() -> int:
    """Find a free localhost port for this session."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_marimo(notebook: Path, port: int) -> tuple[subprocess.Popen, str]:
    """Launch `marimo edit` in headless mode; return (process, url_with_token)."""
    cmd = [
        sys.executable, "-m", "marimo", "edit",
        str(notebook),
        "--headless",
        "--host", "127.0.0.1",
        "--port", str(port),
        "--no-token",          # simplest for tests — bypass the access-token dance
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    # Poll until the port responds.
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return proc, f"http://127.0.0.1:{port}/?file={notebook.name}"
        except OSError:
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError(f"marimo server did not start on port {port}")


@pytest.fixture(scope="session")
def marimo_server():
    """Start one marimo server for the whole session against demo_small.py."""
    port = _pick_port()
    proc, url = _start_marimo(FIXTURES_DIR / "demo_small.py", port)
    yield url
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def browser():
    """Session-scoped Playwright chromium browser."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch(
            headless=True,
            args=["--use-gl=swiftshader", "--disable-dev-shm-usage"],
        )
        yield br
        br.close()


@pytest.fixture
def page(browser):
    """Function-scoped page with console-error collector attached."""
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = context.new_page()
    pg._console_log = []   # type: ignore[attr-defined]
    pg.on("console", lambda m: pg._console_log.append((m.type, m.text)))
    yield pg
    context.close()


@pytest.fixture
def widget(page, marimo_server):
    """Load demo_small.py, wait for _render_ready, return a WidgetHandle."""
    from tests.integration.helpers.widget import WidgetHandle

    page.goto(marimo_server)
    page.wait_for_load_state("networkidle")
    handle = WidgetHandle(page, widget_index=0)
    handle.wait_for_ready(timeout_ms=30000)
    return handle
```

- [ ] **Step 7: WidgetHandle helpers**

Create `tests/integration/helpers/widget.py`:

```python
"""WidgetHandle — Playwright-driven API for talking to a rendered BioImageViewer.

Reaches into the marimo shadow-DOM [spec §4], finds the MARIMO-ANYWIDGET that
matches `widget_index`, and exposes:

  wait_for_ready   block until _render_ready flips True
  get_trait/set    read / write traitlets by round-tripping through model
  click_tool       click toolbar button by title prefix
  drag             synthesise a pointer-down / move / up gesture
  focus            click inside the widget (focuses the container for keyboard)
  perf_snapshot    getPerfReport() dict
  perf_p95         convenience
  clear_perf       clearPerf()
"""
from __future__ import annotations

import time
from typing import Any


_WIDGET_JS_PRELUDE = """
(index) => {
  const widgets = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) widgets.push(el);
  }
  return widgets[index] || null;
}
"""


_GET_TRAIT_JS = """
([index, name]) => {
  const widgets = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) widgets.push(el);
  }
  const w = widgets[index];
  if (!w) return null;
  return w._widget?.model?.get(name) ?? null;
}
"""


_SET_TRAIT_JS = """
([index, name, value]) => {
  const widgets = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) widgets.push(el);
  }
  const w = widgets[index];
  if (!w || !w._widget?.model) return false;
  w._widget.model.set(name, value);
  w._widget.model.save_changes();
  return true;
}
"""


_CANVAS_BOX_JS = """
(index) => {
  const widgets = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) widgets.push(el);
  }
  const w = widgets[index];
  if (!w) return null;
  const c = w.shadowRoot.querySelector('canvas');
  if (!c) return null;
  const r = c.getBoundingClientRect();
  return { x: r.left, y: r.top, w: r.width, h: r.height };
}
"""


_CLICK_TOOL_JS = """
([index, titlePrefix]) => {
  const widgets = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) widgets.push(el);
  }
  const w = widgets[index];
  if (!w) return false;
  const btns = [...w.shadowRoot.querySelectorAll('button')];
  const target = btns.find(b => (b.title || b.getAttribute('aria-label') || '').startsWith(titlePrefix));
  if (!target) return false;
  target.click();
  return true;
}
"""


_FOCUS_WIDGET_JS = """
(index) => {
  const widgets = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) widgets.push(el);
  }
  const w = widgets[index];
  if (!w) return false;
  const root = w.shadowRoot.querySelector('.bioimage-viewer');
  if (root && typeof root.focus === 'function') { root.focus(); return true; }
  return false;
}
"""


_PERF_REPORT_JS = """
() => {
  // perf.js is loaded per-widget; all widgets on the page share the same
  // module instance because the bundle is ES-module cached. First widget wins.
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
      if (window.__anybioimage_perf_report) return window.__anybioimage_perf_report();
    }
  }
  return {};
}
"""


_INSTALL_PERF_PROBE_JS = """
() => {
  // The App.jsx entry exposes perf helpers on window so tests can reach them
  // without walking the React tree. Set by Task 7 (entry.js wiring).
  window.__ANYBIOIMAGE_PERF = true;
}
"""


class WidgetHandle:
    def __init__(self, page, widget_index: int = 0) -> None:
        self._page = page
        self._idx = widget_index

    # ---- readiness ----

    def wait_for_ready(self, timeout_ms: int = 30000) -> None:
        """Block until _render_ready === True (spec §2)."""
        # Enable perf instrumentation up-front — cheap and harmless.
        self._page.evaluate(_INSTALL_PERF_PROBE_JS)
        # Poll the trait rather than subscribing; handles the race where the
        # trait flipped before we could attach a listener (spec §10).
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            ok = self._page.evaluate(_GET_TRAIT_JS, [self._idx, "_render_ready"])
            if ok is True:
                return
            self._page.wait_for_timeout(100)
        raise TimeoutError("widget did not reach _render_ready within timeout")

    # ---- trait I/O ----

    def get(self, name: str) -> Any:
        return self._page.evaluate(_GET_TRAIT_JS, [self._idx, name])

    def set(self, name: str, value: Any) -> None:
        ok = self._page.evaluate(_SET_TRAIT_JS, [self._idx, name, value])
        if not ok:
            raise RuntimeError(f"failed to set trait {name}")

    # ---- gesture helpers ----

    def canvas_box(self) -> dict:
        box = self._page.evaluate(_CANVAS_BOX_JS, self._idx)
        if not box:
            raise RuntimeError("canvas not found")
        return box

    def click_tool(self, title_prefix: str) -> None:
        ok = self._page.evaluate(_CLICK_TOOL_JS, [self._idx, title_prefix])
        if not ok:
            raise RuntimeError(f"tool button '{title_prefix}' not found")

    def focus(self) -> None:
        ok = self._page.evaluate(_FOCUS_WIDGET_JS, self._idx)
        if not ok:
            # Fall back to a canvas click — focuses the shadow root's root div.
            box = self.canvas_box()
            self._page.mouse.click(box["x"] + box["w"] / 2, box["y"] + box["h"] / 2)

    def drag(self, x0: float, y0: float, x1: float, y1: float, steps: int = 10) -> None:
        self._page.mouse.move(x0, y0)
        self._page.mouse.down()
        self._page.mouse.move(x1, y1, steps=steps)
        self._page.mouse.up()

    def key(self, name: str) -> None:
        self._page.keyboard.press(name)

    # ---- perf ----

    def clear_perf(self) -> None:
        self._page.evaluate("() => window.__anybioimage_perf_clear && window.__anybioimage_perf_clear()")

    def perf_snapshot(self) -> dict:
        return self._page.evaluate(_PERF_REPORT_JS) or {}

    def perf_p95(self, label: str) -> float:
        rpt = self.perf_snapshot()
        entry = rpt.get(label)
        if not entry:
            raise KeyError(f"no perf samples under label '{label}'")
        return float(entry["p95"])
```

- [ ] **Step 8: pixel helpers**

Create `tests/integration/helpers/pixels.py`:

```python
"""Pixel sampling for integration tests.

Reads canvas pixels via deck.gl's `readPixels` [spec §4] so we don't trip the
tainted-canvas rule that affects `getImageData` on WebGL-sourced images from
cross-origin contexts.
"""
from __future__ import annotations


_READ_PIXELS_JS = """
([index, x, y, w, h]) => {
  const widgets = [];
  for (const el of document.querySelectorAll('*')) {
    if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) widgets.push(el);
  }
  const w2 = widgets[index];
  if (!w2) return null;
  const canvas = w2.shadowRoot.querySelector('canvas');
  if (!canvas) return null;
  // Use the WebGL context's readPixels directly — avoids the 2D-context
  // getImageData path entirely.
  const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
  if (!gl) return null;
  const pixels = new Uint8Array(w * h * 4);
  gl.readPixels(x, y, w, h, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
  return Array.from(pixels);
}
"""


def read_pixels_at(page, index: int, x: int, y: int, w: int = 1, h: int = 1) -> list[int]:
    """Return RGBA values at canvas coord (x, y). Flat list of length w*h*4."""
    return page.evaluate(_READ_PIXELS_JS, [index, x, y, w, h]) or []


def sample_canvas(page, index: int, points: list[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    """Sample canvas pixels at each (x, y) in `points`; return [(r,g,b,a), ...]."""
    out = []
    for (x, y) in points:
        px = read_pixels_at(page, index, x, y, 1, 1)
        if len(px) < 4:
            out.append((0, 0, 0, 0))
        else:
            out.append((px[0], px[1], px[2], px[3]))
    return out


def assert_non_black(samples: list[tuple[int, int, int, int]], threshold: int = 10) -> None:
    """Fail loudly if every sampled pixel is near-black."""
    for (r, g, b, _a) in samples:
        if r > threshold or g > threshold or b > threshold:
            return
    raise AssertionError(f"all {len(samples)} sampled pixels are near-black (<={threshold}): {samples}")
```

- [ ] **Step 9: Harness-smoke integration test**

Create `tests/integration/test_harness_smoke.py`:

```python
"""Proves the integration harness wiring works end-to-end [spec §4, §9 step 1].

The only assertion is that `_render_ready` flipped True — everything else is
covered by later tests. If this test fails, the harness is broken; no later
test can be trusted.
"""
from __future__ import annotations

import pytest


@pytest.mark.integration
def test_render_ready_flips_true(widget):
    assert widget.get("_render_ready") is True


@pytest.mark.integration
def test_channel_settings_is_nonempty(widget):
    settings = widget.get("_channel_settings")
    assert isinstance(settings, list)
    assert len(settings) >= 1
```

- [ ] **Step 10: Expose `clearPerf` + `getPerfReport` on `window` for tests**

`entry.js` (bundle entry) must expose the perf functions on `window` so Playwright tests can reach them. Edit `anybioimage/frontend/viewer/src/entry.js` — add two lines at the top-level before the anywidget render export. First read the current entry.

```bash
# Read current entry content.
sed -n '1,40p' anybioimage/frontend/viewer/src/entry.js
```

Edit `anybioimage/frontend/viewer/src/entry.js` — add an import and a `window.__anybioimage_perf_*` assignment at the top of the file, after the existing imports:

```js
// anybioimage/frontend/viewer/src/entry.js
import * as React from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App.jsx';
import { getPerfReport, clearPerf } from './util/perf.js';

// Expose perf probes on window so integration tests can read them without
// walking the React tree. No-op on end-user machines unless __ANYBIOIMAGE_PERF
// is set first [spec §3].
if (typeof window !== 'undefined') {
  window.__anybioimage_perf_report = getPerfReport;
  window.__anybioimage_perf_clear = clearPerf;
}

export default {
  render({ model, el }) {
    const root = createRoot(el);
    root.render(React.createElement(App, { model }));
    return () => root.unmount();
  },
};
```

Note: the existing `entry.js` may have a slightly different shape; preserve its existing export contract and only add the three lines that import `util/perf.js` and assign to `window.__anybioimage_perf_*`.

- [ ] **Step 11: Update CI to run the integration job**

Edit `.github/workflows/ci.yml` — add a new `integration` job below the existing `test` job:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v4
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          uv venv
          uv pip install -e ".[all]"

      - name: Lint (ruff)
        run: uv run ruff check anybioimage/ --output-format=github

      - name: Type check (ty)
        run: uv run ty check anybioimage/
        continue-on-error: true  # mixin pattern causes false positives; non-blocking

  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          uv venv
          uv pip install -e ".[all]"

      - name: Run tests
        run: uv run pytest tests/ -v --ignore=tests/integration --ignore=tests/playwright

  integration:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v4
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          uv venv
          uv pip install -e ".[all]"

      - name: Install Playwright browsers
        run: uv run playwright install chromium --with-deps

      - name: Run integration tests
        env:
          # CI is slower than a dev laptop; loosen perf budgets by 1.5× [spec §10].
          ANYBIOIMAGE_PERF_BUDGET_MULTIPLIER: "1.5"
        run: uv run pytest tests/integration/ -v -m integration
```

- [ ] **Step 12: Rebuild bundle + run harness test locally**

```
cd anybioimage/frontend/viewer && npm run build && cd -
uv run pytest tests/integration/test_harness_smoke.py -v -m integration
```

Expected: both tests green. If `playwright install chromium` has not been run locally, run `uv run playwright install chromium` once.

- [ ] **Step 13: Commit**

```bash
git add pyproject.toml \
        anybioimage/viewer.py \
        anybioimage/frontend/viewer/src/render/DeckCanvas.jsx \
        anybioimage/frontend/viewer/src/entry.js \
        anybioimage/frontend/viewer/dist/viewer-bundle.js \
        tests/integration/ \
        .github/workflows/ci.yml
git commit -m "test(integration): scaffold integration-test tier + _render_ready [spec §2, §4]

- New tier under tests/integration/; 'integration' pytest marker added.
- marimo+chromium fixture chain; WidgetHandle helper; pixel sampling helper.
- JS flips _render_ready once first image layer renders.
- CI gains a dedicated integration job with Playwright browser install.
- test_harness_smoke.py proves wiring end-to-end."
```

---

## Task 3: Fix Select tool — inject `pickObject` via `setContext`

**Goal:** Implement the Select-tool correctness fix [spec §5.1]. Integration test `test_select_picks.py` is written first, fails, then lands green after the `setContext` + DeckCanvas wiring change.

**Files:**
- Create: `tests/integration/test_select_picks.py`
- Modify: `anybioimage/frontend/viewer/src/interaction/InteractionController.js`
- Modify: `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx`
- Modify: `anybioimage/frontend/viewer/src/interaction/InteractionController.test.js` (existing file from Phase 2)

- [ ] **Step 1: Write the failing integration test**

Create `tests/integration/test_select_picks.py`:

```python
"""Select tool: click on a rect, selected_annotation_id matches; click empty, id cleared.

Root cause (spec §5.1): InteractionController._ctx is `{ model, controller }`
only; the `pickObject` closure the Select tool calls is not injected. This
test draws a rect, clicks the Select tool, clicks inside the rect's pixel
bounds, and asserts selected_annotation_id was set to the rect's id.
"""
from __future__ import annotations

import pytest


@pytest.mark.integration
def test_select_picks_a_rect(widget):
    # Place a rect directly via the trait so we don't depend on rect-tool drag.
    # Rect coords are in image pixels. demo_small.py is 256×256.
    widget.set("_annotations", [{
        "id": "r_test",
        "kind": "rect",
        "geometry": [50.0, 50.0, 150.0, 150.0],
        "label": "",
        "color": "#ff0000",
        "visible": True,
        "t": 0,
        "z": 0,
        "created_at": "2026-04-19T00:00:00Z",
        "metadata": {},
    }])
    # Activate Select tool (title prefix "Select").
    widget.click_tool("Select")

    # Click near the rect's centroid in image coords. Map through the canvas:
    # the test demo's view fits the image; centroid ≈ image (100, 100).
    # We can't trivially map image→screen from Python, so click the canvas
    # center — the demo's OrthographicView default shows the whole image
    # and the centroid sits near the middle. Nudge 20% toward top-left so we
    # hit the rect (50..150 range, not the whole canvas).
    box = widget.canvas_box()
    cx = box["x"] + box["w"] * 0.40
    cy = box["y"] + box["h"] * 0.40
    widget._page.mouse.click(cx, cy)
    widget._page.wait_for_timeout(300)

    assert widget.get("selected_annotation_id") == "r_test"
    assert widget.get("selected_annotation_type") == "rect"


@pytest.mark.integration
def test_select_clears_on_empty_click(widget):
    widget.set("_annotations", [{
        "id": "r_test",
        "kind": "rect",
        "geometry": [10.0, 10.0, 40.0, 40.0],
        "label": "",
        "color": "#ff0000",
        "visible": True,
        "t": 0,
        "z": 0,
        "created_at": "2026-04-19T00:00:00Z",
        "metadata": {},
    }])
    widget.set("selected_annotation_id", "r_test")
    widget.click_tool("Select")

    # Click far from the rect (bottom-right corner).
    box = widget.canvas_box()
    widget._page.mouse.click(box["x"] + box["w"] * 0.95, box["y"] + box["h"] * 0.95)
    widget._page.wait_for_timeout(300)

    assert widget.get("selected_annotation_id") == ""
    assert widget.get("selected_annotation_type") == ""
```

- [ ] **Step 2: Run, expect fail**

```
cd anybioimage/frontend/viewer && npm run build && cd -
uv run pytest tests/integration/test_select_picks.py -v -m integration
```

Expected: both tests fail because `ctx.pickObject` is `undefined` — the Select tool's `picked` is always null, so click-on-rect fails to set `selected_annotation_id` and click-on-empty still sets the trait to `""` (but we never got to the rect case passing, so the first test fails).

- [ ] **Step 3: Add `setContext` to InteractionController**

Modify `anybioimage/frontend/viewer/src/interaction/InteractionController.js`:

```js
/**
 * InteractionController — central dispatcher for pointer / key events on the
 * DeckCanvas. Holds the active tool selected by the `tool_mode` traitlet and
 * forwards events. Tools mutate `_annotations` (only mutation surface other
 * than the Layers panel).
 *
 * Each registered tool exports:
 *   { id, cursor, onPointerDown, onPointerMove, onPointerUp, onKeyDown,
 *     getPreviewLayer }
 * `getPreviewLayer()` returns a deck.gl Layer (or null) that renders the
 * in-progress draw. `markPreviewDirty()` triggers a re-render in DeckCanvas.
 */
import { trace } from '../util/perf.js';

const NOOP_TOOL = {
  id: '__noop',
  cursor: 'default',
  onPointerDown() {},
  onPointerMove() {},
  onPointerUp() {},
  onKeyDown() {},
  getPreviewLayer() { return null; },
};

export class InteractionController {
  constructor(model) {
    this._model = model;
    this._tools = new Map();
    this._previewListeners = new Set();
    this._ctx = { model, controller: this };
  }

  /**
   * Inject extra keys into the tool-invocation context. Called once from
   * DeckCanvas after mount to expose `pickObject` to tools. Further calls
   * merge — existing keys persist unless overridden. [spec §5.1]
   */
  setContext(extra) {
    if (!extra || typeof extra !== 'object') return;
    this._ctx = { ...this._ctx, ...extra };
  }

  register(tool) {
    this._tools.set(tool.id, tool);
  }

  get activeToolId() {
    return this._model.get('tool_mode') || 'pan';
  }

  get activeTool() {
    return this._tools.get(this.activeToolId) || NOOP_TOOL;
  }

  get cursor() {
    return this.activeTool.cursor || 'default';
  }

  handlePointerEvent(phase, event) {
    trace(`interaction:${phase}`, () => {
      const tool = this.activeTool;
      try {
        if (phase === 'down') tool.onPointerDown(event, this._ctx);
        else if (phase === 'move') tool.onPointerMove(event, this._ctx);
        else if (phase === 'up') tool.onPointerUp(event, this._ctx);
      } catch (err) {
        // Tools should never throw at runtime; log so we can see regressions
        // without killing the canvas.
        console.error(`tool '${tool.id}' threw in ${phase}:`, err);
      }
    });
  }

  handleKeyDown(event) {
    try {
      this.activeTool.onKeyDown(event, this._ctx);
    } catch (err) {
      console.error(`tool '${this.activeTool.id}' threw in keyDown:`, err);
    }
  }

  getPreviewLayer() {
    return this.activeTool.getPreviewLayer(this._ctx) || null;
  }

  onPreviewChange(cb) {
    this._previewListeners.add(cb);
    return () => this._previewListeners.delete(cb);
  }

  markPreviewDirty() {
    for (const cb of this._previewListeners) cb();
  }
}
```

- [ ] **Step 4: Wire `setContext({ pickObject })` in DeckCanvas**

Modify `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx` — after the `pickObject` function (around line 181), add a useEffect that injects it into the controller. The `pickObject` function must be wrapped in a stable callback — but the controller reads the live `pickObject` via the `_ctx` reference, so inject once on mount with a closure that always reads the latest `deckRef.current.deck` / `annotations` (via the closure, which React re-creates on every render — so inject on every render; the `setContext` merge is cheap).

Replace the block starting at the `pickObject` function through to before `onClick`:

```jsx
  function pickObject(event) {
    const deck = deckRef?.current?.deck;
    if (!deck || !event) return null;
    const picked = deck.pickObject({
      x: event.screenX ?? event._screenX ?? 0,
      y: event.screenY ?? event._screenY ?? 0,
      radius: 4,
    });
    if (!picked) return null;
    const id = picked.object?.id;
    const sourceAnnotation = id ? annotations.find((a) => a.id === id) : null;
    return { layer: picked.layer, object: picked.object, sourceAnnotation };
  }

  // Inject pickObject into the interaction controller's tool context
  // [spec §5.1]. `pickObject` is a new closure every render (it captures
  // `annotations` and `deckRef`), but setContext just merges into _ctx so
  // the cost is one object spread per render.
  useEffect(() => {
    if (!controller) return;
    controller.setContext({ pickObject });
  });  // no dep list — runs every render, matches the closure's capture window
```

- [ ] **Step 5: Update the existing `InteractionController.test.js`**

The Phase 2 unit test already tests the controller API; confirm it still passes and extend it with a `setContext` case. Read the file:

```bash
cat anybioimage/frontend/viewer/src/interaction/InteractionController.test.js
```

Append a new describe block at the bottom of the file:

```js
describe('setContext', () => {
  it('injects extra keys into the tool invocation context', () => {
    const model = { get: () => 'pan', set: () => {}, save_changes: () => {} };
    const ctrl = new InteractionController(model);
    let captured = null;
    ctrl.register({
      id: 'pan',
      cursor: 'grab',
      onPointerDown(event, ctx) { captured = ctx; },
      onPointerMove() {},
      onPointerUp() {},
      onKeyDown() {},
      getPreviewLayer() { return null; },
    });
    const pickObject = () => 'picked!';
    ctrl.setContext({ pickObject });
    ctrl.handlePointerEvent('down', { x: 0, y: 0 });
    expect(captured.pickObject).toBe(pickObject);
    expect(captured.pickObject()).toBe('picked!');
  });

  it('setContext merges with existing context and does not lose model', () => {
    const model = { get: () => 'pan', set: () => {}, save_changes: () => {} };
    const ctrl = new InteractionController(model);
    let captured = null;
    ctrl.register({
      id: 'pan',
      cursor: 'grab',
      onPointerDown(event, ctx) { captured = ctx; },
      onPointerMove() {},
      onPointerUp() {},
      onKeyDown() {},
      getPreviewLayer() { return null; },
    });
    ctrl.setContext({ pickObject: () => null });
    ctrl.setContext({ extra: 42 });
    ctrl.handlePointerEvent('down', { x: 0, y: 0 });
    expect(captured.model).toBe(model);
    expect(captured.extra).toBe(42);
    expect(typeof captured.pickObject).toBe('function');
  });
});
```

If the existing file structure has a single top-level `describe()` block, add this as a sibling; if it uses flat `it()` calls, wrap accordingly.

- [ ] **Step 6: Build + run JS tests + integration test**

```
cd anybioimage/frontend/viewer && npm run test && npm run build && cd -
uv run pytest tests/integration/test_select_picks.py -v -m integration
```

Expected: all green. The integration test now finds `selected_annotation_id === "r_test"` after clicking on the rect.

- [ ] **Step 7: Commit**

```bash
git add anybioimage/frontend/viewer/src/interaction/InteractionController.js \
        anybioimage/frontend/viewer/src/interaction/InteractionController.test.js \
        anybioimage/frontend/viewer/src/render/DeckCanvas.jsx \
        anybioimage/frontend/viewer/dist/viewer-bundle.js \
        tests/integration/test_select_picks.py
git commit -m "fix(interaction): Select tool picks annotations via setContext [spec §5.1]

Root cause: InteractionController._ctx exposed only {model, controller};
Select tool's ctx.pickObject(event) returned undefined, always cleared
selection.

Fix: InteractionController.setContext(extra) merges keys into _ctx.
DeckCanvas injects pickObject on every render (cheap shallow spread).
Integration test test_select_picks.py covers hit + empty-click paths."
```

---

## Task 4: Scope keyboard handler to widget container

**Goal:** Two widgets on the same page no longer fight for keyboard events [spec §5.2]. Integration test `test_keyboard_isolation.py` written first, fails, then passes after `installKeyboard(model, containerEl)` signature change.

**Files:**
- Create: `tests/integration/fixtures/demo_two_widgets.py`
- Create: `tests/integration/test_keyboard_isolation.py`
- Modify: `tests/integration/conftest.py` — add a `widgets_two` fixture
- Modify: `anybioimage/frontend/viewer/src/interaction/keyboard.js`
- Modify: `anybioimage/frontend/viewer/src/App.jsx`

- [ ] **Step 1: Two-widget marimo fixture**

Create `tests/integration/fixtures/demo_two_widgets.py`:

```python
"""Two BioImageViewers side-by-side for keyboard-isolation testing [spec §5.2]."""
import marimo

__generated_with = "0.19.0"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    import numpy as np
    from anybioimage import BioImageViewer

    rng = np.random.default_rng(7)
    img_a = rng.integers(10000, 50000, size=(5, 1, 1, 128, 128), dtype=np.uint16)
    img_b = rng.integers(10000, 50000, size=(5, 1, 1, 128, 128), dtype=np.uint16)

    viewer_a = BioImageViewer()
    viewer_a.set_image(img_a)
    viewer_b = BioImageViewer()
    viewer_b.set_image(img_b)
    return (viewer_a, viewer_b)


@app.cell
def _(mo, viewer_a):
    mo.ui.anywidget(viewer_a)
    return


@app.cell
def _(mo, viewer_b):
    mo.ui.anywidget(viewer_b)
    return


if __name__ == "__main__":
    app.run()
```

- [ ] **Step 2: Add `marimo_server_two` + `widgets_two` fixtures to conftest**

Edit `tests/integration/conftest.py` — append new session-scoped fixtures after the existing `marimo_server`:

```python
@pytest.fixture(scope="session")
def marimo_server_two():
    """Session-scoped two-widget notebook."""
    port = _pick_port()
    proc, url = _start_marimo(FIXTURES_DIR / "demo_two_widgets.py", port)
    yield url
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def widgets_two(page, marimo_server_two):
    """Load demo_two_widgets.py; return (WidgetHandle(0), WidgetHandle(1))."""
    from tests.integration.helpers.widget import WidgetHandle

    page.goto(marimo_server_two)
    page.wait_for_load_state("networkidle")
    a = WidgetHandle(page, widget_index=0)
    b = WidgetHandle(page, widget_index=1)
    a.wait_for_ready(timeout_ms=30000)
    b.wait_for_ready(timeout_ms=30000)
    return (a, b)
```

- [ ] **Step 3: Write failing keyboard-isolation test**

Create `tests/integration/test_keyboard_isolation.py`:

```python
"""Keyboard shortcuts are scoped to the focused widget [spec §5.2].

Root cause: keyboard.js attaches its handler to `window`. Two widgets on a
page stack two listeners, both respond to every key.
"""
from __future__ import annotations

import pytest


@pytest.mark.integration
def test_arrow_right_only_affects_focused_widget(widgets_two):
    a, b = widgets_two
    # Baseline.
    assert a.get("current_t") == 0
    assert b.get("current_t") == 0

    # Focus widget A, press ArrowRight → only A's current_t should advance.
    a.focus()
    a._page.wait_for_timeout(100)
    a.key("ArrowRight")
    a._page.wait_for_timeout(200)
    assert a.get("current_t") == 1, "widget A did not advance"
    assert b.get("current_t") == 0, "widget B advanced despite not being focused"

    # Focus widget B, press ArrowRight → only B's current_t should advance.
    b.focus()
    b._page.wait_for_timeout(100)
    b.key("ArrowRight")
    b._page.wait_for_timeout(200)
    assert a.get("current_t") == 1, "widget A's current_t moved while focus on B"
    assert b.get("current_t") == 1, "widget B did not advance"


@pytest.mark.integration
def test_tool_shortcut_only_affects_focused_widget(widgets_two):
    a, b = widgets_two
    assert a.get("tool_mode") == "pan"
    assert b.get("tool_mode") == "pan"

    a.focus()
    a._page.wait_for_timeout(100)
    a.key("r")   # Rectangle shortcut
    a._page.wait_for_timeout(200)
    assert a.get("tool_mode") == "rect"
    assert b.get("tool_mode") == "pan", "tool_mode leaked to non-focused widget B"
```

- [ ] **Step 4: Run, expect fail**

```
uv run pytest tests/integration/test_keyboard_isolation.py -v -m integration
```

Expected: both tests fail because the `window`-level handler in every widget fires on every keydown, so `a.get("current_t") == 1` and `b.get("current_t") == 1` both.

- [ ] **Step 5: Change `installKeyboard` signature**

Modify `anybioimage/frontend/viewer/src/interaction/keyboard.js`:

```js
// anybioimage/frontend/viewer/src/interaction/keyboard.js
const TOOL_KEYS = {
  v: 'select', p: 'pan',
  r: 'rect', g: 'polygon', o: 'point',
  l: 'line', m: 'areaMeasure',
};

function isEditableTarget(el) {
  if (!el) return false;
  if (el.isContentEditable) return true;
  const tag = el.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  return false;
}

/**
 * Install keyboard shortcuts on a specific DOM element so that two widgets on
 * the same page do not fight each other [spec §5.2].
 *
 *   installKeyboard(model, containerEl)
 *     model       — the anywidget model for this viewer instance
 *     containerEl — the focusable root (tabIndex=0) of this widget; the
 *                   listener is attached here, not on window
 *
 * Returns a disposer that removes the listener.
 */
export function installKeyboard(model, containerEl) {
  if (!containerEl) {
    // Defensive: if the caller forgot to pass an element, do nothing and
    // return a no-op disposer. Fail loudly via console so we notice.
    console.error('installKeyboard: containerEl is required (spec §5.2)');
    return () => {};
  }

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

  containerEl.addEventListener('keydown', handler);
  return () => containerEl.removeEventListener('keydown', handler);
}
```

- [ ] **Step 6: Pass the root div into `installKeyboard`**

Modify `anybioimage/frontend/viewer/src/App.jsx`:

```jsx
// anybioimage/frontend/viewer/src/App.jsx
import React, { useState, useRef, useMemo, useEffect } from 'react';
import { Toolbar } from './chrome/Toolbar.jsx';
import { DimControls } from './chrome/DimControls.jsx';
import { StatusBar } from './chrome/StatusBar.jsx';
import { LayersPanel } from './chrome/LayersPanel/LayersPanel.jsx';
import { DeckCanvas } from './render/DeckCanvas.jsx';
import { installKeyboard } from './interaction/keyboard.js';
import { makeHoverHandler } from './render/onHoverPixelInfo.js';
import { InteractionController } from './interaction/InteractionController.js';
import { panTool } from './interaction/tools/pan.js';
import { selectTool } from './interaction/tools/select.js';
import { rectTool } from './interaction/tools/rect.js';
import { polygonTool } from './interaction/tools/polygon.js';
import { pointTool } from './interaction/tools/point.js';
import { MaskSourceBridge } from './render/pixel-sources/MaskSourceBridge.js';

export function App({ model }) {
  const [panelOpen, setPanelOpen] = useState(false);
  const [hover, setHover] = useState(null);
  const sourcesRef = useRef(null);
  const selectionsRef = useRef(null);
  const deckRef = useRef(null);
  const rootRef = useRef(null);

  const controller = useMemo(() => {
    const c = new InteractionController(model);
    c.register(panTool);
    c.register(selectTool);
    c.register(rectTool);
    c.register(polygonTool);
    c.register(pointTool);
    return c;
  }, [model]);

  const maskBridge = useMemo(() => new MaskSourceBridge(model), [model]);
  useEffect(() => () => maskBridge.destroy(), [maskBridge]);

  useEffect(() => {
    const handler = () => {
      rectTool.reset();
      polygonTool.reset();
    };
    model.on('change:tool_mode', handler);
    return () => model.off('change:tool_mode', handler);
  }, [model, controller]);

  const onHover = useMemo(
    () => makeHoverHandler({
      getSources: () => sourcesRef.current,
      getSelections: () => selectionsRef.current,
      setHover,
    }),
    []);

  // Scope keyboard handler to THIS widget's root div [spec §5.2].
  useEffect(() => {
    if (!rootRef.current) return;
    return installKeyboard(model, rootRef.current);
  }, [model]);

  return (
    <div ref={rootRef} className="bioimage-viewer" tabIndex={0}>
      <Toolbar model={model} onToggleLayers={() => setPanelOpen((v) => !v)} panelOpen={panelOpen} />
      <DimControls model={model} />
      <div className="content-area" style={{ display: 'flex', flex: 1, minHeight: 500 }}>
        <div className="viewport-slot" style={{ position: 'relative', flex: 1, minHeight: 500, background: '#000' }}>
          <DeckCanvas model={model} onHover={onHover}
                      controller={controller}
                      maskBridge={maskBridge}
                      deckRef={deckRef}
                      sourcesRef={sourcesRef}
                      selectionsRef={selectionsRef} />
        </div>
        {panelOpen && <LayersPanel model={model} />}
      </div>
      <StatusBar model={model} hover={hover} />
    </div>
  );
}
```

- [ ] **Step 7: Build + re-run integration test**

```
cd anybioimage/frontend/viewer && npm run build && cd -
uv run pytest tests/integration/test_keyboard_isolation.py -v -m integration
```

Expected: both tests green.

- [ ] **Step 8: Commit**

```bash
git add anybioimage/frontend/viewer/src/interaction/keyboard.js \
        anybioimage/frontend/viewer/src/App.jsx \
        anybioimage/frontend/viewer/dist/viewer-bundle.js \
        tests/integration/fixtures/demo_two_widgets.py \
        tests/integration/conftest.py \
        tests/integration/test_keyboard_isolation.py
git commit -m "fix(interaction): scope keyboard handler to widget container [spec §5.2]

Root cause: installKeyboard(model) attached to window. Two widgets on a
page stacked two listeners; every keydown advanced both viewers.

Fix: installKeyboard(model, containerEl) — listener attaches to the
focusable root div (.bioimage-viewer already has tabIndex=0). App.jsx
passes rootRef.current.
Integration test test_keyboard_isolation.py drives two viewers, asserts
focused-only response for both ArrowRight (current_t) and 'r' (tool_mode)."
```

---

## Task 5: Widget isolation audit

**Goal:** Systematic grep for shared mutable state, module-level listeners, and `window.*` usage [spec §5.4]. Produce an audit note; fix anything discovered that's not intentional. If no fixes are needed, commit the audit doc alone.

**Files:**
- Create: `docs/superpowers/notes/widget-isolation-audit.md`

- [ ] **Step 1: Grep for suspect patterns**

Run each search and record findings. Use the project's Grep tool equivalent:

```bash
cd anybioimage/frontend/viewer/src

# 1. window.* references (not just addEventListener)
grep -rn "window\." --include="*.js" --include="*.jsx" . | grep -v "\.test\."

# 2. Module-level `let` / `var` — candidates for shared mutable state
grep -rn "^let \|^var " --include="*.js" --include="*.jsx" . | grep -v "\.test\."

# 3. setInterval / setTimeout with no matching clear
grep -rn "setInterval\|setTimeout" --include="*.js" --include="*.jsx" . | grep -v "\.test\."

# 4. document.addEventListener (global DOM listeners)
grep -rn "document\.addEventListener" --include="*.js" --include="*.jsx" . | grep -v "\.test\."
```

- [ ] **Step 2: Write the audit report**

Create `docs/superpowers/notes/widget-isolation-audit.md`:

```markdown
# Widget isolation audit — Phase 2.5 Task 5

**Date:** 2026-04-19
**Scope:** `anybioimage/frontend/viewer/src/` — find shared mutable state,
module-level listeners, and window/document globals. For each finding, decide:

- **Intentional global** — keep, documented here.
- **Per-widget (accidental global)** — fix (scope to instance).

## Findings

### 1. `_nextRequestId` in `pixel-sources/anywidget-source.js`

```js
let _nextRequestId = 1;
```

**Status:** intentional global. Multiple AnywidgetPixelSource instances share
this counter; each source owns its own `_pending` map keyed by `requestId`,
and the model.on('msg:custom') listener checks `_pending.has(requestId)` so
cross-widget collisions cannot cause cross-delivery. Confirmed benign.

### 2. `ADDITIVE_COLORMAP_EXT` in `render/layers/buildImageLayer.js`

```js
const ADDITIVE_COLORMAP_EXT = new AdditiveColormapExtension();
```

**Status:** intentional global. Stateless singleton — sharing it avoids
re-initialising Viv's GPU pipeline on every channel-setting change.

### 3. `window` listeners

- `installKeyboard` — previously attached to `window`. Fixed in Task 4.
- `document.addEventListener` — none found.

### 4. Module-level `let` / `var`

_Fill in during audit pass. Expected: only `_nextRequestId`._

### 5. Unclosed timers

Each `setInterval` / `setTimeout` must have a matching `clearInterval` /
`clearTimeout` in a cleanup path.

- `DimControls.jsx` `useLivePlay` — setInterval cleared via the returned
  cleanup. OK.
- `anywidget-source.js` `_flushTimer` — cleared in `destroy()`. OK.
- `DeckCanvas.jsx` `reportViewport` debounce — _check during audit_.

### 6. InteractionController / MaskSourceBridge

Both are instantiated per-App via `useMemo`. Each instance holds its own
Maps and listener sets. Confirmed per-widget.

## Summary

If after walking all greps everything above still holds, commit this file
alone. If any additional findings require fixing, fix them and document
the fix in a new sub-section of this file with the commit SHA that landed
the fix.
```

- [ ] **Step 3: Walk every grep hit and update the audit**

Do not commit the audit with placeholder text. For each of sections 4 and 5, replace the placeholder with actual findings or "No new findings — section 1/2/3 enumerates all module state." Fix any accidental globals discovered.

- [ ] **Step 4: Build + run all tests to confirm nothing regressed**

```
cd anybioimage/frontend/viewer && npm run test && npm run build && cd -
uv run pytest tests/ -v --ignore=tests/integration --ignore=tests/playwright
```

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/notes/widget-isolation-audit.md
# Add any code fixes the audit uncovered — e.g., specific JS / Python files.
git commit -m "audit(isolation): widget isolation audit [spec §5.4]

Grep-driven walk through frontend/viewer/src. Findings:
- _nextRequestId in anywidget-source.js — intentional global, confirmed benign.
- ADDITIVE_COLORMAP_EXT — stateless singleton, confirmed OK.
- window listener in keyboard.js — fixed in Task 4.
- [any new findings + their fixes]

See docs/superpowers/notes/widget-isolation-audit.md for the full walk."
```

---

## Task 6: Remote OME-Zarr renders (diagnostic loop)

**Goal:** Fix the "remote zarr loads but canvas stays black" bug [spec §5.3]. **No preemptive fix.** Write the failing integration test FIRST with a concrete non-black-pixel assertion; run it; diagnose via console + network logs; determine the root cause; fix the root cause.

**Files:**
- Create: `tests/integration/fixtures/demo_remote_zarr.py`
- Create: `tests/integration/test_remote_zarr_renders.py`
- Modify: `tests/integration/conftest.py` — add a `marimo_server_remote` + `widget_remote` fixture
- Modify: whatever the root cause turns out to be — **unknown at plan-authoring time**. Do not pre-commit to any specific file.

- [ ] **Step 1: Remote-zarr marimo fixture**

Create `tests/integration/fixtures/demo_remote_zarr.py`:

```python
"""Remote OME-Zarr fixture — loads a known-good public IDR URL [spec §5.3].

If IDR's URL changes or goes offline, swap for another known-good public zarr.
Verified upfront per risk §10 of the spec.
"""
import marimo

__generated_with = "0.19.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _():
    from anybioimage import BioImageViewer

    # IDR 9822151.zarr — a public multiscale OME-Zarr. Swap if flaky.
    URL = "https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0062A/6001240.zarr"
    viewer = BioImageViewer()
    viewer.set_image(URL)
    return (viewer,)


@app.cell
def _(mo, viewer):
    mo.ui.anywidget(viewer)
    return


if __name__ == "__main__":
    app.run()
```

- [ ] **Step 2: Add `marimo_server_remote` + `widget_remote` fixtures**

Append to `tests/integration/conftest.py`:

```python
@pytest.fixture(scope="session")
def marimo_server_remote():
    """Session-scoped remote-zarr notebook."""
    port = _pick_port()
    proc, url = _start_marimo(FIXTURES_DIR / "demo_remote_zarr.py", port)
    yield url
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture
def widget_remote(page, marimo_server_remote):
    from tests.integration.helpers.widget import WidgetHandle

    page.goto(marimo_server_remote)
    page.wait_for_load_state("networkidle")
    handle = WidgetHandle(page, widget_index=0)
    # Remote fetch is slow; give it 60 s to reach _render_ready.
    handle.wait_for_ready(timeout_ms=60000)
    return handle
```

- [ ] **Step 3: Write failing integration test**

Create `tests/integration/test_remote_zarr_renders.py`:

```python
"""Remote OME-Zarr render pixels [spec §5.3].

This test fails initially. After diagnosis, the root-cause fix makes it pass.
DO NOT silence this test, xfail it, or patch around it — the failure is the
signal that the fix is needed.
"""
from __future__ import annotations

import time

import pytest

from tests.integration.helpers.pixels import assert_non_black, sample_canvas


@pytest.mark.integration
def test_remote_zarr_renders_non_black(widget_remote, page):
    # wait_for_ready already blocks on _render_ready. Give the tiles another
    # 10 seconds to arrive — remote S3 round-trip time variability.
    t0 = time.time()
    while time.time() - t0 < 10:
        box = widget_remote.canvas_box()
        # Sample a 4×4 grid of canvas-center-ish coords.
        points = []
        for fx in (0.25, 0.40, 0.55, 0.70):
            for fy in (0.30, 0.45, 0.60, 0.75):
                points.append((int(box["w"] * fx), int(box["h"] * fy)))
        samples = sample_canvas(page, 0, points)
        has_color = any((r > 10 or g > 10 or b > 10) for (r, g, b, _a) in samples)
        if has_color:
            assert_non_black(samples)
            return
        page.wait_for_timeout(500)

    # Final assertion — will fail loudly with the samples included.
    box = widget_remote.canvas_box()
    points = [(int(box["w"] * 0.5), int(box["h"] * 0.5))]
    samples = sample_canvas(page, 0, points)
    assert_non_black(samples)
```

- [ ] **Step 4: Run the test; capture console + network logs**

```
uv run pytest tests/integration/test_remote_zarr_renders.py -v -m integration -s
```

Expected: **test fails.** This is not a bug; this is the method [spec §5.3].

Now diagnose. Temporarily replace the body of `test_remote_zarr_renders_non_black` in `tests/integration/test_remote_zarr_renders.py` with a console-dumping variant so a failed run prints the page console log. Replace the whole file with:

```python
"""Remote OME-Zarr render pixels — DIAGNOSTIC VARIANT [spec §5.3].

This is the diagnostic form. Revert to the original version (Step 3 above)
before committing — the console-dump wrapper is not meant to land.
"""
from __future__ import annotations

import time

import pytest

from tests.integration.helpers.pixels import assert_non_black, sample_canvas


def _dump_console(widget):
    pg = widget._page
    print(f"\n=== CONSOLE LOG ({len(pg._console_log)} entries) ===")
    for t, msg in pg._console_log:
        print(f"[{t}] {msg}")
    print("=== END CONSOLE LOG ===")


@pytest.mark.integration
def test_remote_zarr_renders_non_black(widget_remote, page):
    try:
        t0 = time.time()
        while time.time() - t0 < 10:
            box = widget_remote.canvas_box()
            points = []
            for fx in (0.25, 0.40, 0.55, 0.70):
                for fy in (0.30, 0.45, 0.60, 0.75):
                    points.append((int(box["w"] * fx), int(box["h"] * fy)))
            samples = sample_canvas(page, 0, points)
            has_color = any((r > 10 or g > 10 or b > 10) for (r, g, b, _a) in samples)
            if has_color:
                assert_non_black(samples)
                return
            page.wait_for_timeout(500)
        box = widget_remote.canvas_box()
        points = [(int(box["w"] * 0.5), int(box["h"] * 0.5))]
        samples = sample_canvas(page, 0, points)
        assert_non_black(samples)
    except Exception:
        _dump_console(widget_remote)
        raise
```

Run again. Read:
- Every `console.error` / `console.warn`.
- Network requests (open Playwright with `headless=False` + DevTools if the console log is insufficient).

**Determine the root cause.** Document it in the commit body of Step 6. Examples of what the diagnosis might reveal:

| Diagnosis | Fix location |
|---|---|
| CORS blocked on `.zattrs` | `zarr-source.js` — add fetch options + document limitation |
| Default contrast too narrow (all pixels clip to 0) | `channelState.js` or `image_loading.py` — default to auto-contrast on first render |
| Pyramid level selector picks missing level | `DeckCanvas.jsx` level picker — fix the math |
| Viv's `MultiscaleImageLayer` rejects the sources shape | `zarr-source.js` — post-process the returned sources |

**Do not pre-commit to a fix.** The plan's job ends at "here is the diagnostic loop." The fix is whatever the diagnosis reveals.

- [ ] **Step 5: Apply the root-cause fix**

Edit the specific file(s) the diagnosis points to. Keep the fix minimal — fix the root cause, don't patch around it. If the fix involves adding CORS config + a doc note, add the doc note to `README.md` "Remote zarr" subsection. If it involves changing default contrast, update the docstring for `_compute_channel_ranges` in `image_loading.py`. Remove the `_dump_console` helper added in Step 4 — that was diagnostic-only.

- [ ] **Step 6: Rebuild + rerun**

```
cd anybioimage/frontend/viewer && npm run build && cd -
uv run pytest tests/integration/test_remote_zarr_renders.py -v -m integration
```

Expected: green.

- [ ] **Step 7: Commit**

Explicitly enumerate the files the fix touched after diagnosis. Typical candidates (one of these, not all):
  - If CORS → `anybioimage/frontend/viewer/src/render/pixel-sources/zarr-source.js` + `README.md`
  - If contrast → `anybioimage/mixins/image_loading.py`
  - If pyramid selector → `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx`
  - If Viv rejects sources shape → `anybioimage/frontend/viewer/src/render/pixel-sources/zarr-source.js`

```bash
# Staging (the test file + fixture are always staged; add fix files enumerated above):
git add tests/integration/fixtures/demo_remote_zarr.py \
        tests/integration/conftest.py \
        tests/integration/test_remote_zarr_renders.py
# Add the specific fix file(s) identified by diagnosis — for example:
#   git add anybioimage/frontend/viewer/src/render/pixel-sources/zarr-source.js \
#           anybioimage/frontend/viewer/dist/viewer-bundle.js
git commit -m "fix(remote-zarr): render visible pixels [spec §5.3]

Root cause: <one-sentence root cause identified by the diagnostic run>

Fix: <one-sentence description of the fix, naming the file changed>

Integration test test_remote_zarr_renders.py samples a 4x4 pixel grid
after _render_ready + 10s of tile budget; asserts non-black."
```

---

## Task 7: Instrument remaining three hot paths

**Goal:** Complete the perf wiring — wrap the per-layer sub-memos in `DeckCanvas.jsx`, `AnywidgetPixelSource.getTile`, and `InteractionController.handlePointerEvent` [spec §3]. Build-only: no fix lands here. This task prepares Task 8 (baseline measurement).

**Files:**
- Modify: `anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.js`
- Modify: `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx` (stay monolithic for now — split is Task 9; just wrap the single big memo with `trace("layers:build", ...)` and add per-label timings inside.)
- Modify: `anybioimage/frontend/viewer/src/interaction/InteractionController.js` — already wrapped `handlePointerEvent` in Task 3; confirm still in place.

- [ ] **Step 1: Wrap `AnywidgetPixelSource.getTile`**

Modify `anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.js`:

```js
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
import { trace } from '../../util/perf.js';

const DTYPE_TO_VIV = {
  uint8: 'Uint8', uint16: 'Uint16', uint32: 'Uint32', float32: 'Float32',
};

const VIV_TO_ARRAY = {
  Uint8: Uint8Array, Uint16: Uint16Array, Uint32: Uint32Array, Float32: Float32Array,
};

let _nextRequestId = 1;

function toTypedArray(buf, Ctor) {
  if (!buf) return new Ctor(0);
  if (buf instanceof ArrayBuffer) {
    return new Ctor(buf, 0, buf.byteLength / Ctor.BYTES_PER_ELEMENT);
  }
  const backing = buf.buffer;
  const offset = buf.byteOffset | 0;
  const length = (buf.byteLength | 0) / Ctor.BYTES_PER_ELEMENT;
  return new Ctor(backing, offset, length);
}

export class AnywidgetPixelSource {
  constructor(model, { shape, dtype, tileSize = 512, level = 0, labels }) {
    this._model = model;
    this._level = level;
    this._tileSize = tileSize;
    this._dtype = dtype;
    this._shape = shape;
    this._labels = labels || ['t', 'c', 'z', 'y', 'x'];
    this._pending = new Map();

    this._pendingBatch = [];
    this._flushTimer = null;

    this._listener = (content, buffers) => {
      if (!content || content.kind !== 'chunk') return;
      const entry = this._pending.get(content.requestId);
      if (!entry) return;
      this._pending.delete(content.requestId);
      if (!content.ok) {
        entry.reject(new Error(content.error || 'chunk fetch failed'));
        return;
      }
      const Ctor = VIV_TO_ARRAY[this._dtype] || Uint8Array;
      entry.resolve({
        data: toTypedArray(buffers && buffers[0], Ctor),
        width: content.w,
        height: content.h,
      });
    };
    model.on('msg:custom', this._listener);
  }

  destroy() {
    this._model.off('msg:custom', this._listener);
    for (const entry of this._pending.values()) {
      entry.reject(new Error('pixel source destroyed'));
    }
    this._pending.clear();
    if (this._flushTimer !== null) {
      clearTimeout(this._flushTimer);
      this._flushTimer = null;
    }
    this._pendingBatch = [];
  }

  get shape() { return this._shape; }
  get labels() { return this._labels; }
  get tileSize() { return this._tileSize; }
  get dtype() { return this._dtype; }

  _flush() {
    this._flushTimer = null;
    const batch = this._pendingBatch.splice(0);
    for (const msg of batch) this._model.send(msg);
  }

  async getTile(args) {
    // trace() wraps the whole promise including the wait for Python's reply.
    // Label used by integration perf tests [spec §3].
    return trace('pixelSource:getTile', () => this._getTile(args));
  }

  async _getTile({ x, y, selection, signal }) {
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
      this._pendingBatch.push({
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
      if (this._flushTimer === null) {
        this._flushTimer = setTimeout(() => this._flush(), 0);
      }
    });
  }

  onTileError(err) {
    if (err && err.message === 'aborted') return;
    throw err;
  }

  async getRaster({ selection, signal }) {
    const [, , , yLen, xLen] = this._shape;
    const w = xLen; const h = yLen;
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

- [ ] **Step 2: Wrap the `layers` useMemo in DeckCanvas.jsx**

Modify `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx` — import `trace` at the top and wrap the final `layers` useMemo body. The per-layer sub-memos become dedicated Task 9 work — for now the big memo gets the single `layers:build` label plus inline sub-timings.

Add the import at the top:

```jsx
import { trace } from '../util/perf.js';
```

Replace the existing `layers` useMemo block with:

```jsx
  const layers = useMemo(() => trace('layers:build', () => {
    const out = [];
    if (imageLayerProps && imageVisible) {
      trace('layers:image', () => {
        out.push(new MultiscaleImageLayer({ id: 'viv-image', viewportId: 'ortho', ...imageLayerProps }));
      });
    }
    trace('layers:masks', () => { for (const l of maskLayers) out.push(l); });
    trace('layers:annotations', () => { for (const l of annotationLayers) out.push(l); });
    if (previewLayer) {
      trace('layers:preview', () => out.push(previewLayer));
    }
    if (scaleBarVisible && pixelSizeUm) {
      trace('layers:scaleBar', () => {
        out.push(buildScaleBarLayer({ pixelSizeUm, viewState, width, height }));
      });
    }
    return out;
  }), [imageLayerProps, imageVisible, maskLayers, annotationLayers, previewLayer,
      pixelSizeUm, scaleBarVisible, viewState, width, height]);
```

- [ ] **Step 3: Confirm `interaction:<phase>` is still wrapped**

```bash
grep -n "interaction:" anybioimage/frontend/viewer/src/interaction/InteractionController.js
```

Should show the `trace(\`interaction:${phase}\`, () => {` line from Task 3. If missing, re-apply the Task 3 wrap.

- [ ] **Step 4: Build + run unit tests**

```
cd anybioimage/frontend/viewer && npm run test && npm run build
```

Expected: all unit tests green; bundle builds. No behavior change.

- [ ] **Step 5: Commit**

```bash
git add anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.js \
        anybioimage/frontend/viewer/src/render/DeckCanvas.jsx \
        anybioimage/frontend/viewer/dist/viewer-bundle.js
git commit -m "feat(perf): instrument 3 remaining hot paths [spec §3]

Labels wired:
- pixelSource:getTile        (anywidget-source.js — whole promise)
- layers:build               (DeckCanvas.jsx — outer memo)
- layers:image, layers:masks, layers:annotations,
  layers:preview, layers:scaleBar (inner per-type scopes)
- interaction:<phase>        (InteractionController — from Task 3)

Build-only; no behavior change. Task 8 captures baseline; Task 9 splits
the monolithic layers memo to cut rebuilds on channel-only changes."
```

---

## Task 8: Baseline perf measurement

**Goal:** First run of the three perf integration tests against the unchanged code. Commit the numbers as evidence of where we started. No fix yet. [spec §9 step 4]

**Files:**
- Create: `tests/integration/test_channel_toggle_perf.py`
- Create: `tests/integration/test_t_scrub_perf.py`
- Create: `tests/integration/test_z_scrub_perf.py`
- Create: `docs/superpowers/notes/phase2-5-perf-baseline.md`

- [ ] **Step 1: Channel-toggle perf test**

Create `tests/integration/test_channel_toggle_perf.py`:

```python
"""Channel toggle → next paint p95 ≤ 16 ms [spec §1 perf budget].

Labels checked:
  layers:image   — per-layer rebuild time when _channel_settings flips.
  layers:build   — outer memo wall time.

This test fails BASELINE (Task 8), passes after Task 9 splits the monolithic
layers useMemo into per-layer sub-memos.
"""
from __future__ import annotations

import os

import pytest


BUDGET_MS = 16.0 * float(os.environ.get("ANYBIOIMAGE_PERF_BUDGET_MULTIPLIER", "1.0"))
WARMUP = 10
MEASURE = 30


def _toggle_channel(widget, idx: int) -> None:
    settings = widget.get("_channel_settings") or []
    if not settings:
        return
    s = list(settings)
    s[idx] = {**s[idx], "visible": not s[idx].get("visible", True)}
    widget.set("_channel_settings", s)


@pytest.mark.integration
def test_channel_toggle_meets_budget(widget):
    widget.clear_perf()
    for _ in range(WARMUP):
        _toggle_channel(widget, 0)
        _toggle_channel(widget, 0)
    widget.clear_perf()
    for _ in range(MEASURE):
        _toggle_channel(widget, 0)
        _toggle_channel(widget, 0)

    widget._page.wait_for_timeout(300)  # settle
    p95 = widget.perf_p95("layers:image")
    assert p95 <= BUDGET_MS, f"channel toggle layers:image p95 = {p95:.2f} ms > {BUDGET_MS:.2f} ms budget"
```

- [ ] **Step 2: T-scrub perf test**

Create `tests/integration/test_t_scrub_perf.py`:

```python
"""T slider scrub p95 ≤ 30 ms per step [spec §1 perf budget].

The demo_small.py fixture has dim_t == 1 — change it to 5 to enable this
test, OR use a dedicated larger fixture. For simplicity, we use set_trait
to cycle between current_t = 0 and current_t = 1 after forcing dim_t to 5
via a separate fixture (not worth adding; small-scrub is representative).

BASELINE task: runs + measures; does not flip scrub_perf_verified.
Task 14 introduces verify_scrub_perf() which, on pass, flips the trait.
"""
from __future__ import annotations

import os

import pytest


BUDGET_MS = 30.0 * float(os.environ.get("ANYBIOIMAGE_PERF_BUDGET_MULTIPLIER", "1.0"))
WARMUP = 10
MEASURE = 30


@pytest.mark.integration
def test_t_scrub_meets_budget(widget):
    dim_t = widget.get("dim_t") or 1
    if dim_t <= 1:
        pytest.skip("fixture has dim_t <= 1; T-scrub N/A")

    widget.clear_perf()
    cur = widget.get("current_t") or 0
    for i in range(WARMUP):
        widget.set("current_t", (cur + i) % dim_t)
    widget.clear_perf()
    for i in range(MEASURE):
        widget.set("current_t", (cur + i) % dim_t)

    widget._page.wait_for_timeout(300)
    p95 = widget.perf_p95("pixelSource:getTile")
    assert p95 <= BUDGET_MS, f"T scrub pixelSource:getTile p95 = {p95:.2f} ms > {BUDGET_MS:.2f} ms budget"
```

- [ ] **Step 3: Z-scrub perf test**

Create `tests/integration/test_z_scrub_perf.py`:

```python
"""Z slider scrub p95 ≤ 30 ms per step [spec §1 perf budget]."""
from __future__ import annotations

import os

import pytest


BUDGET_MS = 30.0 * float(os.environ.get("ANYBIOIMAGE_PERF_BUDGET_MULTIPLIER", "1.0"))
WARMUP = 10
MEASURE = 30


@pytest.mark.integration
def test_z_scrub_meets_budget(widget):
    dim_z = widget.get("dim_z") or 1
    if dim_z <= 1:
        pytest.skip("fixture has dim_z <= 1; Z-scrub N/A")

    widget.clear_perf()
    cur = widget.get("current_z") or 0
    for i in range(WARMUP):
        widget.set("current_z", (cur + i) % dim_z)
    widget.clear_perf()
    for i in range(MEASURE):
        widget.set("current_z", (cur + i) % dim_z)

    widget._page.wait_for_timeout(300)
    p95 = widget.perf_p95("pixelSource:getTile")
    assert p95 <= BUDGET_MS, f"Z scrub pixelSource:getTile p95 = {p95:.2f} ms > {BUDGET_MS:.2f} ms budget"
```

- [ ] **Step 4: Update `demo_small.py` to give dim_t = 5 + dim_z = 3 so scrub tests have data**

Edit `tests/integration/fixtures/demo_small.py` — the `img` ndarray. Change:

```python
    img = rng.integers(10000, 50000, size=(1, 3, 1, 256, 256), dtype=np.uint16)
```

to:

```python
    img = rng.integers(10000, 50000, size=(5, 3, 3, 256, 256), dtype=np.uint16)
```

- [ ] **Step 5: Run all three; expect channel-toggle to FAIL (monolithic memo), scrub to pass-or-fail depending on hardware**

```
uv run pytest tests/integration/test_channel_toggle_perf.py \
              tests/integration/test_t_scrub_perf.py \
              tests/integration/test_z_scrub_perf.py \
              -v -m integration -s
```

Capture the p95 for each label from the output.

- [ ] **Step 6: Write the baseline note**

Create `docs/superpowers/notes/phase2-5-perf-baseline.md`:

```markdown
# Phase 2.5 — baseline perf numbers

**Date:** 2026-04-19
**Branch:** feature/viv-backend
**Commit before fixes:** <SHA at this task's commit>
**Hardware:** <filled in — CPU / GPU / OS>

Captured via `uv run pytest tests/integration/test_*_perf.py -v -m integration -s`.

| Label                      | Test                        | p50   | p95   | p99   | Budget  | Status   |
|----------------------------|-----------------------------|-------|-------|-------|---------|----------|
| layers:image               | channel toggle              | X.XX  | X.XX  | X.XX  | 16 ms   | FAIL/PASS |
| layers:build               | channel toggle              | X.XX  | X.XX  | X.XX  | n/a     | —        |
| pixelSource:getTile        | T scrub                     | X.XX  | X.XX  | X.XX  | 30 ms   | FAIL/PASS |
| pixelSource:getTile        | Z scrub                     | X.XX  | X.XX  | X.XX  | 30 ms   | FAIL/PASS |
| interaction:up             | click (manual, if possible) | X.XX  | X.XX  | X.XX  | n/a     | —        |

## Notes

- Channel toggle baseline is expected to exceed the 16 ms budget because
  the Phase-2 layers useMemo rebuilds every layer on every
  `_channel_settings` mutation. Task 9 splits the memo.
- T/Z scrub baseline depends on the chunk-bridge round-trip — no prefetch
  yet; Task 10 adds prefetch on settle.
- All budgets include a 1.5× multiplier on CI (ANYBIOIMAGE_PERF_BUDGET_MULTIPLIER).
```

Fill in the X.XX values from the test-run output.

- [ ] **Step 7: Commit**

```bash
git add tests/integration/test_channel_toggle_perf.py \
        tests/integration/test_t_scrub_perf.py \
        tests/integration/test_z_scrub_perf.py \
        tests/integration/fixtures/demo_small.py \
        docs/superpowers/notes/phase2-5-perf-baseline.md
git commit -m "test(perf): baseline channel-toggle + T/Z scrub [spec §9 step 4]

Baseline numbers captured:
- layers:image channel-toggle p95 = <X> ms (budget 16 ms, <FAIL/PASS>)
- pixelSource:getTile T-scrub p95 = <X> ms (budget 30 ms, <FAIL/PASS>)
- pixelSource:getTile Z-scrub p95 = <X> ms (budget 30 ms, <FAIL/PASS>)

See docs/superpowers/notes/phase2-5-perf-baseline.md for full table.
No fix in this commit — Tasks 9 (monolithic memo split) and 10 (T/Z prefetch)
deliver the fixes."
```

---

## Task 9: Split monolithic `layers` useMemo

**Goal:** Channel-toggle p95 ≤ 16 ms [spec §6.1]. Split the `layers` useMemo into per-type sub-memos with minimal dep lists. Image-only sub-memo depends on `imageLayerProps` + `imageVisible`; mask sub-memo on `maskLayers`; annotation sub-memo on `annotationLayers`; preview on `previewLayer`; scale-bar on its specific deps. The final `layers` array is a cheap `[image, ...masks, ...anns, preview, scaleBar]` reassembly.

**Files:**
- Modify: `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx`

- [ ] **Step 1: Capture the BEFORE p95 one more time (sanity check)**

```
uv run pytest tests/integration/test_channel_toggle_perf.py -v -m integration -s
```

Note the p95. Include in commit body.

- [ ] **Step 2: Split the memo**

Modify `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx` — replace the single `layers` useMemo block:

```jsx
  // Per-type sub-memos [spec §6.1] — each rebuild is scoped to the traits
  // that actually feed it. Channel toggles change imageLayerProps only;
  // mask / annotation / preview / scaleBar memos don't rerun.

  const imageLayerMemo = useMemo(() => trace('layers:image', () => {
    if (!imageLayerProps || !imageVisible) return null;
    return new MultiscaleImageLayer({ id: 'viv-image', viewportId: 'ortho', ...imageLayerProps });
  }), [imageLayerProps, imageVisible]);

  const maskLayersMemo = useMemo(
    () => trace('layers:masks', () => maskLayers.slice()),
    [maskLayers]);

  const annotationLayersMemo = useMemo(
    () => trace('layers:annotations', () => annotationLayers.slice()),
    [annotationLayers]);

  const previewLayerMemo = useMemo(
    () => trace('layers:preview', () => previewLayer),
    [previewLayer]);

  const scaleBarLayerMemo = useMemo(() => trace('layers:scaleBar', () => {
    if (!(scaleBarVisible && pixelSizeUm)) return null;
    return buildScaleBarLayer({ pixelSizeUm, viewState, width, height });
  }), [scaleBarVisible, pixelSizeUm, viewState, width, height]);

  // Final assembly — cheap array concat, no layer construction here.
  const layers = useMemo(() => trace('layers:build', () => {
    const out = [];
    if (imageLayerMemo) out.push(imageLayerMemo);
    for (const l of maskLayersMemo) out.push(l);
    for (const l of annotationLayersMemo) out.push(l);
    if (previewLayerMemo) out.push(previewLayerMemo);
    if (scaleBarLayerMemo) out.push(scaleBarLayerMemo);
    return out;
  }), [imageLayerMemo, maskLayersMemo, annotationLayersMemo, previewLayerMemo, scaleBarLayerMemo]);
```

- [ ] **Step 3: Rebuild + run channel-toggle perf test**

```
cd anybioimage/frontend/viewer && npm run build && cd -
uv run pytest tests/integration/test_channel_toggle_perf.py -v -m integration -s
```

Expected: p95 drops; test now passes the 16 ms budget. Capture the AFTER p95 for the commit body.

If it still fails, dig deeper per spec §6.1 — check whether `imageLayerProps`'s `colors` / `contrastLimits` arrays are getting new identities unnecessarily, or whether `MultiscaleImageLayer.updateState` is comparing `extensions` by reference. Do not move on until the budget is met.

- [ ] **Step 4: Run the full integration suite to make sure nothing regressed**

```
uv run pytest tests/integration/ -v -m integration
```

Expected: every integration test still passes.

- [ ] **Step 5: Commit**

```bash
git add anybioimage/frontend/viewer/src/render/DeckCanvas.jsx \
        anybioimage/frontend/viewer/dist/viewer-bundle.js
git commit -m "perf(layers): split monolithic layers useMemo into per-type sub-memos [spec §6.1]

Before (channel toggle, layers:image p95): <X> ms
After  (channel toggle, layers:image p95): <Y> ms (≤ 16 ms budget)

Each sub-memo (image, masks, annotations, preview, scaleBar) depends only
on its own inputs. Channel-setting mutations now rebuild only the image
layer; masks/annotations/preview/scaleBar memos are hits.

Final layers array is a cheap reassembly — no allocations inside the hot
path."
```

---

## Task 10: Pre-fetch on T/Z scrub settle

**Goal:** T/Z scrub p95 ≤ 30 ms [spec §6.2]. Add `prefetch({ t, z, halfWindow })` to `AnywidgetPixelSource` and call it from `DeckCanvas.jsx` on a 100 ms-debounced settle of `current_t` / `current_z`. Cancel outstanding prefetch when the user moves again.

**Files:**
- Modify: `anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.js`
- Modify: `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx`

- [ ] **Step 1: Capture BEFORE p95**

```
uv run pytest tests/integration/test_t_scrub_perf.py \
              tests/integration/test_z_scrub_perf.py \
              -v -m integration -s
```

- [ ] **Step 2: Add `prefetch` to `AnywidgetPixelSource`**

Modify `anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.js` — add a new method + constructor state:

In the constructor, after `this._pendingBatch = []; this._flushTimer = null;`, add:

```js
    // Prefetch manager [spec §6.2] — tracks in-flight prefetch AbortControllers
    // so a new scrub cancels the previous prefetch window.
    this._prefetchAbort = null;
```

Update `destroy()` to abort any outstanding prefetch:

```js
  destroy() {
    this._model.off('msg:custom', this._listener);
    for (const entry of this._pending.values()) {
      entry.reject(new Error('pixel source destroyed'));
    }
    this._pending.clear();
    if (this._flushTimer !== null) {
      clearTimeout(this._flushTimer);
      this._flushTimer = null;
    }
    this._pendingBatch = [];
    if (this._prefetchAbort) {
      this._prefetchAbort.abort();
      this._prefetchAbort = null;
    }
  }
```

Add the new method after `getRaster`:

```js
  /**
   * Prefetch tiles for t±halfWindow and z±halfWindow at the given viewport.
   * Called on scrub settle from DeckCanvas. Cancels any previous outstanding
   * prefetch so only the most recent settle wins. [spec §6.2]
   *
   *   viewport: { tx0, ty0, tx1, ty1, currentC: number[] } — tile bounds +
   *             which channels are visible (prefetch all visible channels).
   */
  prefetch({ t, z, halfWindow = 1, viewport }) {
    if (!viewport) return;
    if (this._prefetchAbort) this._prefetchAbort.abort();
    this._prefetchAbort = new AbortController();
    const { signal } = this._prefetchAbort;

    const { tx0, ty0, tx1, ty1, currentC } = viewport;
    const channels = Array.isArray(currentC) && currentC.length ? currentC : [0];

    const neighbors = [];
    for (let dt = -halfWindow; dt <= halfWindow; dt++) {
      for (let dz = -halfWindow; dz <= halfWindow; dz++) {
        if (dt === 0 && dz === 0) continue;    // current slice is not a prefetch target
        const tt = t + dt;
        const zz = z + dz;
        if (tt < 0 || zz < 0) continue;
        const [dimT, , dimZ] = this._shape;
        if (tt >= dimT || zz >= dimZ) continue;
        neighbors.push({ t: tt, z: zz });
      }
    }

    for (const { t: tt, z: zz } of neighbors) {
      for (const c of channels) {
        for (let ty = ty0; ty <= ty1; ty++) {
          for (let tx = tx0; tx <= tx1; tx++) {
            // Fire-and-forget; swallow aborted errors so the console stays clean.
            this.getTile({ x: tx, y: ty, selection: { t: tt, c, z: zz }, signal })
                .catch((e) => {
                  if (e && e.message === 'aborted') return;
                  // Other errors still swallowed — prefetch is best-effort.
                });
          }
        }
      }
    }
  }
```

- [ ] **Step 3: Debounced prefetch call from DeckCanvas on T/Z settle**

Modify `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx` — add a useEffect that watches `currentT` / `currentZ` and fires `source.prefetch` 100 ms after the last change:

Add near the other useEffects, after the image-layer ready signal:

```jsx
  // Prefetch window [spec §6.2] — 100 ms after the last T/Z change, fire a
  // prefetch for t±1 and z±1 tiles over the current viewport. Cancelled
  // automatically by source.prefetch() if another settle arrives first.
  useEffect(() => {
    if (!sources || !sources.length) return;
    const src = sources[0];
    if (!src || typeof src.prefetch !== 'function') return;   // zarr path has no prefetch

    const id = setTimeout(() => {
      // Current viewport as tile range. Use a coarse 3×3 tile fallback if
      // viewState is missing; the actual range is computed by the image
      // layer when tiles are requested, and any superset is safe.
      const currentC = (channelSettings || [])
        .map((ch, idx) => (ch.visible ? (ch.index ?? idx) : -1))
        .filter((i) => i >= 0);
      src.prefetch({
        t: currentT || 0,
        z: currentZ || 0,
        halfWindow: 1,
        viewport: { tx0: 0, ty0: 0, tx1: 3, ty1: 3, currentC },
      });
    }, 100);
    return () => clearTimeout(id);
  }, [sources, currentT, currentZ, channelSettings]);
```

- [ ] **Step 4: Rebuild + run T/Z-scrub perf tests**

```
cd anybioimage/frontend/viewer && npm run build && cd -
uv run pytest tests/integration/test_t_scrub_perf.py \
              tests/integration/test_z_scrub_perf.py \
              -v -m integration -s
```

Expected: T/Z scrub p95 drops (prefetched tiles land in the Python-side cache, so subsequent `getTile` calls are cache hits). Budget 30 ms met.

If T-scrub is green but Z-scrub isn't, or vice versa — do NOT widen the halfWindow speculatively. Dig into whichever axis fails and measure what's actually slow.

- [ ] **Step 5: Run full integration suite**

```
uv run pytest tests/integration/ -v -m integration
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.js \
        anybioimage/frontend/viewer/src/render/DeckCanvas.jsx \
        anybioimage/frontend/viewer/dist/viewer-bundle.js
git commit -m "perf(prefetch): T/Z scrub prefetch window [spec §6.2]

Before (T-scrub pixelSource:getTile p95): <X> ms
After  (T-scrub pixelSource:getTile p95): <Y> ms (≤ 30 ms budget)
Before (Z-scrub pixelSource:getTile p95): <X> ms
After  (Z-scrub pixelSource:getTile p95): <Y> ms (≤ 30 ms budget)

AnywidgetPixelSource.prefetch({t, z, halfWindow, viewport}) fires tile
requests for t±1 and z±1 at the current viewport, using an AbortController
that a subsequent settle cancels.

DeckCanvas debounces current_t/current_z changes at 100 ms and calls
prefetch — pre-warmed Python-side cache makes the next real getTile a hit."
```

---

## Task 11: `chrome/icons.js` + Toolbar SVG icon migration

**Goal:** Replace every single-letter / emoji toolbar button with an accessible inline SVG icon [spec §7.1]. `aria-label` + `title` on every button.

**Files:**
- Create: `anybioimage/frontend/viewer/src/chrome/icons.js`
- Modify: `anybioimage/frontend/viewer/src/chrome/Toolbar.jsx`

- [ ] **Step 1: Create the icon module**

Create `anybioimage/frontend/viewer/src/chrome/icons.js`:

```jsx
// anybioimage/frontend/viewer/src/chrome/icons.js
/**
 * Inline SVG icon set for the toolbar + chrome [spec §7.1].
 * Heroicons-style stroke-based. 24×24 viewBox. currentColor-driven so
 * the toolbar's color state (hover, active, disabled) applies.
 *
 * Storage: inlined here, no network fetch. Each export is a React element.
 */
import React from 'react';

function Icon({ children, label }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg"
         viewBox="0 0 24 24"
         fill="none"
         stroke="currentColor"
         strokeWidth={2}
         strokeLinecap="round"
         strokeLinejoin="round"
         aria-hidden="true"
         focusable="false">
      {children}
    </svg>
  );
}

export const ICONS = {
  pan: (
    <Icon>
      {/* Four-arrow move cursor */}
      <path d="M12 3v18M3 12h18M7 7l5-4 5 4M7 17l5 4 5-4M7 7l-4 5 4 5M17 7l4 5-4 5" />
    </Icon>
  ),
  select: (
    <Icon>
      {/* Arrow cursor */}
      <path d="M4 3l16 9-7 2-2 7z" />
    </Icon>
  ),
  rect: (
    <Icon>
      <rect x="4" y="4" width="16" height="16" rx="1" />
    </Icon>
  ),
  polygon: (
    <Icon>
      <path d="M12 3l9 6-3 11H6L3 9z" />
    </Icon>
  ),
  point: (
    <Icon>
      <circle cx="12" cy="12" r="3" fill="currentColor" />
      <circle cx="12" cy="12" r="8" />
    </Icon>
  ),
  line: (
    <Icon>
      <path d="M4 20L20 4" />
      <circle cx="4" cy="20" r="1.5" fill="currentColor" />
      <circle cx="20" cy="4" r="1.5" fill="currentColor" />
    </Icon>
  ),
  areaMeasure: (
    <Icon>
      <path d="M4 20h16M4 20L12 4l8 16" />
    </Icon>
  ),
  lineProfile: (
    <Icon>
      <path d="M3 17c3-6 6-6 9 0s6 6 9 0" />
    </Icon>
  ),
  reset: (
    <Icon>
      <path d="M3 12a9 9 0 1 0 3-6.7" />
      <path d="M3 4v5h5" />
    </Icon>
  ),
  layers: (
    <Icon>
      <path d="M12 3l9 5-9 5-9-5 9-5z" />
      <path d="M3 13l9 5 9-5" />
      <path d="M3 18l9 5 9-5" />
    </Icon>
  ),
  play: (
    <Icon>
      <path d="M7 4l13 8-13 8z" fill="currentColor" />
    </Icon>
  ),
  pause: (
    <Icon>
      <rect x="6" y="4" width="4" height="16" fill="currentColor" />
      <rect x="14" y="4" width="4" height="16" fill="currentColor" />
    </Icon>
  ),
};

// Aria labels for tools keyed by mode id; Toolbar.jsx reads these for aria-label.
export const TOOL_ARIA = {
  pan: 'Pan',
  select: 'Select',
  rect: 'Rectangle',
  polygon: 'Polygon',
  point: 'Point',
  line: 'Line',
  areaMeasure: 'Area measure',
  lineProfile: 'Line profile',
};

// Keyboard-shortcut letter keyed by mode id; Toolbar.jsx appends "(X)" to title.
export const TOOL_SHORTCUT = {
  pan: 'P',
  select: 'V',
  rect: 'R',
  polygon: 'G',
  point: 'O',
  line: 'L',
  areaMeasure: 'M',
};
```

- [ ] **Step 2: Rewrite Toolbar.jsx**

Modify `anybioimage/frontend/viewer/src/chrome/Toolbar.jsx`:

```jsx
// anybioimage/frontend/viewer/src/chrome/Toolbar.jsx
import React from 'react';
import { useModelTrait } from '../model/useModelTrait.js';
import { ICONS, TOOL_ARIA, TOOL_SHORTCUT } from './icons.js';

function ToolButton({ model, mode, disabled }) {
  const current = useModelTrait(model, 'tool_mode');
  const active = current === mode;
  const aria = TOOL_ARIA[mode] || mode;
  const shortcut = TOOL_SHORTCUT[mode];
  const title = shortcut ? `${aria} (${shortcut})` : aria;
  return (
    <button
      className={'tool-btn' + (active ? ' active' : '')}
      disabled={disabled}
      aria-label={aria}
      aria-pressed={active}
      title={title}
      onClick={() => { model.set('tool_mode', mode); model.save_changes(); }}
    >{ICONS[mode]}</button>
  );
}

export function Toolbar({ model, onToggleLayers, panelOpen }) {
  const phase3Disabled = true;   // line / areaMeasure land in Phase 3
  return (
    <div className="toolbar">
      <div className="tool-group">
        <ToolButton model={model} mode="pan" />
        <ToolButton model={model} mode="select" />
      </div>
      <div className="toolbar-separator" />
      <div className="tool-group">
        <ToolButton model={model} mode="rect" />
        <ToolButton model={model} mode="polygon" />
        <ToolButton model={model} mode="point" />
        <ToolButton model={model} mode="line" disabled={phase3Disabled} />
        <ToolButton model={model} mode="areaMeasure" disabled={phase3Disabled} />
      </div>
      <div className="toolbar-separator" />
      <button className="tool-btn"
              aria-label="Reset view"
              title="Reset view"
              onClick={() => model.send({ kind: 'reset-view' })}>{ICONS.reset}</button>
      <div className="toolbar-separator" />
      <button className={'layers-btn' + (panelOpen ? ' active' : '')}
              aria-label="Toggle layers panel"
              aria-pressed={panelOpen}
              title="Toggle layers panel"
              onClick={onToggleLayers}>
        <span>{ICONS.layers}</span><span> Layers</span>
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Build + visual check**

```
cd anybioimage/frontend/viewer && npm run test && npm run build
```

Bundle should still be under 4 MB (new SVGs are ~1 KB total). Run `npm run size` to confirm.

- [ ] **Step 4: Update `WidgetHandle.click_tool()` to still work**

Since the `title` prefix still starts with the aria label (e.g., `"Rectangle (R)"`), `click_tool("Rectangle")` still matches. No test updates needed. Confirm:

```
uv run pytest tests/integration/ -v -m integration
```

- [ ] **Step 5: Commit**

```bash
git add anybioimage/frontend/viewer/src/chrome/icons.js \
        anybioimage/frontend/viewer/src/chrome/Toolbar.jsx \
        anybioimage/frontend/viewer/dist/viewer-bundle.js
git commit -m "feat(ux): SVG icon set + accessible toolbar buttons [spec §7.1]

icons.js exports Heroicons-style stroke-based SVGs for pan, select, rect,
polygon, point, line, areaMeasure, lineProfile, reset, layers, play, pause.

Toolbar.jsx switches from single-letter text to ICONS[mode]. Every button
carries aria-label + aria-pressed + title with the shortcut letter.
No single-letter visible text remains on the toolbar.

Bundle size unchanged within noise (<1 KB delta)."
```

---

## Task 12: `NumericInput.jsx` component + tests

**Goal:** A reusable numeric-entry widget to pair with sliders [spec §7.2]. Two-way bound with the slider via the parent's state. Validates on blur or Enter; reverts on invalid.

**Files:**
- Create: `anybioimage/frontend/viewer/src/chrome/NumericInput.jsx`
- Create: `anybioimage/frontend/viewer/src/chrome/NumericInput.test.jsx`

- [ ] **Step 1: Write failing vitest**

Create `anybioimage/frontend/viewer/src/chrome/NumericInput.test.jsx`:

```jsx
// anybioimage/frontend/viewer/src/chrome/NumericInput.test.jsx
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import { NumericInput } from './NumericInput.jsx';

describe('NumericInput', () => {
  it('renders the passed-in value formatted', () => {
    const { container } = render(
      <NumericInput value={0.5} min={0} max={1} step={0.01} format={(n) => n.toFixed(2)} onCommit={() => {}} />
    );
    const input = container.querySelector('input');
    expect(input.value).toBe('0.50');
  });

  it('commits a valid value on Enter', () => {
    const onCommit = vi.fn();
    const { container } = render(
      <NumericInput value={0.5} min={0} max={1} step={0.01} format={(n) => n.toFixed(2)} onCommit={onCommit} />
    );
    const input = container.querySelector('input');
    fireEvent.change(input, { target: { value: '0.75' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onCommit).toHaveBeenCalledWith(0.75);
  });

  it('commits a valid value on blur', () => {
    const onCommit = vi.fn();
    const { container } = render(
      <NumericInput value={0.5} min={0} max={1} step={0.01} format={(n) => n.toFixed(2)} onCommit={onCommit} />
    );
    const input = container.querySelector('input');
    fireEvent.change(input, { target: { value: '0.8' } });
    fireEvent.blur(input);
    expect(onCommit).toHaveBeenCalledWith(0.8);
  });

  it('reverts on invalid input', () => {
    const onCommit = vi.fn();
    const { container } = render(
      <NumericInput value={0.5} min={0} max={1} step={0.01} format={(n) => n.toFixed(2)} onCommit={onCommit} />
    );
    const input = container.querySelector('input');
    fireEvent.change(input, { target: { value: 'abc' } });
    fireEvent.blur(input);
    expect(onCommit).not.toHaveBeenCalled();
    expect(input.value).toBe('0.50');
  });

  it('clamps out-of-range to min/max', () => {
    const onCommit = vi.fn();
    const { container } = render(
      <NumericInput value={0.5} min={0} max={1} step={0.01} format={(n) => n.toFixed(2)} onCommit={onCommit} />
    );
    const input = container.querySelector('input');
    fireEvent.change(input, { target: { value: '5' } });
    fireEvent.blur(input);
    expect(onCommit).toHaveBeenCalledWith(1);
  });

  it('reverts on Escape without committing', () => {
    const onCommit = vi.fn();
    const { container } = render(
      <NumericInput value={0.5} min={0} max={1} step={0.01} format={(n) => n.toFixed(2)} onCommit={onCommit} />
    );
    const input = container.querySelector('input');
    fireEvent.change(input, { target: { value: '0.9' } });
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(onCommit).not.toHaveBeenCalled();
    expect(input.value).toBe('0.50');
  });

  it('reflects prop changes when not editing', () => {
    const { container, rerender } = render(
      <NumericInput value={0.5} min={0} max={1} step={0.01} format={(n) => n.toFixed(2)} onCommit={() => {}} />
    );
    const input = container.querySelector('input');
    expect(input.value).toBe('0.50');
    rerender(<NumericInput value={0.75} min={0} max={1} step={0.01} format={(n) => n.toFixed(2)} onCommit={() => {}} />);
    expect(input.value).toBe('0.75');
  });
});
```

- [ ] **Step 2: Install `@testing-library/react`**

Check `package.json` — if `@testing-library/react` is already present (Phase 2 added it for existing jsx tests), skip. Otherwise:

```bash
cd anybioimage/frontend/viewer
npm install --save-dev @testing-library/react
cd -
```

- [ ] **Step 3: Run — expect fail**

```
cd anybioimage/frontend/viewer && npm run test -- src/chrome/NumericInput.test.jsx
```

Expected: module not found.

- [ ] **Step 4: Implement `NumericInput.jsx`**

Create `anybioimage/frontend/viewer/src/chrome/NumericInput.jsx`:

```jsx
// anybioimage/frontend/viewer/src/chrome/NumericInput.jsx
import React, { useState, useEffect, useRef } from 'react';

/**
 * Numeric entry paired with a slider [spec §7.2].
 *
 * Props:
 *   value     — current canonical value (from the parent).
 *   min, max  — bounds (inclusive). Out-of-range commits clamp.
 *   step      — used for the native number input spinner.
 *   format    — (n) => string, how the committed value is rendered in the input.
 *   onCommit  — (n) => void, called with the parsed + clamped number.
 *   disabled, style, className — standard DOM passthroughs.
 *
 * Behavior:
 *   - When not editing (input not focused), displays format(value).
 *   - While editing, tracks the user's raw text. Enter or blur triggers commit.
 *   - Escape reverts without committing.
 *   - Invalid parse → revert; no onCommit call.
 */
function parseNumber(raw) {
  const s = String(raw).trim();
  if (s === '') return null;
  const n = Number(s);
  if (!Number.isFinite(n)) return null;
  return n;
}

export function NumericInput({
  value, min, max, step = 'any',
  format = (n) => String(n),
  onCommit, disabled, style, className,
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(() => format(value));
  const inputRef = useRef(null);

  // When the canonical value changes externally (slider drag), refresh the
  // displayed text — but only if the user isn't mid-edit.
  useEffect(() => {
    if (!editing) setDraft(format(value));
  }, [value, format, editing]);

  function commit() {
    const n = parseNumber(draft);
    if (n === null) {
      setDraft(format(value));   // revert
      return;
    }
    const clamped = Math.max(min, Math.min(max, n));
    onCommit(clamped);
    setDraft(format(clamped));
  }

  function onKeyDown(e) {
    if (e.key === 'Enter') {
      commit();
      inputRef.current?.blur();
    } else if (e.key === 'Escape') {
      setDraft(format(value));
      setEditing(false);
      inputRef.current?.blur();
    }
  }

  return (
    <input
      ref={inputRef}
      type="text"
      inputMode="decimal"
      className={className}
      style={style}
      value={draft}
      disabled={disabled}
      step={step}
      onFocus={() => setEditing(true)}
      onChange={(e) => { setEditing(true); setDraft(e.target.value); }}
      onBlur={() => { commit(); setEditing(false); }}
      onKeyDown={onKeyDown}
    />
  );
}
```

- [ ] **Step 5: Re-run tests**

```
cd anybioimage/frontend/viewer && npm run test -- src/chrome/NumericInput.test.jsx
```

Expected: all 7 tests pass.

- [ ] **Step 6: Full JS test sweep**

```
cd anybioimage/frontend/viewer && npm run test
```

All green.

- [ ] **Step 7: Commit**

```bash
git add anybioimage/frontend/viewer/src/chrome/NumericInput.jsx \
        anybioimage/frontend/viewer/src/chrome/NumericInput.test.jsx \
        anybioimage/frontend/viewer/package.json \
        anybioimage/frontend/viewer/package-lock.json
git commit -m "feat(ux): NumericInput component + tests [spec §7.2]

Reusable numeric entry — two-way bound via parent state, validates on
blur/Enter, reverts on invalid, Escape cancels, clamps to [min, max].

7 vitest cases cover: format-on-mount, Enter commit, blur commit, invalid
revert, out-of-range clamp, Escape revert, external prop update."
```

---

## Task 13: ImageSection integration — numeric inputs + reset-gamma + data-value toggle

**Goal:** Wire `NumericInput` into min/max/gamma rows [spec §7.2, §7.3, §7.5]. Add a `1` reset-gamma button. Add a per-channel `%` toggle for min/max unit display. Default to data-value display (integer for integer dtypes, 4-sig-fig float).

**Files:**
- Modify: `anybioimage/frontend/viewer/src/chrome/LayersPanel/ImageSection.jsx`

- [ ] **Step 1: Helper — dtype-aware formatters**

Prepend this helper block to `ImageSection.jsx`, right under the imports:

```jsx
// anybioimage/frontend/viewer/src/chrome/LayersPanel/ImageSection.jsx
import React, { useState } from 'react';
import { useModelTrait } from '../../model/useModelTrait.js';
import { listLuts } from '../../render/luts/index.js';
import { NumericInput } from '../NumericInput.jsx';

// --- data-value formatting [spec §7.5] ---

// Dtype → (value: number) => string.
// Stored trait is normalized [0, 1]; display transforms to data-value
// using ch.data_min / ch.data_max. The normalized → data conversion:
//   data = data_min + normalized * (data_max - data_min)
function normalizedToData(norm, ch) {
  const dmin = ch.data_min ?? 0;
  const dmax = ch.data_max ?? 65535;
  return dmin + norm * (dmax - dmin);
}
function dataToNormalized(data, ch) {
  const dmin = ch.data_min ?? 0;
  const dmax = ch.data_max ?? 65535;
  const span = Math.max(dmax - dmin, 1);
  return (data - dmin) / span;
}

function integerFormat(n) { return Math.round(n).toString(); }
function scientificFormat(n) {
  if (n === 0) return '0';
  const abs = Math.abs(n);
  if (abs >= 1e6 || abs < 1e-3) return n.toExponential(2);
  return n.toFixed(0);
}
function floatFormat(n) {
  if (n === 0) return '0.00';
  // 4 significant digits
  return Number(n).toPrecision(4);
}

function pickFormatter(dtype) {
  switch ((dtype || '').toLowerCase()) {
    case 'uint8': return integerFormat;
    case 'uint16': return integerFormat;
    case 'uint32': return scientificFormat;
    case 'float32': return floatFormat;
    case 'float64': return floatFormat;
    default: return floatFormat;
  }
}

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
    <div className="layer-item image-row" style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0' }}>
      <button className={'layer-toggle' + (visible ? ' visible' : '')}
        onClick={() => { model.set('image_visible', !visible); model.save_changes(); }}
        aria-label={visible ? 'Hide image' : 'Show image'}
        style={{ background: 'none', border: 'none', cursor: 'pointer' }}
        title={visible ? 'Hide image' : 'Show image'}>
        {visible ? '👁' : '⊘'}
      </button>
      <span style={{ flex: 1 }}>Image</span>
      <select value={displayMode}
        aria-label="Display mode"
        onChange={(e) => { model.set('_display_mode', e.target.value); model.save_changes(); }}>
        <option value="composite">Composite</option>
        <option value="single">Single</option>
      </select>
    </div>
  );
}

function ChannelRow({ model, ch, idx, active, onActivate, imageDtype }) {
  const luts = listLuts();
  // Per-channel unit toggle [spec §7.5]. Default: data values.
  const [unitMode, setUnitMode] = useState('data'); // 'data' | 'percent'
  const formatter = pickFormatter(imageDtype);

  // Min/max display transforms.
  const minData = normalizedToData(ch.min ?? 0, ch);
  const maxData = normalizedToData(ch.max ?? 1, ch);
  const minPercent = (ch.min ?? 0) * 100;
  const maxPercent = (ch.max ?? 1) * 100;

  const minDisplayed = unitMode === 'percent' ? minPercent : minData;
  const maxDisplayed = unitMode === 'percent' ? maxPercent : maxData;
  const minFormatter = unitMode === 'percent' ? (n) => `${n.toFixed(1)}%` : formatter;
  const maxFormatter = unitMode === 'percent' ? (n) => `${n.toFixed(1)}%` : formatter;
  const dmin = ch.data_min ?? 0;
  const dmax = ch.data_max ?? 65535;
  const minBounds = unitMode === 'percent' ? { min: 0, max: 100 } : { min: dmin, max: dmax };
  const maxBounds = unitMode === 'percent' ? { min: 0, max: 100 } : { min: dmin, max: dmax };

  function commitMin(displayed) {
    const normalized = unitMode === 'percent' ? displayed / 100 : dataToNormalized(displayed, ch);
    setChannel(model, idx, { min: Math.max(0, Math.min(1, normalized)) });
  }
  function commitMax(displayed) {
    const normalized = unitMode === 'percent' ? displayed / 100 : dataToNormalized(displayed, ch);
    setChannel(model, idx, { max: Math.max(0, Math.min(1, normalized)) });
  }

  return (
    <>
      <div className={'layer-item channel-layer-item' + (active ? ' active-channel' : '')}
           onClick={onActivate}
           style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0',
                    background: active ? '#eef5ff' : 'transparent', cursor: 'pointer' }}>
        <button className={'layer-toggle' + (ch.visible ? ' visible' : '')}
          onClick={(e) => { e.stopPropagation(); setChannel(model, idx, { visible: !ch.visible }); }}
          aria-label={ch.visible ? 'Hide channel' : 'Show channel'}
          title={ch.visible ? 'Hide channel' : 'Show channel'}
          style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
          {ch.visible ? '👁' : '⊘'}
        </button>
        <span className="channel-name" style={{ flex: 1, fontSize: 12 }}>{ch.name || `Ch ${idx}`}</span>

        <select value={ch.color_kind || 'solid'}
          aria-label="Color mode"
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => setChannel(model, idx, { color_kind: e.target.value })}
          style={{ fontSize: 11 }}>
          <option value="solid">Solid</option>
          <option value="lut">LUT</option>
        </select>

        {ch.color_kind === 'lut' ? (
          <select value={ch.lut || 'viridis'}
            aria-label="LUT"
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => setChannel(model, idx, { lut: e.target.value })}
            style={{ fontSize: 11 }}>
            {luts.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        ) : (
          <input type="color" value={ch.color || '#ffffff'}
            aria-label="Channel color"
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => setChannel(model, idx, { color: e.target.value })}
            style={{ width: 24, height: 20, border: 'none', padding: 0 }} />
        )}

        <button className="auto-contrast-btn"
          aria-label="Auto contrast"
          title="Auto contrast"
          onClick={(e) => {
            e.stopPropagation();
            model.send({ kind: 'auto-contrast', channelIndex: idx });
          }}
          style={{ fontSize: 11, padding: '2px 6px' }}>Auto</button>

        <button className="unit-toggle-btn"
          aria-label={unitMode === 'percent' ? 'Show data values' : 'Show percent'}
          title={unitMode === 'percent' ? 'Show data values' : 'Show percent'}
          onClick={(e) => { e.stopPropagation(); setUnitMode(unitMode === 'percent' ? 'data' : 'percent'); }}
          style={{ fontSize: 11, padding: '2px 6px' }}>
          {unitMode === 'percent' ? '%' : 'val'}
        </button>
      </div>

      {/* Min row */}
      <div className="layer-item sub-item channel-contrast-row"
           style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '2px 0 2px 16px', fontSize: 11 }}>
        <span className="slider-label" style={{ width: 40, color: '#666' }}>Min</span>
        <input type="range" min="0" max="100" value={Math.round((ch.min ?? 0) * 100)}
          aria-label="Channel min"
          onChange={(e) => setChannel(model, idx, { min: parseInt(e.target.value) / 100 })}
          style={{ flex: 1 }} />
        <NumericInput
          value={minDisplayed}
          min={minBounds.min} max={minBounds.max} step="any"
          format={minFormatter}
          onCommit={commitMin}
          style={{ width: 72, fontSize: 11, padding: '1px 4px' }}
          aria-label="Channel min value" />
      </div>

      {/* Max row */}
      <div className="layer-item sub-item channel-contrast-row"
           style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '2px 0 2px 16px', fontSize: 11 }}>
        <span className="slider-label" style={{ width: 40, color: '#666' }}>Max</span>
        <input type="range" min="0" max="100" value={Math.round((ch.max ?? 1) * 100)}
          aria-label="Channel max"
          onChange={(e) => setChannel(model, idx, { max: parseInt(e.target.value) / 100 })}
          style={{ flex: 1 }} />
        <NumericInput
          value={maxDisplayed}
          min={maxBounds.min} max={maxBounds.max} step="any"
          format={maxFormatter}
          onCommit={commitMax}
          style={{ width: 72, fontSize: 11, padding: '1px 4px' }}
          aria-label="Channel max value" />
      </div>

      {/* Gamma row [spec §7.3] — NumericInput + reset-to-1 button */}
      <div className="layer-item sub-item channel-contrast-row"
           style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '2px 0 2px 16px', fontSize: 11 }}>
        <span className="slider-label" style={{ width: 40, color: '#666' }}>Gamma</span>
        <input type="range" min="10" max="500" value={Math.round((ch.gamma ?? 1) * 100)}
          aria-label="Channel gamma"
          onChange={(e) => setChannel(model, idx, { gamma: parseInt(e.target.value) / 100 })}
          style={{ flex: 1 }} />
        <NumericInput
          value={ch.gamma ?? 1}
          min={0.1} max={5} step="any"
          format={(n) => n.toFixed(2)}
          onCommit={(n) => setChannel(model, idx, { gamma: n })}
          style={{ width: 56, fontSize: 11, padding: '1px 4px' }}
          aria-label="Channel gamma value" />
        <button className="reset-gamma-btn"
          aria-label="Reset gamma to 1"
          title="Reset gamma to 1"
          onClick={(e) => { e.stopPropagation(); setChannel(model, idx, { gamma: 1.0 }); }}
          style={{ fontSize: 11, padding: '2px 6px' }}>1</button>
      </div>
    </>
  );
}

export function ImageSection({ model }) {
  const channels = useModelTrait(model, '_channel_settings') || [];
  const activeChannel = useModelTrait(model, 'current_c') || 0;
  const imageDtype = useModelTrait(model, '_image_dtype') || 'uint16';
  return (
    <>
      <ImageRow model={model} />
      {channels.map((ch, idx) => (
        <ChannelRow key={idx} model={model} ch={ch} idx={idx}
          active={idx === activeChannel}
          imageDtype={imageDtype}
          onActivate={() => { model.set('current_c', idx); model.save_changes(); }} />
      ))}
    </>
  );
}
```

- [ ] **Step 2: Build + smoke-run JS tests**

```
cd anybioimage/frontend/viewer && npm run test && npm run build
```

- [ ] **Step 3: Run the full integration suite**

```
uv run pytest tests/integration/ -v -m integration
```

Expected: still green. No integration test covers NumericInput directly yet — the unit tests (Task 12) cover it.

- [ ] **Step 4: Commit**

```bash
git add anybioimage/frontend/viewer/src/chrome/LayersPanel/ImageSection.jsx \
        anybioimage/frontend/viewer/dist/viewer-bundle.js
git commit -m "feat(ux): ImageSection — NumericInput + reset-gamma + data-value toggle [spec §7.2, §7.3, §7.5]

- Min / max / gamma rows gain a NumericInput beside each slider.
- Gamma row gains a '1' button that resets to gamma = 1.0.
- Min/max default to data-value display (dtype-aware formatter);
  per-channel 'val' <-> '%' toggle flips the column.
- Data-value → normalized conversion uses ch.data_min / ch.data_max so
  the stored trait stays normalized [0, 1]."
```

---

## Task 14: Play button gating + `verify_scrub_perf()` helper

**Goal:** Play button hidden when `dim_t <= 1`; disabled-with-tooltip until `scrub_perf_verified === true` [spec §7.4]. Add a Python helper `BioImageViewer.verify_scrub_perf()` that programmatically runs the T-scrub test + flips the trait on pass. The test fixture flips the trait for its own duration.

**Files:**
- Modify: `anybioimage/frontend/viewer/src/chrome/DimControls.jsx`
- Modify: `anybioimage/viewer.py`
- Modify: `tests/integration/test_t_scrub_perf.py` — flip trait inside the test so play button works for the duration

- [ ] **Step 1: Update DimControls play button**

Modify `anybioimage/frontend/viewer/src/chrome/DimControls.jsx`:

```jsx
// anybioimage/frontend/viewer/src/chrome/DimControls.jsx
import React, { useEffect, useState } from 'react';
import { useModelTrait } from '../model/useModelTrait.js';
import { ICONS } from './icons.js';

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

function PlayButton({ model, traitKey, max }) {
  const [playing, setPlaying] = useLivePlay(model, traitKey, max);
  const verified = useModelTrait(model, 'scrub_perf_verified');
  const disabled = !verified;
  const label = playing ? 'Pause' : 'Play';
  const tooltip = disabled
    ? 'Scrub performance not yet verified — run `viewer.verify_scrub_perf()` or `pytest tests/integration/test_t_scrub_perf.py`'
    : label;
  return (
    <button
      className={'play-btn' + (disabled ? ' disabled' : '')}
      disabled={disabled}
      aria-label={label}
      title={tooltip}
      onClick={() => { if (!disabled) setPlaying(!playing); }}>
      {playing ? ICONS.pause : ICONS.play}
    </button>
  );
}

function DimSlider({ model, label, traitKey, max, showPlay = false }) {
  const value = useModelTrait(model, traitKey) ?? 0;
  if (max <= 1) return null;        // [spec §7.4] — hidden when dim <= 1
  return (
    <div className="dim-slider-wrapper">
      <span className="dim-label">{label}</span>
      {showPlay && <PlayButton model={model} traitKey={traitKey} max={max} />}
      <input className="dim-slider" type="range" min="0" max={max - 1} value={value}
        aria-label={`${label} index`}
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
        aria-label={label}
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

- [ ] **Step 2: Add `verify_scrub_perf()` helper to BioImageViewer**

Modify `anybioimage/viewer.py` — add a new method near the other public methods (after `close`):

```python
    def verify_scrub_perf(self) -> bool:
        """Programmatically invoke the T-scrub perf integration test.

        Runs `pytest tests/integration/test_t_scrub_perf.py -m integration -q`
        in a subprocess against THIS process's widget. On pass, flips
        `scrub_perf_verified` to True so the play button activates. Does not
        persist to disk — each fresh kernel starts with the trait False, per
        spec §7.4 (we only enable features we've proven work on the current
        machine).

        Returns True on pass, False on fail or error.
        """
        import subprocess
        import sys

        cmd = [
            sys.executable, "-m", "pytest",
            "tests/integration/test_t_scrub_perf.py",
            "-m", "integration", "-q",
        ]
        try:
            rc = subprocess.call(cmd)
        except Exception:
            return False
        if rc == 0:
            self.scrub_perf_verified = True
            return True
        return False
```

- [ ] **Step 3: Update `test_t_scrub_perf.py` to flip the trait during the test**

Modify `tests/integration/test_t_scrub_perf.py` — after the budget assertion passes, set `scrub_perf_verified = True`:

```python
"""T slider scrub p95 ≤ 30 ms per step [spec §1 perf budget, §7.4]."""
from __future__ import annotations

import os

import pytest


BUDGET_MS = 30.0 * float(os.environ.get("ANYBIOIMAGE_PERF_BUDGET_MULTIPLIER", "1.0"))
WARMUP = 10
MEASURE = 30


@pytest.mark.integration
def test_t_scrub_meets_budget(widget):
    dim_t = widget.get("dim_t") or 1
    if dim_t <= 1:
        pytest.skip("fixture has dim_t <= 1; T-scrub N/A")

    widget.clear_perf()
    cur = widget.get("current_t") or 0
    for i in range(WARMUP):
        widget.set("current_t", (cur + i) % dim_t)
    widget.clear_perf()
    for i in range(MEASURE):
        widget.set("current_t", (cur + i) % dim_t)

    widget._page.wait_for_timeout(300)
    p95 = widget.perf_p95("pixelSource:getTile")
    assert p95 <= BUDGET_MS, f"T scrub pixelSource:getTile p95 = {p95:.2f} ms > {BUDGET_MS:.2f} ms budget"

    # On pass, flip the trait for this widget [spec §7.4].
    widget.set("scrub_perf_verified", True)
```

- [ ] **Step 4: Build + run**

```
cd anybioimage/frontend/viewer && npm run build && cd -
uv run pytest tests/integration/test_t_scrub_perf.py -v -m integration
```

Expected: green. In a browser session after the test, the widget's play button would be enabled (but only for the life of that widget — the trait doesn't persist).

- [ ] **Step 5: Commit**

```bash
git add anybioimage/frontend/viewer/src/chrome/DimControls.jsx \
        anybioimage/viewer.py \
        anybioimage/frontend/viewer/dist/viewer-bundle.js \
        tests/integration/test_t_scrub_perf.py
git commit -m "feat(ux): gate play button on scrub_perf_verified [spec §7.4]

- DimSlider hides entirely when dim <= 1 (spec requirement, not just T).
- PlayButton disabled with tooltip until scrub_perf_verified is True.
- Tooltip directs user to \`viewer.verify_scrub_perf()\` or pytest command.
- BioImageViewer.verify_scrub_perf() subprocess-runs the integration test
  and flips the trait on success.
- test_t_scrub_perf.py flips the trait on its own widget after the assertion
  — feature is only visible when we can prove it works on this machine."
```

---

## Task 15: Console hygiene integration test

**Goal:** Fail the suite if any unfiltered console error/warning fires during a 30-second demo walk [spec §4 console-hygiene test]. Allow-list covers known driver noise.

**Files:**
- Create: `tests/integration/test_console_hygiene.py`

- [ ] **Step 1: Write the test**

Create `tests/integration/test_console_hygiene.py`:

```python
"""Console hygiene [spec §4].

Any `console.error` or `console.warn` that fires during a 30-second window
after loading the demo is a suite failure, UNLESS its text matches one of
the allow-list regexes below. The allow-list captures known-benign driver
noise from swiftshader / marimo dev-time diagnostics.
"""
from __future__ import annotations

import re

import pytest


ALLOW = [
    r"GL Driver Message",
    r"gradient-yHQUC",
    r"noise-60BoTA",
    r"copilot-language-server",
    # swiftshader occasionally emits a missing-extension notice.
    r"WebGL.* is not supported",
]


@pytest.mark.integration
def test_no_unfiltered_console_errors(page, marimo_server):
    errors: list[tuple[str, str]] = []

    def collect(msg):
        if msg.type in ("error", "warning"):
            errors.append((msg.type, msg.text))

    page.on("console", collect)
    page.goto(marimo_server)
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(30000)

    bad = [(t, text) for t, text in errors
           if not any(re.search(p, text) for p in ALLOW)]

    assert not bad, (
        f"{len(bad)} unfiltered console errors/warnings:\n"
        + "\n".join(f"  [{t}] {text}" for t, text in bad)
    )
```

- [ ] **Step 2: Run**

```
uv run pytest tests/integration/test_console_hygiene.py -v -m integration -s
```

If the test fails, either the warning is legitimate (fix it — don't add to the allow-list) or it's benign driver noise not yet in the allow-list (add the regex). Do not silence legitimate warnings.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_console_hygiene.py
git commit -m "test(integration): console-hygiene gate [spec §4]

Fails the suite if any console.error or console.warn fires during a 30-s
demo window, unless its text matches a small allow-list of known-benign
swiftshader / marimo diagnostics.

No silencing of legitimate warnings — per spec §11.1, 'no xfail to hide
a failure, no TODO comments hiding known issues.'"
```

---

## Task 16: Final validation + CHANGELOG

**Goal:** Mirror the Phase 2 end-of-phase ritual. Run the full test matrix, integration tier, bundle check, and a manual browser walk-through of `examples/full_demo.py`. Update `CHANGELOG.md` with Phase 2.5 additions.

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Full Python test sweep (non-integration)**

```
uv run pytest tests/ -v --ignore=tests/integration --ignore=tests/playwright
```

Expected: ≥163 passed, 0 failed. Record the exact number.

- [ ] **Step 2: Full JS test sweep**

```
cd anybioimage/frontend/viewer && npm run test
```

Expected: green.

- [ ] **Step 3: Full integration sweep**

```
uv run pytest tests/integration/ -v -m integration
```

Expected: green. Every perf budget met. Every correctness test green.

- [ ] **Step 4: Bundle build + size**

```
cd anybioimage/frontend/viewer && npm run build && npm run size
```

Expected: ≤ 4 MB.

- [ ] **Step 5: `marimo check examples/full_demo.py`**

```
uv run marimo check examples/full_demo.py
```

Expected: clean.

- [ ] **Step 6: Manual browser walk-through**

```
uv run marimo edit examples/full_demo.py
```

Open via playwright-cli:

```
mkdir -p /tmp/anybioimage-screenshots
playwright-cli open "http://localhost:2718?access_token=<token>" --browser=chromium
```

Drive through all 8 Phase-2 demo sections. Confirm:
- Every tool button renders an icon with a hover tooltip showing shortcut.
- Numeric inputs appear next to min/max/gamma sliders.
- Gamma row has a `1` button that resets gamma.
- Min/max column toggles between data values (dtype-formatted) and `%`.
- Play button is hidden for dim_t=1 sections; disabled with tooltip for dim_t>1 until `verify_scrub_perf()` runs.
- Select tool picks a drawn rect.
- No red errors in the console.

Capture screenshots:
- `/tmp/anybioimage-screenshots/phase2-5-toolbar.png`
- `/tmp/anybioimage-screenshots/phase2-5-numeric-inputs.png`
- `/tmp/anybioimage-screenshots/phase2-5-play-gated.png`
- `/tmp/anybioimage-screenshots/phase2-5-select-works.png`

Clean up:

```
rm -rf /tmp/anybioimage-screenshots
```

- [ ] **Step 7: Update `CHANGELOG.md`**

Append a Phase 2.5 subsection under `[Unreleased]`:

```markdown
### Added — Phase 2.5 (Hardening + Integration Test Tier)

- **Integration test tier** under `tests/integration/` — Playwright + marimo
  drives real gestures, asserts via model traitlets, enforces perf budgets.
  New pytest marker `integration`. New CI job runs Playwright + chromium.
- **`_render_ready` traitlet** — JS flips it True on first successful raster
  render; integration fixtures block on it. Race-safe (checked synchronously
  before subscribing).
- **Perf instrumentation** (`src/util/perf.js`) — `mark`, `measure`, `trace`,
  `getPerfReport`, `clearPerf`. Gated by `window.__ANYBIOIMAGE_PERF`. Four
  hot paths wired: `layers:build` (+ per-layer sub-labels),
  `pixelSource:getTile`, `buildImageLayerProps`, `interaction:<phase>`.
- **Perf budgets enforced** (spec §1) — channel toggle p95 ≤ 16 ms,
  T/Z scrub p95 ≤ 30 ms; loosened by 1.5× on CI via
  `ANYBIOIMAGE_PERF_BUDGET_MULTIPLIER`.
- **SVG icon set** (`src/chrome/icons.js`) — Heroicons-style stroke-based
  icons for every toolbar tool. Every button carries `aria-label` + `title`
  with shortcut letter.
- **`NumericInput` component** — reusable numeric entry paired with sliders.
  Validates on blur/Enter, reverts on invalid, clamps to [min, max],
  Escape cancels. Wired to channel min/max/gamma rows.
- **Reset gamma button** — `1` button next to gamma NumericInput.
- **Data-value unit display** — min/max default to dtype-formatted data
  values (integer for uint8/uint16, scientific for uint32, 4-sig-fig for
  float). Per-channel `val`/`%` toggle.
- **`scrub_perf_verified` traitlet** + `BioImageViewer.verify_scrub_perf()`
  helper — play button disabled-with-tooltip until T-scrub perf is proven
  on the current machine.

### Fixed — Phase 2.5

- **Select tool picks annotations** (spec §5.1) — `InteractionController`
  gains `setContext(extra)` merging keys into `_ctx`. `DeckCanvas` injects
  `pickObject` on every render. Select click now sets
  `selected_annotation_id` to the hit object's id.
- **Keyboard shortcuts scoped per widget** (spec §5.2) — `installKeyboard`
  signature changed to `installKeyboard(model, containerEl)`. Listener
  attaches to the viewer's root `.bioimage-viewer` div (already
  `tabIndex={0}`). Two widgets on a page no longer stack listeners.
- **Remote OME-Zarr renders visible pixels** (spec §5.3) — see commit for
  the specific root cause + fix.
- **Monolithic `layers` useMemo split into per-type memos** (spec §6.1) —
  channel toggles now rebuild the image layer only; mask/annotation/preview/
  scale-bar memos stay cached.
- **T/Z scrub prefetch** (spec §6.2) — `AnywidgetPixelSource.prefetch`
  called 100 ms after the last slider change, pre-warming Python-side cache
  for t±1 and z±1.

### Changed — Phase 2.5

- `Toolbar.jsx` — button `title` text now uses `"Name (Shortcut)"` format
  (e.g., `"Rectangle (R)"`) instead of `"Rectangle (R)"` display + single
  letter. No behavior change for `WidgetHandle.click_tool()`.

### Infrastructure — Phase 2.5

- `docs/superpowers/notes/widget-isolation-audit.md` — audit of
  `window.*`, module-level state, shared listeners. No accidental-global
  regressions at Phase 2.5 cut.
- `docs/superpowers/notes/phase2-5-perf-baseline.md` — baseline numbers
  before the layer-memo split and prefetch.

### Acceptance gate met (spec §8)

- ✅ `uv run pytest tests/ -v --ignore=tests/integration --ignore=tests/playwright` green.
- ✅ `cd anybioimage/frontend/viewer && npm run test` green.
- ✅ `uv run pytest tests/integration/ -v -m integration` green — no xfail.
- ✅ `npm run build` ≤ 4 MB.
- ✅ `marimo check examples/full_demo.py` clean.
- ✅ Browser walk-through: every section renders without console errors.
```

- [ ] **Step 8: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): Phase 2.5 — Hardening + Integration Test Tier

Acceptance gate met (spec §8):
- Python tests green (≥163 passed, 0 failed)
- JS tests green
- Integration tier green — no xfail, no skip on correctness/perf tests
- Bundle ≤ 4 MB
- marimo check clean
- Browser walk-through: zero console errors

Phase 3 (editing, measurement, undo, export) is now unblocked."
```

---

## Self-review checklist (run before declaring Phase 2.5 done)

- [ ] **Spec §1 (scope in/out)** — correctness, perf, isolation, UX polish covered. Phase 3 items correctly deferred.
- [ ] **Spec §2 (architecture)** — every listed new file and modified file actually touched in the plan. Check against the file-structure section.
- [ ] **Spec §3 (perf instrumentation)** — `util/perf.js` API matches (`mark`, `measure`, `trace`, `getPerfReport`, `clearPerf`); four hot paths wired (Task 1 + Task 7); `window.__ANYBIOIMAGE_PERF` gating confirmed; ring buffer size 1000 confirmed.
- [ ] **Spec §4 (integration test tier)** — `tests/integration/` directory layout matches; fixture chain (marimo_server / browser / page / widget) exists; `WidgetHandle` helpers named per spec; `sample_canvas` / `assert_non_black` helpers; console-hygiene test present.
- [ ] **Spec §5.1 (Select)** — Task 3, `setContext({pickObject})`, integration test written first.
- [ ] **Spec §5.2 (Keyboard)** — Task 4, `installKeyboard(model, containerEl)` signature change, `tabIndex={0}` preserved, two-widget test.
- [ ] **Spec §5.3 (Remote zarr)** — Task 6, diagnostic loop with no pre-committed fix, test written first, page.on('console') log inspection.
- [ ] **Spec §5.4 (Isolation audit)** — Task 5, note under `docs/superpowers/notes/`, walks greps for `window.`, module-level `let/var`, timers, `document.addEventListener`.
- [ ] **Spec §6.1 (Channel toggle)** — Task 9, per-layer sub-memos, before/after p95 in commit message.
- [ ] **Spec §6.2 (T/Z prefetch)** — Task 10, `prefetch({t, z, halfWindow})` method, AbortController cancellation, 100 ms debounce, before/after p95 in commit message.
- [ ] **Spec §7.1 (Toolbar icons)** — Task 11, `chrome/icons.js`, aria-label + title on every button.
- [ ] **Spec §7.2 (NumericInput)** — Task 12 + Task 13, on blur / Enter commit, Escape reverts, clamps to [min, max].
- [ ] **Spec §7.3 (Reset gamma)** — Task 13, `1` button.
- [ ] **Spec §7.4 (Play gating)** — Task 14, `dim_t <= 1` hides, `scrub_perf_verified` disables-with-tooltip, `verify_scrub_perf()` helper.
- [ ] **Spec §7.5 (Data-value display)** — Task 13, dtype-aware formatters, per-channel `%` toggle.
- [ ] **Spec §8 (Acceptance gate)** — Task 16 runs the full list.
- [ ] **Spec §9 (Phasing)** — task order matches: infrastructure → correctness → remote diagnosis → perf measurement → perf fixes → UX polish → final.
- [ ] **Spec §10 (Risks)** — `_render_ready` race handled in `WidgetHandle.wait_for_ready` (poll before subscribe). CI multiplier env var in place.
- [ ] **Spec §11 (Decisions locked in)** — no shortcut patches, test-first, perf numbers in commits.
- [ ] **Placeholder scan** — no `...`, no "similar to X", no "etc.", no TODO, no unfilled `<X>` outside the commit-message placeholders that are explicitly filled at commit time.
- [ ] **Internal consistency — `_render_ready`** — declared in viewer.py (Task 2), flipped in DeckCanvas.jsx (Task 2), polled in WidgetHandle.wait_for_ready (Task 2). No other consumer.
- [ ] **Internal consistency — `scrub_perf_verified`** — declared in viewer.py (Task 2), read in DimControls.PlayButton (Task 14), flipped by verify_scrub_perf helper (Task 14) + by test_t_scrub_perf.py (Task 14).
- [ ] **Type consistency** — perf label strings (`layers:image`, `pixelSource:getTile`, `buildImageLayerProps`, `interaction:<phase>`) are spelled the same in JS and in integration-test assertions.
- [ ] **Commit message content** — perf commits have before/after p95 numbers in the body. Correctness commits reference the failing-then-passing integration test by filename.
- [ ] **Scope check** — 16 tasks is a cohesive set. No task is overspecified or bundles unrelated concerns. Task 6 (remote zarr) deliberately does not pre-commit to a fix, per spec §5.3.

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-19-phase2-5-hardening.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks. Best fit for 16 bite-sized tasks; keeps main-session context clean. Task 6 (remote-zarr diagnosis) in particular benefits from a clean subagent context because the diagnostic loop involves reading a lot of console/network output.

**2. Inline Execution** — execute tasks in this session using `superpowers:executing-plans`; batch checkpoints for review (every 3–4 tasks).

**Which approach?**
