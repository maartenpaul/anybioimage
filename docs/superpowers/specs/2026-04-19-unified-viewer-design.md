# Unified BioImageViewer — design spec

> Output of the `superpowers:brainstorming` skill. Feed this spec into `superpowers:writing-plans` to produce an implementation plan when ready to build.

**Status:** approved 2026-04-19. Targets branch `feature/viv-backend`. Supersedes `2026-04-16-viv-backend-design.md`.

**Goal (one sentence):** Replace the two-backend split with a single rendering pipeline (Viv + deck.gl on WebGL2) that handles every input — remote OME-Zarr, local OME-Zarr, HCS plates, local TIFF/CZI/ND2 via bioio, and raw numpy — and carries the full Fiji/napari-style channel model, annotation toolkit, measurement tools, and display features (colormaps, scale bar, metadata panel, pixel-info hover) on one coherent canvas.

**Tech stack:** Python anywidget + traitlets · React 18 · `@hms-dbmi/viv` · `zarrita` (npm) · `deck.gl` (`MultiscaleImageLayer`, `BitmapLayer`, `PolygonLayer`, `ScatterplotLayer`, `PathLayer`, `EditableGeoJsonLayer`) · esbuild · `hatch-jupyter-builder` · Playwright · vitest.

---

## 1. User-visible behaviour

One widget, one API. No backend keyword.

```python
from anybioimage import BioImageViewer
import numpy as np
from bioio import BioImage

v = BioImageViewer()

v.set_image("https://s3.example.com/my.ome.zarr")   # remote zarr — direct browser fetch
v.set_image(BioImage("local.tif"))                  # local TIFF — chunk bridge to browser
v.set_image(np.random.rand(10, 3, 5, 2048, 2048))   # numpy — chunk bridge
v.set_plate("plate.zarr")                           # HCS plate — well/FOV dropdowns

# Every input type supports every feature: channel LUTs, masks, annotations,
# SAM, measurement, export, undo/redo, pixel-info hover, scale bar.
```

- `render_backend` kwarg accepted for one release with a `DeprecationWarning`, then removed.
- WebGL2 required. No silent Canvas2D fallback — widget shows a clear message if the browser lacks WebGL2.
- All existing public API surface stays: `set_image`, `set_plate`, `add_mask`, `enable_sam`, `rois_df`, `polygons_df`, `points_df`, plus all traitlets (`current_t`, `current_z`, `channel_settings`, etc.).

Logical workflows mirror Fiji / napari:

- Channels behave like napari image layers — each has independent visibility, colour / LUT, contrast (min/max), gamma, blending (Composite default).
- Masks behave like napari label layers — stacked, each with its own visibility / opacity / colour.
- Annotations behave like napari shape / point layers — typed, editable, selectable, with per-item metadata.

---

## 2. Architecture

### Module layout

