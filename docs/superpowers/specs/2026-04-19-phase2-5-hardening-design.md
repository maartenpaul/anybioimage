# Phase 2.5 — Hardening + Integration Test Tier — design spec

> Output of the `superpowers:brainstorming` skill. Feed this spec into `superpowers:writing-plans` when ready.

**Status:** approved 2026-04-19. Targets branch `feature/viv-backend`.

**Goal (one sentence):** Harden the unified viewer to a ship-quality standard by root-cause-fixing the correctness, performance, isolation, and UX-polish issues surfaced during the Phase-2 browser run, and install a durable integration-test tier so future regressions fail a test rather than a user report.

**Explicit non-goal:** no new features. Phase 3 (editing, measurement, undo, export) is blocked on Phase 2.5 landing.

**Guiding principle:** "Doing business" — no shortcut patches, no silenced warnings, no tests marked xfail to hide a failure, no TODO comments hiding known issues. Every perf fix ships with measured before/after numbers. Every correctness fix ships with a failing-then-passing integration test.

---

## 1. Scope

### In

- **Correctness**
  - Select tool can pick annotations (currently broken — `InteractionController._ctx` does not expose `pickObject`).
  - Keyboard shortcuts scoped per widget instead of `window` — two widgets on a page no longer fight.
  - Remote OME-Zarr renders visible pixels (currently black; unknown root cause).
  - Widget-isolation audit — no shared mutable state between widget instances unless intentional.

- **Performance** — against the spec §10 budget, measured, asserted:
  - Channel toggle → next paint: p95 ≤ 16 ms
  - T slider scrub (in-RAM): p95 ≤ 30 ms per step
  - Z slider scrub (in-RAM): p95 ≤ 30 ms per step
  - Cold tile fetch (chunk-bridge, local numpy): p95 ≤ 30 ms
  - Pan / zoom steady state: 60 fps

- **Instrumentation** — a durable perf-measurement layer under `src/util/perf.js`, wired into the four hot paths identified in section 3.

- **Integration test tier** — a third testing tier under `tests/integration/` that drives real gestures via Playwright, asserts state by reading model traitlets back, and enforces the perf budget above.

- **UX polish**
  - Tool buttons: inline-SVG icons + accessible `aria-label` + `title` tooltips with shortcut letter. No single-letter button text.
  - Numeric entry for every slider (min, max, gamma).
  - Reset-gamma-to-1 button next to the gamma input.
  - Play button: hidden when `dim_t <= 1`; disabled with tooltip until T-scrub perf budget has been measured green.
  - Min/max default to data values (dtype-formatted), with an opt-in normalized (%) toggle per channel.

### Out

- Toolbar / Layers-panel visual redesign.
- Anything in Phase 3: `EditableGeoJsonLayer` vertex edit, line / area / line-profile measurement tools, undo/redo, CSV/JSON export buttons.
- Keyboard-shortcut discoverability popover (hover tooltips cover it adequately).
- Canvas2D fallback (removed in Phase 1 — stays removed).

---

## 2. Architecture

### Module layout (additions + modifications)

**New:**

- `anybioimage/frontend/viewer/src/util/perf.js` — instrumentation. `mark`, `measure`, `trace`, `getPerfReport`, `clearPerf`.
- `anybioimage/frontend/viewer/src/util/perf.test.js`
- `anybioimage/frontend/viewer/src/chrome/icons.js` — named SVG icon exports for Pan, Select, Rect, Polygon, Point, Line, AreaMeasure, Reset, Layers.
- `anybioimage/frontend/viewer/src/chrome/NumericInput.jsx` — reusable numeric-entry widget, two-way bound with slider; validation on blur/enter; revert on invalid.
- `anybioimage/frontend/viewer/src/chrome/NumericInput.test.jsx`
- `tests/integration/__init__.py`
- `tests/integration/conftest.py` — marimo server + playwright browser + widget-ready fixture.
- `tests/integration/fixtures/demo_small.py` — a minimal marimo notebook loaded by integration tests.
- `tests/integration/helpers/widget.py` — `wait_for_ready`, `get_model`, `set_trait`, `perf_snapshot`, `perf_p95`.
- `tests/integration/helpers/pixels.py` — `sample_canvas`, `assert_non_black`, `read_pixels_at`.
- `tests/integration/test_select_picks.py`
- `tests/integration/test_draw_rect.py`
- `tests/integration/test_draw_polygon.py`
- `tests/integration/test_draw_point.py`
- `tests/integration/test_keyboard_isolation.py`
- `tests/integration/test_channel_toggle_perf.py`
- `tests/integration/test_t_scrub_perf.py`
- `tests/integration/test_z_scrub_perf.py`
- `tests/integration/test_remote_zarr_renders.py`
- `tests/integration/test_console_hygiene.py`

