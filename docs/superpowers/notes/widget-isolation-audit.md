# Widget isolation audit — Phase 2.5 Task 5

**Date:** 2026-04-19
**Scope:** `anybioimage/frontend/viewer/src/` — find shared mutable state,
module-level listeners, and window/document globals. For each finding, decide:

- **Intentional global** — keep, documented here.
- **Per-widget (accidental global)** — fix (scope to instance).

---

## Grep summary

Searches run (excluding `*.test.*` and `node_modules`):

| Pattern | Files with hits |
|---|---|
| `window\.` | `entry.js`, `util/perf.js` |
| `^let \|^var ` at module level | none (regex matched nothing — confirmed by manual inspection) |
| `let ` anywhere (manual) | `polygon.js`, `rect.js`, `point.js`, `anywidget-source.js`, `perf.js` |
| `setInterval\|setTimeout` | none (regex matched nothing — `setTimeout` in `anywidget-source.js` is inside a constructor, confirmed by inspection) |
| `document\.addEventListener` | none |

---

## Findings

### 1. `_nextRequestId` in `render/pixel-sources/anywidget-source.js` (line 21)

```js
let _nextRequestId = 1;
```

**Classification: Intentional global.** Multiple `AnywidgetPixelSource` instances
share this counter, but each instance owns its own `_pending` Map keyed by
`requestId`, and the `msg:custom` listener checks `_pending.has(requestId)`.
Cross-widget request ID collisions cannot cause cross-delivery because the
listener is a closure over the instance's own `_pending` map. Confirmed benign.
No change required.

### 2. `ADDITIVE_COLORMAP_EXT` in `render/layers/buildImageLayer.js` (line 6)

```js
const ADDITIVE_COLORMAP_EXT = new AdditiveColormapExtension();
```

**Classification: Intentional global.** Stateless singleton — sharing it avoids
re-initialising Viv's GPU pipeline on every channel-setting change. The
`AdditiveColormapExtension` object carries no per-render mutable state.
No change required.

### 3. `window.*` references in `entry.js` (lines 11–12)

```js
window.__anybioimage_perf_report = getPerfReport;
window.__anybioimage_perf_clear = clearPerf;
```

**Classification: Intentional global.** These are debug/test probe hooks.
They write to `window` only once (at module load) so repeated widget mounts
overwrite with the same functions. No interference between widget instances.
No change required.

### 4. `window.__ANYBIOIMAGE_PERF` in `util/perf.js` (line 21)

```js
return typeof window !== 'undefined' && window.__ANYBIOIMAGE_PERF === true;
```

**Classification: Intentional global.** A read-only feature flag; the module
writes nothing to `window`. The `_marks` and `_rings` Maps in `perf.js` are
module-level, but they are a deliberate aggregated performance ring-buffer for
the whole page session — not per-widget. No change required.

### 5. `window` listeners — `installKeyboard`

**Classification: Fixed in Task 4.** `installKeyboard` previously attached to
`window`. Since Task 4 it accepts a `containerEl` argument and attaches the
listener to the focusable root `div` of each widget. No global listener remains.
Verified: `keyboard.js` calls `containerEl.addEventListener('keydown', handler)`
and returns a disposer that calls `containerEl.removeEventListener(...)`.

### 6. `document.addEventListener`

No hits. No global document listeners exist.

### 7. Unclosed timers

#### 7a. `anywidget-source.js` — `_flushTimer`

`_flushTimer` is set via `setTimeout(..., 0)` inside `getTile()`.
`destroy()` calls `clearTimeout(this._flushTimer)`. **OK — cleaned up.**

#### 7b. No `setInterval` usage found anywhere in the source tree.

### 8. `model.on` / `model.off` symmetry

All `model.on(...)` calls found:

| File | Event | `model.off` in cleanup? |
|---|---|---|
| `App.jsx` | `change:tool_mode` | Yes — returned from `useEffect` |
| `App.jsx` | `keyboard` via `installKeyboard` | Yes — disposer returned from `useEffect` |
| `DeckCanvas.jsx` | `msg:custom` (reset-view) | Yes |
| `anywidget-source.js` | `msg:custom` | Yes — `destroy()` |

All listeners have matching `off`-handlers or disposers. No leaks.

