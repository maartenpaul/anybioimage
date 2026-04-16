# Viv + zarrita.js rendering backend — design spec

> Output of the `superpowers:brainstorming` skill. Feed this spec into `superpowers:writing-plans` to produce an implementation plan when ready to build.

**Status:** approved by user on 2026-04-16. Slated for release as **v0.7.0-alpha**.

**Goal (one sentence):** Ship a second rendering backend for `BioImageViewer` that uses Viv (WebGL2 shader rendering) + zarrita.js (browser-direct OME-Zarr chunk fetch) alongside the existing Canvas2D backend, keeping the Python API identical so users opt in with a single keyword.

**Tech stack:** Python anywidget + React + `@hms-dbmi/viv` + `zarrita` (npm) + deck.gl, bundled via esbuild or vite through `hatch-jupyter-builder`.

---

## 1. User-visible behavior

Users opt in with a keyword argument; everything else stays the same.

```python
from anybioimage import BioImageViewer

# Default: Canvas2D backend, unchanged from v0.3.x
viewer = BioImageViewer()
viewer.set_image(bio_image)

# Opt in to Viv backend
viewer = BioImageViewer(render_backend="viv")
viewer.set_image("https://s3.example.com/my.ome.zarr")  # zarr URL → Viv renders
viewer.set_image(np.random.rand(...))                    # non-zarr → auto-fallback to Canvas2D
```

- All existing Python traitlets work identically: `viewer.current_t = 5`, `channel_settings = [...]`, `set_plate(...)`.
- The existing HTML/CSS channel panel (eye toggles, color picker, min/max sliders, histogram, auto-contrast) is re-used on the Viv backend; event handlers drive shader uniforms instead of Canvas2D composites.
- HCS plate dropdowns (well / FOV) work identically.
- Non-zarr inputs trigger a silent auto-fallback to Canvas2D for that image, with a one-line info log — no errors, no broken notebooks.
- Users who don't pass `render_backend="viv"` are unaffected.

---

## 2. Architecture

### Module layout

```
anybioimage/
├── viewer.py                    # BioImageViewer — unchanged public API
├── mixins/                      # Unchanged (image_loading, plate_loading, annotations, mask_management, sam_integration, utils)
├── backends/                    # NEW: registry + selection logic
│   ├── __init__.py
│   ├── canvas2d.py              # Existing inline ESM string moved here
│   └── viv.py                   # Loader for the bundled Viv JS
└── frontend/viv/                # NEW: React + Viv + zarrita source tree
    ├── package.json             # npm deps: @hms-dbmi/viv, zarrita, deck.gl, react
    ├── build.config.js          # esbuild or vite config
    ├── src/
    │   ├── entry.js             # anywidget render() entrypoint
    │   ├── VivCanvas.jsx        # React component wrapping Viv
    │   └── channel-sync.js      # Maps Python channel_settings → Viv props
    └── dist/
        └── viv-bundle.js        # Compiled output, shipped in wheel
```

### Coexistence model

- `_render_backend` traitlet chooses `"canvas2d"` (default, unchanged) or `"viv"` (new).
- Backend picked once per viewer construction via `__init__(render_backend=...)`. Swapping mid-session not in scope.
- Canvas2D backend stays as an inline `_esm` string — no Node required to touch it.
- Viv backend is a bundled JS file loaded from the Python package's static assets.

### Build pipeline — hybrid

- `hatch-jupyter-builder` runs `npm install && npm run build` in `anybioimage/frontend/viv/` at wheel-build time.
- `dist/viv-bundle.js` is included in the wheel as a data file.
- End users running `pip install anybioimage` receive a normal wheel with the pre-built bundle — no Node toolchain needed on their machine.
- CI (the existing PyPI publish workflow) gains a `setup-node@v4` step before building wheels.
- The pre-built bundle is checked in to git so `pip install -e .` works without Node for contributors who only touch Python. A CI guard verifies the checked-in bundle is in sync with source.
- Bundle-size guardrail via `size-limit` at ~3 MB gzip catches accidental heavy imports.

