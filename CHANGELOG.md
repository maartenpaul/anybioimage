# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — targeting v0.7.0

### Added — Phase 2.5 (Hardening + Integration Tier)

- **Integration test tier** under `tests/integration/`. Drives a real
  Playwright + chromium browser against a `marimo run` server, asserts
  via traitlets, enforces perf budgets. New `integration` pytest marker.
- **`_render_ready` traitlet** — flipped True by JS once the first image
  layer renders; integration fixtures block on it.
- **Perf instrumentation** (`src/util/perf.js`) — `mark`, `measure`,
  `trace`, `getPerfReport`, `clearPerf`. Gated by `window.__ANYBIOIMAGE_PERF`.
  Hot paths wired: `layers:build` (+ per-type sub-labels `layers:image`,
  `layers:masks`, `layers:annotations`, `layers:preview`,
  `layers:scaleBar`), `pixelSource:getTile`, `buildImageLayerProps`,
  `interaction:<phase>`.
- **JS-side LRU tile cache + in-flight deduplication** in
  `AnywidgetPixelSource`. Cache hits avoid the Python round-trip
  entirely; concurrent callers for the same tile share one in-flight
  request rather than flooding the bridge.
- **SVG icon set** (`src/chrome/icons.js`) — Heroicons-style stroke-based
  icons for every toolbar tool, plus play/pause for the T-slider.
- **`NumericInput` component** — reusable numeric entry paired with the
  contrast sliders. Validates on blur/Enter, reverts on invalid, clamps
  to [min, max], Escape cancels.
- **Reset gamma button** (`1`) next to the gamma NumericInput.
- **Dtype-aware data-value display** — min/max columns now show data
  values (integer for uint8/uint16, scientific-when-large for uint32,
  4 sig figs for floats) instead of raw 0–100% percentages. Stored
  traits stay normalized [0, 1]; conversion uses `ch.data_min` /
  `ch.data_max`.

### Fixed — Phase 2.5

- **Select tool picks annotations** — `InteractionController.setContext`
  merges `pickObject` from `DeckCanvas` into the tool context. Select
  click now sets `selected_annotation_id` to the hit object's id.
- **Keyboard shortcuts scoped per widget** — `installKeyboard` now
  attaches to the viewer's root `.bioimage-viewer` div (which is already
  `tabIndex={0}`). Two widgets on a page no longer stack listeners.
- **Remote OME-Zarr renders visible pixels** — axes-aware selections +
  OMERO pre-fetch path.
- **`layers` useMemo split into per-type sub-memos** — channel toggles
  now rebuild only the image layer; mask / annotation / preview / scale
  bar memos don't rerun. `layers:image` p95 < 16 ms (budget met).
- **Tool singletons → per-instance factories** so two viewers in one
  notebook don't share tool state.

### Removed — Phase 2.5

- Disabled toolbar placeholders for `line`, `areaMeasure`, `lineProfile`.
  These will land when Phase 3 brings the tool implementation; until
  then there is no reason to render an unusable button.
- The mid-flight `prefetch()` method on `AnywidgetPixelSource` and the
  two `useEffect` prefetch hooks in `DeckCanvas` — they fought each
  other (settle prefetch aborted the initial full-dataset prefetch) and
  flooded the single-threaded Python chunk handler on burst-scrub. The
  cache + dedup pair already meets the budget on the realistic path. A
  proper prefetch needs a parallel Python-side handler first; tracked
  in `docs/superpowers/notes/phase2-5-perf-baseline.md`.

### Infrastructure — Phase 2.5

- `docs/superpowers/notes/widget-isolation-audit.md` — audit of
  `window.*`, module-level state, shared listeners.
- `docs/superpowers/notes/phase2-5-perf-baseline.md` — before/after
  numbers and the rationale for the simplified Task 10 path.