```
anybioimage/
├── viewer.py                         # BioImageViewer — public API unchanged
├── mixins/
│   ├── image_loading.py              # slimmed: drops tile/composite caches, keeps metadata + percentile init
│   ├── pixel_source.py               # NEW — chunk-bridge handler for AnywidgetPixelSource
│   ├── plate_loading.py              # existing, uses _zarr_source
│   ├── annotations.py                # unified _annotations traitlet + legacy DataFrame properties
│   ├── mask_management.py            # unchanged Python API, maps to deck.gl BitmapLayer
│   ├── sam_integration.py            # unchanged
│   └── measurements.py               # NEW — line / area / line-profile handlers
├── frontend/
│   ├── __init__.py
│   └── viewer/                       # the one frontend (was frontend/viv/)
│       ├── package.json
│       ├── build.config.mjs
│       ├── size-limit.config.cjs
│       ├── src/
│       │   ├── entry.js              # anywidget render()
│       │   ├── App.jsx               # top-level React tree (chrome + deck.gl canvas)
│       │   ├── chrome/
│       │   │   ├── Toolbar.jsx       # Pan / Select / Rect / Polygon / Point / Line / AreaMeasure / LineProfile / Reset / Layers
│       │   │   ├── DimControls.jsx   # T / Z sliders, Well / FOV selectors
│       │   │   ├── StatusBar.jsx     # T · Z · x,y · intensities · active-tool readout
│       │   │   └── LayersPanel/
│       │   │       ├── LayersPanel.jsx
│       │   │       ├── MetadataSection.jsx
│       │   │       ├── ImageSection.jsx   # channels with LUT / min / max / gamma
│       │   │       ├── MasksSection.jsx
│       │   │       ├── AnnotationsSection.jsx
│       │   │       └── ExportFooter.jsx
│       │   ├── render/
│       │   │   ├── DeckCanvas.jsx     # the single deck.gl instance + layer composer
│       │   │   ├── pixel-sources/
│       │   │   │   ├── zarr-source.js           # zarrita — remote/local URL
│       │   │   │   └── anywidget-source.js      # NEW — chunk bridge PixelSource
│       │   │   ├── layers/
│       │   │   │   ├── buildImageLayer.js
│       │   │   │   ├── buildMaskLayers.js
│       │   │   │   ├── buildAnnotationLayers.js
│       │   │   │   ├── buildMeasurementLayers.js
│       │   │   │   ├── buildScaleBar.js
│       │   │   │   └── buildSamPreview.js
│       │   │   └── luts/
│       │   │       ├── index.js                 # colormap registry
│       │   │       ├── lut-textures/*.png       # 256×1 RGBA LUT assets
│       │   │       └── VivLutExtension.js       # custom shader extension
│       │   ├── interaction/
│       │   │   ├── InteractionController.js    # dispatches pointer events per tool_mode
│       │   │   ├── tools/
│       │   │   │   ├── pan.js
│       │   │   │   ├── select.js                # mounts EditableGeoJsonLayer
│       │   │   │   ├── rect.js
│       │   │   │   ├── polygon.js
│       │   │   │   ├── point.js
│       │   │   │   ├── line.js                  # measurement
│       │   │   │   ├── areaMeasure.js
│       │   │   │   └── lineProfile.js
│       │   │   ├── keyboard.js                  # shortcut map
│       │   │   └── undo.js                      # in-JS undo stack
│       │   ├── model/
│       │   │   ├── useModelTrait.js             # traitlet ↔ React hook
│       │   │   └── channelState.js              # mapping _channel_settings ↔ Viv props
│       │   └── util/
│       │       ├── debounce.js
│       │       └── coords.js                    # pixel ↔ screen transforms
│       └── dist/
│           └── viewer-bundle.js                 # committed build artefact
└── backends/                         # DELETED — no more backend registry
```

### Deletions

- `anybioimage/frontend/shared/canvas2d.js` — 1670 lines.
- `anybioimage/backends/` — directory.
- `anybioimage/mixins/image_loading.py` tile/composite/thumbnail code:
  - `_composite_cache`, `_composite_cache_lock`, `_tile_cache`, `_tile_cache_lock`.
  - `_precompute_all_composites`, `_precompute_composites_remote`.
  - `_update_slice`, `_viewport_tiles_all_cached`.
  - `use_jpeg_tiles` traitlet.
  - PNG encoding, base64 helpers, viewport-tile traitlet plumbing.
- `_viv_mode` traitlet (no more dual-mode selection).
- `examples/full_demo.py` replaces the set of ad-hoc example notebooks.

### Routing — two pixel-source paths, one renderer

| Input | PixelSource | Chunk fetch |
|---|---|---|
| URL string (`http(s)://`, `s3://`, `file://`) that looks like OME-Zarr | Viv's `ZarrPixelSource` via `loadOmeZarr` (zarrita) | Direct browser fetch — Python uninvolved |
| `bioio.BioImage`, `numpy.ndarray`, local non-zarr path | `AnywidgetPixelSource` (new) | JS requests chunks via `model.send()`; Python reads slice from in-RAM array or lazy bioio reader, replies with raw bytes in `buffers` |
| HCS plate OME-Zarr | Same as URL path; well/FOV update `_zarr_source.subpath` | Direct browser fetch |

### Chunk-bridge contract (`AnywidgetPixelSource`)

Implements Viv's `PixelSource` interface:

```js
{
  shape: { t, c, z, y, x },
  labels: ['t','c','z','y','x'],
  tileSize: 512,
  dtype: 'uint8' | 'uint16' | 'uint32' | 'float32',
  async getTile({ x, y, selection, signal }),
  async getRaster({ selection }),
}
```

Protocol — JSON message + binary buffers:

```
JS  → Py : { kind: "chunk", requestId, t, c, z, level, tx, ty, tileSize }
Py  → JS : { kind: "chunk", requestId, ok: true, w, h, dtype, byteOrder } + buffers: [ArrayBuffer]
Py  → JS : { kind: "chunk", requestId, ok: false, error: "..." }  (on failure)
```