**Modified:**

- `anybioimage/frontend/viewer/src/interaction/InteractionController.js` — `_ctx` gains `pickObject` via a `setContext({pickObject})` injection from `DeckCanvas`.
- `anybioimage/frontend/viewer/src/interaction/keyboard.js` — signature changes to `installKeyboard(model, containerEl)`; listener attaches to `containerEl`, not `window`. Container must be focusable (`tabIndex={0}`).
- `anybioimage/frontend/viewer/src/App.jsx` — passes the widget root `div` into `installKeyboard`.
- `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx` — calls `controller.setContext({pickObject})` once on mount; splits the monolithic `layers` useMemo into per-layer memos with tight dep lists (image, masks, annotations, preview, scale bar).
- `anybioimage/frontend/viewer/src/render/pixel-sources/anywidget-source.js` — adds `prefetch({t, z, halfWindow})` method; called from `DeckCanvas` on scrub-settle with a 100 ms debounce.
- `anybioimage/frontend/viewer/src/chrome/Toolbar.jsx` — icons from `icons.js`; every button carries `aria-label` + `title`.
- `anybioimage/frontend/viewer/src/chrome/DimControls.jsx` — play button: hidden when `dim_t <= 1`; disabled with tooltip until `scrub_perf_verified` traitlet flips true.
- `anybioimage/frontend/viewer/src/chrome/LayersPanel/ImageSection.jsx` — channel rows gain `NumericInput` for min/max/gamma, "Reset" button next to gamma, "%" toggle for min/max unit display.
- `anybioimage/viewer.py` — new traitlets: `_render_ready` (Bool, sync), `scrub_perf_verified` (Bool, sync, defaults False).
- `pyproject.toml` — add `[tool.pytest.ini_options].markers` entry for `integration`.

**Deletions:** none. Phase 2.5 is purely additive + refactor.

### Data-flow changes

- `_render_ready` is set to `true` by JS once `MultiscaleImageLayer.updateState` completes the first time with a non-null raster. Integration-test fixtures block on this trait.
- `scrub_perf_verified` is set to `true` only after the T/Z scrub integration tests pass in CI; the harness sends a `set_trait` message. Until then, play button is visible-but-disabled with a tooltip; user-facing evidence that the feature isn't green yet.

---

## 3. Perf instrumentation contract

### `util/perf.js` API

```js
export function mark(name);
export function measure(label, startMark, endMark);     // creates a PerformanceMeasure + records
export function trace(label, fn);                        // wraps fn with mark/measure
export function getPerfReport();                         // → {[label]: {count, p50, p95, p99, mean}}
export function clearPerf();                             // clears the ring buffer
```

### When is it on?

Instrumentation is always compiled into the bundle but is a no-op unless `window.__ANYBIOIMAGE_PERF === true`. Integration tests set the flag during setup. End users can set it in devtools to reproduce perf measurements locally.

### The four hot paths

1. **Layer construction** — wrap the `layers` useMemo's body in `trace("layers:build", () => ...)`. Each per-layer sub-memo also emits its own trace label (`layers:image`, `layers:annotations`, `layers:masks`, `layers:preview`, `layers:scaleBar`).
2. **PixelSource tile fetch** — wrap `AnywidgetPixelSource.getTile`'s outer promise with marks on request-send and response-receive. Label `pixelSource:getTile`.
3. **`buildImageLayerProps`** — function call traced with label `buildImageLayerProps`.
4. **Pointer dispatch** — `InteractionController.handlePointerEvent` wraps each phase with label `interaction:<phase>`.

Ring buffer holds the last 1000 entries per label. `getPerfReport()` computes percentiles on demand. Tests snapshot then assert.

---

## 4. Integration test tier

### Directory layout

```
tests/integration/
├── conftest.py
├── fixtures/
│   └── demo_small.py
├── helpers/
│   ├── widget.py
│   └── pixels.py
└── test_*.py
```

### Fixture chain (conftest.py)