---

## Finding requiring a fix — tool module-level state (FIXED)

### 9. `polygon.js`, `rect.js`, `point.js` — module-level `_state` (FIXED)

**Classification: Accidental global — fixed.**

Before this task each tool exported a singleton object with module-level mutable
state:

```js
// polygon.js (before)
const _state = { vertices: null, hover: null };
let _nextId = 1;
export const polygonTool = { … };

// rect.js (before)
const _state = { drag: null };
let _nextId = 1;
export const rectTool = { … };

// point.js (before)
const _state = { downX: null, downY: null };
let _nextId = 1;
export const pointTool = { … };
```

With two widgets on the page, both `InteractionController` instances registered
the *same* singleton. A polygon in-progress in widget A could be stomped (or
committed to) by widget B when the user clicked in widget B while widget A had
active vertices.

**Root fix:** converted each tool to a factory function. Each `App` instance
calls the factory inside its `useMemo(() => …, [model])` and registers the
fresh per-instance tool with its own `InteractionController`.

```js
// polygon.js (after)
export function makePolygonTool() {
  const _state = { vertices: null, hover: null };
  return { id: 'polygon', … };   // closure over instance-private _state
}

// rect.js (after)
export function makeRectTool() {
  const _state = { drag: null };
  return { id: 'rect', … };
}

// point.js (after)
export function makePointTool() {
  const _state = { downX: null, downY: null };
  return { id: 'point', … };
}
```

`App.jsx` updated accordingly:

```js
const controller = useMemo(() => {
  const rectTool    = makeRectTool();
  const polygonTool = makePolygonTool();
  const pointTool   = makePointTool();
  const c = new InteractionController(model);
  c.register(panTool); c.register(selectTool);
  c.register(rectTool); c.register(polygonTool); c.register(pointTool);
  c._rectTool = rectTool; c._polygonTool = polygonTool;  // for reset on tool_mode change
  return c;
}, [model]);
```

The module-level `_nextId` counters remain global — this is intentional.
They only need to be monotone within a JS session, and annotation IDs are
namespaced by `kind` prefix (`rect_`, `poly_`, `point_`) plus a timestamp.

**Tests updated:** each test file now calls the factory in `beforeEach` to get
a fresh instance. Three new isolation tests (one per tool) assert that two
independent instances do not share state.

---

## InteractionController — `activeTool` per-instance

`activeTool` is a getter that reads `this._model.get('tool_mode')` and looks up
from `this._tools` (a `Map` on the instance). Both `_model` and `_tools` are
assigned in the constructor. Confirmed per-instance. No change required.

## AnywidgetPixelSource — `_pendingBatch`, `_pending`, `_flushTimer`

All three are assigned as `this._...` in the constructor. Confirmed per-instance.
`destroy()` clears them. No change required.

## MaskSourceBridge

Instantiated via `useMemo(() => new MaskSourceBridge(model), [model])` in
`App.jsx`. Per-instance. `useEffect(() => () => maskBridge.destroy(), [maskBridge])`
ensures cleanup. No change required.

---

## Summary

| # | Finding | Classification | Action |
|---|---|---|---|
| 1 | `_nextRequestId` in `anywidget-source.js` | Intentional global | None |
| 2 | `ADDITIVE_COLORMAP_EXT` in `buildImageLayer.js` | Intentional global | None |
| 3 | `window.__anybioimage_perf_*` in `entry.js` | Intentional global | None |
| 4 | `window.__ANYBIOIMAGE_PERF` in `perf.js` | Intentional global | None |
| 5 | `installKeyboard` on `window` | Fixed in Task 4 | None |
| 6 | `document.addEventListener` | Not present | None |
| 7 | `setInterval` / `setTimeout` | All cleaned up in `destroy()` | None |
| 8 | `model.on` without matching `model.off` | All paired | None |
| 9 | Tool singletons: `polygon.js`, `rect.js`, `point.js` | **Accidental global — FIXED** | Factory refactor |

**Accidental globals found:** 1 (tool singleton state — polygon/rect/point).
**Fixed:** Yes. Factory functions, tests updated, 3 new isolation tests added.
**Commit:** see git log for "fix(tools): convert tool singletons to per-instance factories".