- Dtype passed verbatim; Viv uploads to a WebGL2 texture of matching type — no quantisation, no byte reshuffling in JS.
- `signal` cancels the awaiter; Python drops the response on arrival if the requestId is no longer pending.
- Python side: bounded LRU raw-chunk cache (default 256 entries, ~256 MB for 512×512×uint16) to absorb repeat requests during Z/T scrubbing. Enabled only for `AnywidgetPixelSource` (zarrita handles its own caching).
- No PNG encoding. No base64. No composite cache. No thumbnail image. Viv composites on the GPU.

### Build pipeline

- Single frontend tree under `anybioimage/frontend/viewer/`.
- `hatch-jupyter-builder` runs `npm install && npm run build` at wheel-build time.
- `dist/viewer-bundle.js` committed to git for `pip install -e .` without Node.
- CI bundle-freshness job verifies the committed bundle matches source.
- `size-limit` guardrail at **4 MB gzip** (accommodates deck.gl + Viv + LUT textures).

---

## 3. Layer stack (single deck.gl canvas)

Bottom → top:

1. `MultiscaleImageLayer` — Viv's multichannel composite. Up to 6 active channels (Viv limit). LUT lookup via custom extension when a channel has `color_kind: "lut"`; solid-colour fast path otherwise.
2. `BitmapLayer[]` — one per mask, additive alpha. Contour variant generated Python-side as an edge-only bitmap when `contours=True` on `add_mask()`.
3. Scale-bar overlay — a custom screen-space deck.gl layer (`ScaleBarLayer` in this codebase) built on `CompositeLayer`; suppressed when `pixel_size_um` is `None`.
4. `PolygonLayer` (rect + polygon annotations) + `ScatterplotLayer` (points) + `PathLayer` (line / area measurements).
5. `EditableGeoJsonLayer` — mounted only while tool is `select`; wraps the annotations for drag / resize / vertex-edit. Unmounted otherwise for perf.
6. `BitmapLayer` (SAM preview) — transient, cleared on commit/cancel.

All layers share the image's pixel coordinate space; pan/zoom driven by a single deck.gl view state.

---

## 4. Channel model (Fiji / napari-style)

### Traitlet

```python
_channel_settings = traitlets.List(traitlets.Dict()).tag(sync=True)
# per entry:
# { index, name, visible,
#   color_kind: "solid"|"lut",
#   color: "#rrggbb",          # used when color_kind == "solid"
#   lut: "viridis",            # used when color_kind == "lut"
#   min: 0.0, max: 1.0,        # normalised to [0,1] of data range
#   data_min, data_max,        # absolute dtype range
#   gamma: 1.0,
#   display_mode: "composite"|"single",   # image-level — stored on channel 0 or a sibling traitlet
# }
```

### Display modes (Fiji parity)

- **Composite** (default) — all visible channels blended additively in one shader pass.
- **Single** — only one active channel is rendered; others hidden regardless of their `visible` flag. The active channel is the one most recently toggled. `[` / `]` moves the active channel.

### Colormaps / LUTs

- Registry in `frontend/viewer/src/render/luts/index.js`.
- Shipped: `gray`, `viridis`, `plasma`, `magma`, `inferno`, `cividis`, `turbo`, `red`, `green`, `blue`, `cyan`, `magenta`, `yellow`, `hot`, `cool`.
- Each as a 256×1 RGBA PNG (bundled as an import asset). Uploaded to GPU once per unique LUT per session, cached.
- `VivLutExtension` — custom Viv extension (~80 lines GLSL + JS). Samples `lut[intensity]` when the channel's uniform flag says so, otherwise the default solid-colour path.

### Histogram + Auto

- Existing Python histogram round-trip (`_histogram_request` / `_histogram_data`) retained for the mini-histogram strip under each channel's min/max sliders. Histograms computed from currently loaded raster — fast for in-RAM arrays, sample-based for remote zarr.
- `Auto` button uses Viv's `getChannelStats` (already present) — no Python round-trip.

---

## 5. Annotations (unified)

### Traitlet

```python
_annotations = traitlets.List(traitlets.Dict()).tag(sync=True)
# each entry:
# { id, kind: "rect"|"polygon"|"point"|"line"|"area",
#   geometry,              # rect: [x0,y0,x1,y1]; polygon: [[x,y],...]; point: [x,y]; line: [[x,y],[x,y]]; area: [[x,y],...]
#   label, color, visible, t, z,
#   created_at,            # ISO string
#   metadata,              # dict — e.g. SAM score, measurement length, pixel_size used
# }
```