- `marimo_server` (session scope): spawns `marimo edit tests/integration/fixtures/demo_small.py --headless --host 127.0.0.1 --port <picked>` on a free port. Yields URL.
- `browser` (session scope): Playwright chromium, headless, `--use-gl=swiftshader`.
- `page` (function scope): new context per test, console-error collector attached.
- `widget(page, marimo_server)` (function scope): navigates to URL, waits for `_render_ready`, returns a `WidgetHandle` wrapping page + model-accessor helpers.

### `WidgetHandle` helpers

- `get(trait)` / `set(trait, value)` — round-trip to marimo model.
- `send(content)` — `model.send` from Python-driver side (for testing widget message handlers).
- `click_tool(mode)` — click toolbar button by title.
- `drag(x0, y0, x1, y1)` — deck.gl canvas drag gesture with proper pointer-event sequence.
- `scroll_to_widget(index)` — marimo-aware scroll helper.
- `perf_snapshot()` — returns `getPerfReport()` dict.
- `perf_p95(label)` — convenience.

### `pixels` helpers

- `sample_canvas(page, canvas_selector, points)` — returns list of `(r,g,b,a)` tuples at image coords. Reads from deck.gl via `deck.readPixels({x,y,width:1,height:1})` to avoid CORS-tainted canvas.
- `assert_non_black(samples, threshold=10)` — fails loudly if all samples are near-black.

### Perf-test pattern

```python
# tests/integration/test_channel_toggle_perf.py
BUDGET_MS = 16
WARMUP = 10
MEASURE = 30

def test_channel_toggle_meets_budget(widget):
    widget.clear_perf()
    for _ in range(WARMUP):
        widget.toggle_channel(0); widget.toggle_channel(0)
    widget.clear_perf()
    for _ in range(MEASURE):
        widget.toggle_channel(0); widget.toggle_channel(0)
    p95 = widget.perf_p95("layers:image")
    assert p95 <= BUDGET_MS, f"channel toggle p95 = {p95:.2f} ms > {BUDGET_MS} ms budget"
```

### Console hygiene test

```python
ALLOW = [
  r"GL Driver Message",
  r"gradient-yHQUC",
  r"noise-60BoTA",
  r"copilot-language-server",
]

def test_no_unfiltered_console_errors(page, marimo_server):
    errors = []
    page.on("console", lambda m: errors.append((m.type, m.text)) if m.type in ("error", "warning") else None)
    page.goto(marimo_server)
    page.wait_for_timeout(30000)
    bad = [(t, text) for t, text in errors if not any(re.search(p, text) for p in ALLOW)]
    assert not bad, f"unfiltered console errors/warnings: {bad}"
```

### CI integration

- New pytest mark `integration` declared in `pyproject.toml`.
- Invoked separately: `uv run pytest tests/integration/ -v -m integration`.
- Added to `.github/workflows/ci.yml` as a dedicated job with a Playwright browser install step. Timeout 20 min, 1 parallel worker (perf tests need a stable run).

---

## 5. Correctness fixes

### 5.1 Select tool can pick

**Root cause:** `InteractionController._ctx = { model, controller: this }` — no `pickObject`. The Select tool's `ctx.pickObject(event)` call in `select.js:21` returns `undefined`, the code falls through as if nothing were hit, and always clears selection.

**Fix:** `InteractionController` grows a `setContext(extra)` method that merges extra keys into `_ctx`. `DeckCanvas.jsx` calls `controller.setContext({ pickObject })` in a useEffect after mount. The `pickObject` closure reads the current `deckRef.current.deck` at call time (not at setContext time), so it always picks against the live deck instance.

**Test:** `test_select_picks.py` — draw a rect, click the Select tool, click inside the rect's pixel coords, assert `selected_annotation_id` equals the rect's id. Also: click on empty space → assert id cleared.

### 5.2 Keyboard scoped per widget

**Root cause:** `keyboard.js:52` attaches to `window`. Every widget instance on a page stacks another listener.

**Fix:** change signature to `installKeyboard(model, containerEl)`. The listener attaches to `containerEl`. `App.jsx` passes the `.bioimage-viewer` root `div` which gets `tabIndex={0}` + `outline: none` on focus. First user click inside a widget focuses it. Only the focused widget receives arrow / `[` / `]` / tool-mode keys.

**Test:** `test_keyboard_isolation.py` — fixture notebook renders **two** viewers. Click into widget 1, press `ArrowRight`, assert widget 1's `current_t` incremented and widget 2's did not. Click into widget 2, repeat.