- `tests/integration/test_console_hygiene.py` — fails the suite on any
  unfiltered console error/warning during a 10 s demo load. Allow-list
  covers known-benign GPU driver / swiftshader / marimo dev-asset
  preload notices only.

### Added — Phase 2 (Annotate MVP)

- Unified `_annotations` traitlet — single list of typed entries with
  `id`, `kind`, `geometry`, `label`, `color`, `visible`, `t`, `z`,
  `created_at`, `metadata`.
- Back-compat DataFrame properties `rois_df`, `polygons_df`, `points_df`
  are now read/write views filtered by `kind` over `_annotations`. Existing
  notebooks keep working unchanged.
- Interactive drawing tools: **Rect** (drag), **Polygon** (click vertices,
  double-click / Enter to close, Esc to cancel), **Point** (click).
- Tool registry + `InteractionController` — one module per tool; pointer /
  key events dispatch through a single controller.
- Annotation layers rendered via deck.gl `PolygonLayer` + `ScatterplotLayer`
  mounted between the image layer and the scale bar; selected annotation
  is highlighted with a thicker stroke.
- Mask overlay transport switched from base64 PNG inside `_masks_data` to
  raw RGBA bytes via anywidget message buffers. `_masks_data` entries now
  carry metadata only. JS requests bytes lazily via `{kind:"mask_request"}`.
- New `MasksSection` and `AnnotationsSection` in the Layers panel with
  per-item visibility / opacity / color / contour / delete controls.
- SAM hookup: when `sam_enabled` is true, committing a rectangle or point
  sends `{kind: "sam_rect" | "sam_point"}` to Python; SAM runs and the
  produced mask arrives via the new mask transport.
- Demo notebook sections 7 (Annotations walkthrough) and 8 (SAM walkthrough,
  conditionally shown based on `ultralytics` availability).

### Removed (Breaking) — Phase 2

- `_rois_data`, `_polygons_data`, `_points_data` traitlets (private; no
  back-compat shim) — superseded by `_annotations`.
- `rois_visible`, `roi_color`, `polygons_visible`, `polygon_color`,
  `points_visible`, `point_color`, `point_radius` traitlets — per-kind
  styling now lives per-annotation in the unified list.

### Added — Phase 1 (Unified Pipeline)
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

## [0.3.0]

### Changed
- Renamed package from `anyimage` to `anybioimage`
- Updated all imports: `from anyimage import ...` → `from anybioimage import ...`
- Updated repository URLs and documentation
- Updated GitHub workflows and CI configuration
- Replaced all `print()` calls with proper `logging` module usage
- Narrowed broad `except Exception` to specific exception types where appropriate
- Consolidated duplicate JS event listeners for `current_t`/`current_z`
- Deduplicated cursor map definition in JS frontend (defined once as `CURSORS` constant)

### Added
- Automated PyPI publishing via GitHub releases
- Release process documentation (RELEASING.md)
- Comprehensive docstring for `BioImageViewer` class
- Widget `close()` method for proper resource cleanup (cancels precompute, shuts down thread pool)
- JS error boundary in `render()` to display errors instead of silently failing
- `CONTRIBUTING.md` with development setup and architecture guide
- `ROADMAP.md` with planned features by milestone
- Additional mixin and integration tests
- Project URLs in pyproject.toml (Documentation, Changelog, Issues)
- Python 3.13 classifier
- This changelog

### Fixed
- Version mismatch: `__init__.py` now matches `pyproject.toml` (was "0.1.0", now "0.3.0")
- Old package name "anyimage" references in documentation

### Removed
- Unused `build_channel_lut()` function and `_lut_cache` globals from `utils.py`

## [0.2.0] - Previous Release

Initial release as `anyimage` with core functionality:
- Multi-dimensional image viewer (5D: TCZYX)
- Mask overlay support
- Annotation tools (rectangles, polygons, points)
- SAM (Segment Anything Model) integration
- HCS plate support for OME-Zarr
- Tile-based rendering with caching