### Backwards compatibility

`.rois_df`, `.polygons_df`, `.points_df` keep their current shape. Each is a property that filters `_annotations` by kind and returns the same DataFrame columns as today. Old notebooks keep working.

### Coordinates

Stored in image pixel space. Survives zoom / pan / resize / resolution-level changes. Directly usable for downstream numpy indexing.

### Visibility filter

Annotations with `t != current_t` or `z != current_z` are hidden by default. A Layers-panel toggle ("Show all T/Z") opts in to rendering the full set (useful for labelling workflows).

### SAM integration

Unchanged on Python (existing `sam_integration.py` mixin). Rect- or point-tool completion sends the geometry to Python → SAM runs → Python returns a `{mask_bytes, shape}` response → `buildSamPreview.js` shows it → on commit the mask is added via `add_mask()` (standard path).

---

## 6. Interaction

### Toolbar

`Pan | Select | Rect | Polygon | Point | Line | AreaMeasure | LineProfile | Reset | Layers`

`tool_mode` traitlet drives which tool's handlers are active. The toolbar buttons observe the traitlet and update their `.active` state (fixes existing bug where externally setting `tool_mode` left buttons visually stale).

### Tool registry

Each tool is a separate file exporting a common shape:

```js
{
  id: "rect",
  cursor: "crosshair",
  onPointerDown(event, ctx),
  onPointerMove(event, ctx),
  onPointerUp(event, ctx),
  onKeyDown(event, ctx),
  getPreviewLayer(state),        // transient deck.gl layer during draw
}
```

`InteractionController` holds the current tool's state object, dispatches pointer events from deck.gl, and is the only thing that mutates `_annotations` / `_measurements`.

### Editing (Select tool)

- `EditableGeoJsonLayer` mounted only when `tool_mode === "select"`. Unmounted otherwise.
- Drag / resize / vertex-add / vertex-delete handled entirely by deck.gl.
- Local React state holds the live geometry during the gesture.
- One `model.set("_annotations", ...)` + `model.save_changes()` on pointer-up.

### Measurement tools

- **Line** — click-click. Distance in pixels; + µm if `pixel_size_um` present. Result stored as an `_annotations` entry with `kind: "line"`; live readout in status bar during drag.
- **Area** — polygon draw; area in px² / µm² + perimeter. Stored as `kind: "area"`.
- **LineProfile** — line draw; Python sampled along it via `_histogram_request`-style round-trip returning `{xs, ys}` → status-bar inline sparkline. Result persisted only if the user clicks "Save profile" — otherwise transient.

### Undo / redo

- JS-side `UndoStack` (50-entry ring buffer).
- Snapshots taken on gesture-end (mouse-up after draw / edit / delete), not per-frame.
- Snapshot shape: `{annotations, masks, measurements}` at that moment.
- `Ctrl+Z` / `Ctrl+Shift+Z`. Not persisted across sessions.

### Keyboard shortcuts

| Key | Action |
|---|---|
| `←` / `→` | T −1 / +1 |
| `↑` / `↓` | Z +1 / −1 (up = shallower) |
| `[` / `]` | Previous / next active channel |
| `,` / `.` | Brightness −/+ |
| `V` / `P` | Select / Pan |
| `R` / `G` / `O` / `L` / `M` | Rect / polyGon / pOint / Line / areaMeasure |
| `Delete` / `Backspace` | Remove selected annotation |
| `Ctrl`+`Z` / `Ctrl`+`Shift`+`Z` | Undo / redo |
| `Esc` | Cancel current draw |
| `Space` (hold) | Temporary Pan |

Shortcuts disabled when focus is inside a text input / colour picker / slider.

### Export

Layers-panel footer: **Export CSV**, **Export JSON**, **Copy to clipboard**.

- CSV / JSON — JS sends `{kind: "export", format, target}` → Python returns a single bytes payload (CSV is `pd.concat(...).to_csv()`; JSON is `_annotations` serialised) → JS triggers a browser download.
- Copy — JS-only, serialises `_annotations` to a JSON string and writes to clipboard.

---

## 7. Display features (v0.4.0 items, delivered here)

### Scale bar