### 5.3 Remote zarr black

**Method:** not a guess-fix. An integration test (`test_remote_zarr_renders.py`) loads the IDR URL and asserts non-black pixels within 10 s of `_render_ready`. The test will fail initially. The fix lands only after diagnosis (console logs, network panel inspection during the failing test).

Three likely candidates (any of which would require a different fix):
- CORS blocked on `.zattrs` or subchunks
- `channel_settings` default contrast too narrow relative to data range
- Multiscale level-0 larger than what Viv's zoom maths picks, leaving level-N unrendered

No preemptive fix ships; the diagnostic pass is a task in the plan.

### 5.4 Widget isolation audit

One dedicated task. Grep for `window.`, module-level mutable state, and shared listeners. For each finding, decide: intentional global (keep, documented), per-widget (scope to instance), or accidental global (fix).

Known candidates to check:
- `_nextRequestId` in `anywidget-source.js` — shared counter, fine (IDs scoped by listener which is per-instance).
- `ADDITIVE_COLORMAP_EXT` module const — fine (stateless).
- `keyboard.js` window listener — fixed in 5.2.
- `InteractionController` — per-App, fine.
- Any timer / interval not cleaned up on unmount — fix if found.

---

## 6. Performance fixes

**Rule for every entry:** measure first, fix with evidence, commit message includes before/after p95.

### 6.1 Channel toggle

**Hypothesis (unverified):** the monolithic `layers` useMemo rebuilds all layers on every `_channel_settings` change, even though only the image layer actually depends on channel settings.

**Measurement:** `layers:image` + `layers:annotations` + `layers:masks` + `layers:scaleBar` per-label timing.

**Candidate fix:** split the monolithic useMemo into one per layer. Each memo's dep list is the minimal set of traits that affect that layer. `layers` final array is `[image, ...masks, ...annotations, preview, scaleBar]`, cheap to reassemble.

If measurement shows that even a per-layer memo still produces a 32 ms image-layer rebuild, dig deeper: is Viv's `MultiscaleImageLayer.updateState` comparing `extensions` by reference (and ours is now stable per the earlier simplify pass)? Are `colors` / `contrastLimits` arrays getting new identities unnecessarily? Don't assume — read the specific Viv update path and compare to the repro.

### 6.2 T/Z scrub

**Hypothesis (unverified):** chunk-bridge round-trip cost × N tiles per frame dominates. No pre-fetch so every scrub pays cold-fetch latency.

**Measurement:** `pixelSource:getTile` p95 over 30 scrubs.

**Candidate fix:** pre-fetch window on `T` / `Z` settle. When the user has not moved the slider for 100 ms, fire requests for tiles at T±1 (or Z±1) for the currently-visible viewport. Pre-fetched tiles land in the Python-side LRU (already implemented); JS-side Viv cache also catches them on actual navigation.

Cancellation: if the user moves the slider again before the pre-fetch completes, abort the outstanding requests. `AnywidgetPixelSource` already supports `AbortSignal`; the prefetch manager wires one up.

Do NOT predict beyond ±1 — only expand the window once ±1 is proven to hit budget.

### 6.3 Layer list stability

Consequence of 6.1: per-layer memos. No separate task.

---

## 7. UX polish

### 7.1 Toolbar icons

One `chrome/icons.js` module exports one named SVG per tool. `Toolbar.jsx` renders each button as:

```jsx
<button className={...} aria-label="Pan" title="Pan (P)">{ICONS.pan}</button>
```

No visible text; the icon carries meaning. Accessibility via `aria-label`. Users who want the keyboard shortcut see it on hover.

Icons pulled from a standard set (e.g. Heroicons-style stroke-based) inlined as raw SVG strings. Storing locally, not a network fetch.

### 7.2 Numeric entry

`NumericInput.jsx` — pairs with a slider. Props: `value`, `min`, `max`, `step`, `format`, `onCommit`. On blur or Enter, parses input; if valid, calls `onCommit(n)`; if invalid, reverts visual state.

Used for:
- Channel min
- Channel max
- Channel gamma (plus a "1" reset button beside it)

Each channel row's layout: `[👁 toggle] [name] [color/LUT picker] [Auto] [min slider + numeric + %toggle] [max slider + numeric + %toggle] [gamma slider + numeric + reset-to-1]`.

### 7.3 Reset-gamma-to-1