---

## 3. Data flow & state sync

Python traitlets are the source of truth for state. JS emits user-interaction events back via `model.set`. The anywidget sync layer carries state in both directions.

### Traitlets

| Traitlet | Direction | Purpose |
|---|---|---|
| `_render_backend` | Py → JS | Selects the bundle loaded at construction. |
| `_zarr_source` (dict, new) | Py → JS | `{url, headers, subpath}` — zarrita.js opens the store. Empty `{}` means no image. |
| `_viv_mode` (str, new) | Py → JS | `"viv"` or `"canvas2d-fallback"`, set by Python after `set_image()` inspects the input. |
| `_pixel_info` (dict, new) | JS → Py | `{x, y, intensities: [...]}` emitted on mousemove; surfaces the v0.4.0 "pixel info on hover" feature. |
| `channel_settings[i].gamma` (new field) | Py ↔ JS | Per-channel gamma; shader uniform on Viv, LUT approximation on Canvas2D. |
| `current_t`, `current_z`, `current_c` | Py ↔ JS | Existing. Drive Viv's image-layer selection. |
| `channel_settings` | Py ↔ JS | Existing. Each entry maps to a Viv channel slot. |
| `image_brightness`, `image_contrast` | Py → JS | Existing. Shader uniforms on Viv, CSS filter on Canvas2D. |
| `_histogram_request`, `_histogram_data` | Py ↔ JS | Existing round-trip — Python computes histograms. Reused unchanged on both backends. |
| `plate_wells`, `plate_fovs`, `current_well`, `current_fov` | Py ↔ JS | Existing. FOV change triggers `_zarr_source` update. |

### Zarr image load flow

```
Notebook:     viewer.set_image("s3://.../my.ome.zarr")
                     │
                     ▼
Python side:  ImageLoadingMixin.set_image
              ├─ Detect zarr URL (string + matches ome-zarr pattern)
              ├─ Fetch OME-Zarr metadata once (.zattrs, multiscales, omero/channels)
              │    → populates dim_t, dim_c, dim_z, resolution_levels, channel_settings
              ├─ Set self._zarr_source = {"url": "...", "headers": {}}
              └─ NO tile precompute, NO composite cache, NO PNG encoding
                     │ (anywidget sync)
                     ▼
JS side:      VivCanvas receives _zarr_source change
              ├─ zarrita.js opens the store directly from the browser
              ├─ Resolve multiscales dataset → ZarrPixelSource per pyramid level
              ├─ Mount <VivViewer/> with pixel source and initial channel props
              └─ Viv owns: tile fetch, tile cache, shader compile, WebGL2 render,
                 pan/zoom, pyramid-level auto-selection
```

Python's ongoing role is drastically smaller than on Canvas2D: fetch metadata once, maintain state traitlets, answer histogram requests. No chunk fetching, compositing, PNG encoding, or tile-cache management.

### Channel slider flow

```
User drags min slider for channel 2
  → JS updates channel_settings[2].min locally, debounced model.set
  → Python traitlet update (no-op for rendering)
  → Sync back to JS
  → <VivViewer/> prop change → shader uniform update → next frame
  (Viv's tile cache holds; no chunk re-fetch)
```

### HCS plate switch

```
User picks new well/FOV
  → PlateLoadingMixin updates _zarr_source with the new subpath
  → Viv reopens the store at the new subpath
```

Plate-side Python logic unchanged. Only the final hand-off to the renderer differs.

### Auto-fallback

`_viv_mode` starts as `"viv"`. If `set_image()` receives a non-zarr input (numpy array, bioio-TIFF, etc.), Python sets `_viv_mode = "canvas2d-fallback"` and runs the normal Canvas2D path. The Viv bundle loads the Canvas2D rendering code as an internal fallback module so no extra bundle has to load — mode flips happen via a React state change. Bundle-size cost of bundling Canvas2D as fallback is ~40 KB (Canvas2D is tiny).