- `buildScaleBar.js` — custom deck.gl `CompositeLayer` that draws a screen-space rectangle + text label.
- Reads `pixel_size_um` (populated by `image_loading.py` from `BioImage.physical_pixel_sizes` or OME `.zattrs.multiscales[0].coordinateTransformations`).
- Picks a nice-round physical length (1, 2, 5, 10, 20, 50, 100 µm …) whose pixel width lands in 60–200 px at the current zoom.
- Toggleable in Layers-panel footer. Hidden when `pixel_size_um is None`.

### Pixel info on hover

- deck.gl `onHover` → pixel coords + per-channel intensities, read from Viv's already-loaded raster (no Python round-trip).
- Displayed in status bar as `x, y · ch1:12345 · ch2:678`.
- Throttled to 60 Hz; no websocket traffic.

### Metadata panel

- Collapsed section at top of Layers panel.
- Populated from `BioImage.metadata` and OME `.zattrs` on image load: file name, shape, dtype, pixel size (µm), channel names, acquisition date if present.
- Plain HTML — not a deck.gl layer.

### Resize behaviour

- deck.gl canvas fills its container, sized via `ResizeObserver`.
- `canvas_height` traitlet kept as a `min-height` hint (back-compat only).

---

## 8. Phasing — three checkpoints on `feature/viv-backend`

Each phase ends in a mergeable, demo-app-testable state.

### Phase 1 — Unified core

**Delivers:** chunk bridge, `AnywidgetPixelSource`, deletion of Canvas2D + compositing code, unified Layers panel with channel LUTs, metadata section, pixel-info hover, scale bar, resize behaviour, full keyboard shortcut map for dim navigation + tool switching.

**Demo app at end of phase:** loads a local TIFF, a local OME-Zarr, a remote OME-Zarr, an HCS plate. Exercises every channel control (visibility, LUT switch, min/max, gamma, Composite vs Single, Auto).

**Merge gate:** all Phase-1 demo sections smoke-test green under Playwright; perf budget met for pan/zoom, channel slider, T slider on in-RAM local.

### Phase 2 — Annotate MVP

**Delivers:** rect / polygon / point tools, mask overlays via `BitmapLayer`, SAM hookup, unified `_annotations` traitlet with back-compat DataFrame properties. Interaction controller + tool registry. No editing yet.

**Demo app:** adds annotation walkthrough + SAM section.

**Merge gate:** all Phase-1 tests still green; new Playwright tests for draw-rect, draw-polygon, draw-point, SAM flow pass.

### Phase 3 — Editing + measurement + undo

**Delivers:** `EditableGeoJsonLayer` for Select, Line / Area / LineProfile tools, undo/redo stack, export buttons, annotation visibility filter (current-slice vs all-slices toggle).

**Demo app:** adds measurement section and export section. Perf cell lands.

**Merge gate:** all earlier tests still green; edit / measure / export / undo Playwright tests pass; perf budget met across every metric.

After Phase 3: merge `feature/viv-backend` → `main` as v0.7.0 (drop the `-alpha`). `render_backend` kwarg still accepted with deprecation warning for one release, then removed in v0.8.0.

---

## 9. Demo marimo app — `examples/full_demo.py`

The single source of truth for manual testing *and* user-facing showcase. Every Playwright test has a corresponding section / cell here.

Sections:

1. **Welcome / quick start** — one-cell "load any image, see it, pan, zoom."
2. **Local TIFF** — bundled small TIFF; channel controls + LUT switching demo.
3. **Local OME-Zarr** — unpacked `examples/image.zarr`.
4. **Remote OME-Zarr** — public IDR sample; tests zarrita direct fetch + CORS handling.
5. **HCS plate** — Well / FOV dropdowns.
6. **Annotations** — draw rect / polygon / point interactively; live view of `rois_df`, `polygons_df`, `points_df`.
7. **SAM** — "click a cell, get a mask" walkthrough (only runs if SAM extra installed; shows a clear "pip install anybioimage[sam]" prompt otherwise).
8. **Measurements** — line distance, polygon area, intensity line profile with inline matplotlib plot.
9. **Display features** — colormap switcher, scale bar on/off, metadata panel walkthrough.
10. **Export** — buttons trigger CSV / JSON download; also shows the round-trip back into pandas.
11. **Perf** — a "Run benchmark" button that measures every target in section 10 and prints a table.

Replaces the current `examples/image_notebook.py` (which will be removed at end of Phase 3).