A small `1` button next to the gamma `NumericInput`. Click → `setChannel(idx, {gamma: 1.0})`. That's the whole thing.

### 7.4 Play button gating

- Hidden (not disabled) when `dim_t <= 1`. No reason to see it at all.
- Disabled with tooltip "scrub performance not yet verified — run `pytest tests/integration/test_t_scrub_perf.py`" when `scrub_perf_verified === false`.
- The `scrub_perf_verified` traitlet defaults to `false`. CI sets it `true` by running the perf test first (part of the integration-test run). Shipped wheels carry whatever value the last local edit had — users who install the wheel get `false` by default until they run the perf test themselves (which is fast).

This is the mechanical instantiation of "don't show a feature we can't prove works."

### 7.5 Min/max unit display

Napari-style: data values by default. Formatting:
- `uint8` → integers 0..255
- `uint16` → integers 0..65535
- `uint32` → integers 0..4e9 (scientific)
- `float32` → up to 4 significant digits

Per-channel "%" toggle flips the column to `0..100` normalized. The stored trait value (`ch.min`, `ch.max`) is always normalized `[0, 1]`; the display transform is one-way.

---

## 8. Acceptance gate

Phase 2.5 is done when ALL of these are true, simultaneously, on one CI run:

- `uv run pytest tests/ --ignore=tests/playwright -v` → green (≥163 passed, 0 failed, xfail count documented in CHANGELOG)
- `cd anybioimage/frontend/viewer && npm run test` → green
- `uv run pytest tests/integration/ -v -m integration` → green (all new integration tests pass, including perf budgets)
- `npm run build` → ≤4 MB bundle
- `marimo check examples/full_demo.py` → clean
- A browser run through `examples/full_demo.py` in chromium: all 8 demo sections render without console errors; user visually confirms "feels right" (subjective; required).

No xfailed integration test ever. No `@pytest.mark.skip` on an integration test. If a test is failing because the feature doesn't work yet, fix the feature — not the test.

---

## 9. Phasing within Phase 2.5

Work order:

1. **Infrastructure first** — perf instrumentation (`util/perf.js`) + integration-test tier scaffold (conftest, helpers, one trivial passing test to prove the wiring).
2. **Correctness fixes** (5.1 Select, 5.2 Keyboard, 5.4 Audit) — each lands with an integration test that fails before and passes after.
3. **Remote zarr diagnosis** (5.3) — integration test written first (fails), diagnostic run, root-cause fix, test passes.
4. **Performance measurement pass** — run the perf tests (6.1, 6.2) to capture baseline numbers; commit as "baseline".
5. **Performance fixes** — 6.1 channel toggle, 6.2 T/Z prefetch — each with before/after numbers in commit messages.
6. **UX polish** (7.1 icons, 7.2 numeric input, 7.3 reset-gamma, 7.4 play gating, 7.5 data-value display) — unit tests for `NumericInput`, visual confirmation via `examples/full_demo.py`.
7. **Final validation** — full suite, bundle, browser run, CHANGELOG update.

Each step = one atomic commit (or small commit cluster with a shared theme). No "scratchpad" commits.

---

## 10. Risks

- **Perf test flakiness.** Hardware-sensitive budgets break on slow CI. Mitigation: loose bounds in CI (1.5× local), tight bounds local; allow CI to override via env var. Not "warn-only" — still a hard fail, just with a less aggressive threshold.
- **Remote-zarr fix blocked on external infrastructure.** If IDR URL goes 404 mid-work, swap to another known-good public zarr. Check upfront.
- **`_render_ready` race.** The traitlet flips on first raster render, but a fast test might subscribe after it already flipped. Mitigation: test fixture reads the trait synchronously first, subscribes only if false.
- **Two-widget keyboard test fragility.** Focus management across shadow DOM boundaries can be browser-specific. Mitigation: use marimo's own widget container (not the shadow root) as the focus target if needed.

---

## 11. Decisions locked in

1. Root-cause, measure-first, test-first. No shortcut patches.
2. Scope B (correctness + perf + isolation + UX polish). Redesign deferred.
3. Perf instrumentation stays in the codebase, gated by a window flag.
4. Integration tests are a new tier under `tests/integration/`, not mixed into `tests/playwright/` (that one stays as smoke-screenshot tests).
5. Every fix ships with a failing-then-passing integration test and measured numbers where perf-relevant.
6. Phase 3 is blocked on Phase 2.5 acceptance gate.