---

## 4. Scope for v0.7.0-alpha

### In

- Local OME-Zarr (filesystem path, `file://`).
- Remote OME-Zarr over HTTP/HTTPS.
- Public S3 OME-Zarr (anonymous HTTPS).
- HCS OME-Zarr plates with well + FOV dropdowns driving `_zarr_source` subpath.
- Zarr v2 and v3 (both supported by zarrita.js).
- Multi-channel composites up to 6 channels (Viv default shader slot count).
- Per-channel: color, visibility, min/max, gamma (all shader uniforms on Viv).
- Global `image_brightness` / `image_contrast` as shader uniforms.
- 16-bit direct upload (uint16 zarr → WebGL2 texture, no quantization).
- Additive channel blending (Viv default).
- Auto-pyramid level based on zoom.
- Pan / zoom with deck.gl inertia.
- Pixel-intensity picker on hover (`_pixel_info` traitlet).
- Existing HTML/CSS channel panel re-used.
- T / Z / C sliders.
- Auto-fallback to Canvas2D for non-zarr inputs.
- `pip install anybioimage` with pre-built bundle (no Node at install).
- Playwright smoke tests: initial render, channel toggle, min/max drag, T slider, plate FOV swap. Screenshots under `/tmp/anybioimage-screenshots/` per `CLAUDE.md`.

### Out — deferred to later Viv-backend releases