---

## 10. Performance budget

Measured against the demo-app perf cell. All values p95.

| Metric | Target |
|---|---|
| Pan / zoom at steady state | 60 fps |
| Channel slider drag → GPU visible change | ≤16 ms |
| T slider scrub (local TIFF, in-RAM array) | ≤30 ms per step |
| T slider scrub (remote OME-Zarr, cached chunks) | ≤50 ms per step |
| Cold tile fetch — local TIFF via chunk bridge | ≤30 ms |
| Cold tile fetch — remote OME-Zarr via zarrita | ≤150 ms (WAN-dependent) |
| Rect draw / commit / undo | ≤5 ms each |
| SAM mask render after Python returns | ≤200 ms |
| Cold `set_image()` → first frame visible, local TIFF | ≤2 s for 500 MB in-RAM |
| Cold `set_image()` → first frame visible, remote OME-Zarr | ≤1 s over typical broadband |
| Bundle size (gzipped) | ≤4 MB |

If chunk-bridge cold-fetch misses its target, the Python-side bounded LRU chunk cache absorbs repeat requests during Z/T scrubbing. That's already in the design — see section 2.

---

## 11. Testing

### Python (`uv run pytest tests/ -v`)

- `tests/test_pixel_source.py` — chunk-bridge message protocol: request → slice → response buffers round-trip, cancellation, error path.
- `tests/test_annotations_unified.py` — round-trip of each kind via `_annotations`; DataFrame property shape unchanged vs main; legacy migration from split traitlets.
- `tests/test_metadata_extraction.py` — `pixel_size_um`, channel names, dtype correctly populated from BioImage and from OME `.zattrs`.
- `tests/test_image_loading_slim.py` — metadata-only path (no PNGs, no composites, no tile cache created).
- `tests/test_plate_unified.py` — FOV switch updates `_zarr_source`; no bioio load path triggered.
- `tests/test_chunk_cache.py` — Python LRU bounds, eviction, request-coalesce under concurrent scrub.

### JS (`npm run test` — vitest)

- `interaction/tools/*.test.js` — pointer-event dispatch per tool.
- `interaction/undo.test.js` — snapshot push, pop, redo, ring-buffer bound.
- `render/luts/index.test.js` — LUT texture builder outputs correct RGBA from PNG.
- `util/coords.test.js` — pixel↔screen round-trip at arbitrary zoom/pan.
- `model/channelState.test.js` — `_channel_settings` → Viv props mapping incl. LUT mode.

### Playwright (one flow per demo-app section)

- Phase-1 flows: local TIFF render, local zarr render, remote zarr render, HCS plate switch, channel LUT change, channel min/max, channel Composite/Single, scale bar visibility, metadata panel populated.
- Phase-2 flows: rect draw, polygon draw, point draw, SAM mask, mask visibility toggle.
- Phase-3 flows: annotation drag-edit, line measurement, area measurement, line profile, undo, redo, CSV export, JSON export.

Screenshots under `/tmp/anybioimage-screenshots/` per `CLAUDE.md`.

---

## 12. Migration & back-compat

- `BioImageViewer(render_backend=...)` — accepted for v0.7.x with `DeprecationWarning` on first call per kernel. Removed in v0.8.0.
- `_render_backend`, `_viv_mode` traitlets — removed. No back-compat; they were private.
- `use_jpeg_tiles` traitlet — removed. Private.
- `.rois_df`, `.polygons_df`, `.points_df` — unchanged shape.
- `set_image`, `set_plate`, `add_mask`, `enable_sam` — unchanged signatures + behaviour.
- `channel_settings` public accessor — unchanged shape; `color_kind` / `lut` / `gamma` are additive fields, old code that only reads `color` / `min` / `max` / `visible` keeps working.
- Notebook files written with older `anybioimage` continue to render (traitlet shapes accept the new optional fields as defaults).

CHANGELOG.md entry under `### Breaking` documents: `render_backend` deprecation, dropped internal traitlets, WebGL2 requirement.

README.md update: MIT attribution for Viv, zarrita.js, deck.gl, nebula.gl (EditableGeoJsonLayer).

---

## 13. Risks & open items

### Risks (mitigations in the design)

- **Chunk-bridge cold-path latency for big TIFFs.** Spike at start of Phase 1 confirms ≤30 ms p95; bounded Python chunk cache and pre-fetch-on-slice-change are already designed in as fallbacks.
- **LUT count vs bundle size.** 15 LUTs at 256×1 PNG = ~30 KB total. Negligible.
- **EditableGeoJsonLayer / nebula.gl bundle weight.** Mounted only in Select mode; its bundle chunk can be lazy-loaded if the 4 MB budget is threatened.
- **WebGL2 availability.** Target ≥99% browsers today; clear error message otherwise. No silent fallback.
- **Viv 6-channel shader limit.** Indicator in the UI when >6 channels visible; matches current alpha behaviour.
- **CORS on self-hosted zarr.** Caught + surfaced as a clear error with a remediation note in the demo-app remote-zarr section.

### Open items (resolved during implementation)

- Whether to pre-fetch `(t±1, z±1)` chunks on scrub settle, or rely on Viv's own LRU.
- Whether to lazy-load the nebula.gl chunk (only mounted when Select is chosen).
- Exact shape of the measurement "save profile" persistence (annotation entry vs separate table).
- Whether `display_mode` lives on channel 0 or as a sibling traitlet.

---

## 14. Decisions locked in

1. **One backend, no user-visible switch.** `render_backend` kwarg deprecated then removed.
2. **Viv + deck.gl on WebGL2, required.** No Canvas2D fallback.
3. **Chunk bridge for non-URL inputs.** `AnywidgetPixelSource` + Python slice-on-demand. No PNG compositing; no thumbnail; no tile cache traitlet.
4. **Unified `_annotations`, back-compat DataFrame properties.**
5. **Fiji / napari channel model.** Per-channel LUT, gamma, Composite vs Single mode.
6. **Tool registry pattern.** One file per tool.
7. **In-JS undo stack; not persisted.**
8. **Three-phase landing on `feature/viv-backend`.** Phase 1 = unified core; Phase 2 = annotate MVP; Phase 3 = editing + measurement + undo + export. Merge to `main` as v0.7.0 after Phase 3.
9. **`examples/full_demo.py`** — single source of truth for manual + Playwright tests.
10. **Performance budget** written into the demo-app perf cell; measured, not asserted in isolation.

## 15. Files anticipated to change

Read-only reference — writing-plans will own the exact file list.

- `anybioimage/viewer.py` — drop backend registry / `_esm` swap; single `_esm` import from `frontend/viewer/dist/viewer-bundle.js`; new unified traitlets.
- `anybioimage/mixins/image_loading.py` — remove compositor / tile cache; keep metadata + percentile channel init.
- `anybioimage/mixins/pixel_source.py` — new; chunk bridge.
- `anybioimage/mixins/annotations.py` — unified `_annotations`; DataFrame property compat shim.
- `anybioimage/mixins/mask_management.py` — keep API, change transport from bitmap traitlet + base64 to `model.send()` with binary buffers.
- `anybioimage/mixins/measurements.py` — new; line / area / line-profile handlers.
- `anybioimage/mixins/plate_loading.py` — minor; always sets `_zarr_source`.
- `anybioimage/frontend/viewer/` — new; full tree per section 2.
- `anybioimage/backends/` — deleted.
- `anybioimage/frontend/shared/canvas2d.js` — deleted.
- `examples/full_demo.py` — new; replaces ad-hoc examples.
- `examples/image_notebook.py` — deleted.
- `tests/` — new unit tests; Playwright suite per section 11.
- `pyproject.toml` — single frontend entry in `hatch-jupyter-builder`.
- `README.md` — MIT attributions; updated usage to single API.
- `CHANGELOG.md` — Breaking section for this release.
- `ROADMAP.md` — merged Viv-backend table into main roadmap; v0.4.0/v0.5.0 items marked delivered.

## 16. Reference — from brainstorming discussion

- Approach A (Viv-everywhere + anywidget chunk bridge) was chosen over Approach B (Canvas2D-only) and Approach C (internal auto-select with both engines) because it gives one rendering pipeline and the smallest future maintenance surface, while being testable early with a chunk-bridge spike.
- Scope chosen: **Annotate-Plus phased** — all annotation, measurement, export, display-feature items from the roadmap (v0.4.0 + v0.5.0 + v0.7.x), landed in three phases on `feature/viv-backend`.
- UI shape **kept similar to main branch** — same toolbar layout, collapsible Layers panel (not napari-style always-on sidebar).
- Channel behaviour **modelled on Fiji / napari** — per-channel LUT, gamma, Composite vs Single display mode.