- Mask overlays → v0.7.1 (deck.gl `BitmapLayer`, reuses existing Python-side mask arrays).
- Annotations (rect / poly / point) → v0.7.2 (deck.gl `PolygonLayer` / `ScatterplotLayer` / `PathLayer`).
- SAM integration on Viv → v0.7.2 (needs annotations wired up first).
- MIP / mean / sum projection render modes → v0.7.3.
- Measurement tools, annotation editing, undo/redo → v0.8.0 (Canvas2D first in v0.5.0, port after).
- Orthogonal XY / XZ / YZ views → v0.8.x.
- True volume raycasting (Viv's `VolumeLayer`) → v1.0.
- In-memory zarr bridge for local TIFF/CZI/ND2 → v0.7.x or v0.8.0.
- Private-bucket auth (AWS credentials, Azure Blob, GCS, HTTP basic) → v0.7.x.
- OMERO data source → separate sub-project (v0.9.0).
- Retirement of the Canvas2D backend → deferred beyond v1.0 until Viv has parity and two release cycles of usage.

---

## 5. Acceptance criteria — functional, not numeric

User explicitly chose a pragmatic bar over a formal benchmark harness: *"it should just work as expected… the previous version just acted strange with zarr's."* Release gate:

- Local and remote OME-Zarr render without error on the Viv backend.
- HCS plate well/FOV switching works.
- Auto-fallback to Canvas2D on non-zarr input is silent and logs one line.
- All existing traitlet-driven API calls produce the expected visual changes (`viewer.current_t = 5`, channel toggle, min/max set, plate switch, etc.).
- `pip install anybioimage` on a fresh machine without Node → Viv backend loads and renders.
- Playwright smoke tests pass.
- Subjective: T/Z scrubbing feels responsive; no flicker, stuck loaders, or blank frames on tile boundaries; channel drag is clearly snappier than Canvas2D.
- Canvas2D path (non-zarr inputs, users staying on `render_backend="canvas2d"`) is no slower than today.

Quantified benchmarks become a follow-up only if regressions or user complaints surface.

---

## 6. Risks, open questions, incremental path

### Risks (mitigations built into the design)

- **Viv multichannel shader caps at 6 channels.** Clamp visible channels to 6; show a UI indicator when an image has more; revisit in v0.7.x based on real usage.
- **Zarr v3 + sharding edge cases.** Catch zarrita errors, fall back to Canvas2D, log for field reports.
- **CORS on self-hosted remote zarr.** Detect CORS errors, show a clear message, fall back to Canvas2D. Document CORS requirements in the usage docs.
- **Bundle size creep.** `size-limit` CI guardrail at ~3 MB gzip.
- **Viv major-version breakage.** Pin exact Viv version in `package.json`; upgrade deliberately with smoke tests.
- **JupyterHub websocket latency.** Local JS updates + debounced `model.set` keep sliders feeling instant regardless of network.
- **Non-zarr inputs that look like zarr URLs.** Tolerant detection: verify `.zattrs` / `.zgroup` exists before committing to the Viv path; otherwise fall back.

### Open questions (resolved during implementation; do not block the design)

- Viv built-in multichannel shader vs a custom shader for gamma-in-pass.
- Pyramid-level selection: trust Viv's auto-pick or override with our current logic.
- Checked-in `viv-bundle.js` vs CI-built-only (default: check in plus CI consistency gate).
- Tolerant parser for non-standard OME `omero` channel blocks.

### Incremental path to Canvas2D feature parity

| Release | Adds on Viv backend |
|---|---|
| v0.7.0-alpha | Core zarr rendering + HCS plates (this design) |
| v0.7.1 | Read-only mask overlays |
| v0.7.2 | Annotations + SAM |
| v0.7.3 | MIP / projections |
| v0.8.0 | Measurement, annotation editing, undo/redo (Canvas2D first, port) |
| v0.8.x | Orthogonal views |
| v0.9.0 | OMERO data source (its own spec + plan cycle) |
| v1.0 | Volume raycasting |

Users keep `render_backend="canvas2d"` as the full-feature fallback throughout. No workflow regresses.

---

## 7. Decisions locked in (brainstorming-skill notes)

For the writing-plans skill pass that follows this spec:

1. **Coexistence, not replacement.** Both backends ship; users opt in.
2. **Build fresh on top of `@hms-dbmi/viv`.** Do not fork vizarr. Keep the Python API identical.
3. **v0.7.0-alpha scope = OME-Zarr + HCS plates only.** Mask overlays, annotations, SAM, projections come in v0.7.1–v0.7.3.
4. **Auto-fallback for non-zarr inputs.** `render_backend="viv"` is a preference, not a hard switch.
5. **Hybrid build pipeline.** Canvas2D stays inline; Viv gets its own `frontend/viv/` bundled directory.
6. **Reuse the existing channel panel.** Don't rebuild it in React.
7. **Python traitlets as source of truth.** JS mirrors and emits events back.
8. **Python-side histograms** (reuse existing code). Browser-side zarrita histogram can come later.
9. **Functional + subjective acceptance.** No formal benchmark harness for alpha.
10. **MIT attribution** for Viv, zarrita.js, and deck.gl in `README.md`.

## 8. Files anticipated to change (for the implementation plan)

Read-only reference — the implementation plan produced by writing-plans will own the exact file list.

- `anybioimage/viewer.py` — add `render_backend` and `_zarr_source` traitlets, swap `_esm` source based on backend, detect zarr vs non-zarr in `set_image()`.
- `anybioimage/backends/` — new directory; `canvas2d.py` extracts the current inline ESM string, `viv.py` loads the bundled JS asset.
- `anybioimage/frontend/viv/` — new directory; `package.json`, `build.config.js`, `src/*`, bundled `dist/viv-bundle.js`.
- `anybioimage/mixins/image_loading.py` — tolerant zarr-URL detection; metadata-only path that populates traitlets without starting the tile precompute.
- `anybioimage/mixins/plate_loading.py` — minor: update `_zarr_source` on FOV change instead of calling `set_image()` when the Viv backend is active.
- `pyproject.toml` — add `hatch-jupyter-builder` build hook and bundle artifact declaration.
- `README.md` — add MIT attribution for Viv, zarrita.js, deck.gl.
- CI workflow — add `setup-node@v4` step before wheel build; add bundle-size check.
- Playwright smoke tests under existing test directory.
