# Zarr chunk bridge for the Viv backend — design

**Date:** 2026-09-02
**Branch:** `feature/viv-reader` (PR #9)
**Status:** approved design, pending implementation plan

## Goal

Make `BioImageViewer(render_backend="viv")` a capable OME-Zarr viewer for
*large* stores that the browser cannot fetch directly: local paths, network
mounts, and `s3://` / `gs://` buckets readable with the kernel's credentials.
Today those inputs fall back to the Canvas2D lazy path, which composites
full-resolution planes per tile and is unusable above ~2 GB.

The kernel serves per-level tiles to Viv over the anywidget message channel
(the "chunk bridge"). Viv keeps doing pyramid selection, tiling, and GPU
compositing. Python never loads a full plane, never composites, never encodes
PNG.

## Non-goals (explicitly out of scope)

- `http(s)` CORS/auth failure fallback from browser-direct to the bridge.
- Zarr v3 / NGFF 0.5 for the **browser-direct** path (needs a Viv upgrade off
  zarr.js 0.6). The bridge path supports v3 via zarr-python.
- Annotations, masks, SAM, brightness/contrast, histogram on Viv-rendered images.
- Canvas2D lazy-path improvements (region reads, range sampling).
- Synthetic pyramids for single-level stores.

## Maintainability requirements

- **Spec changes** touch one module: `anybioimage/ngff.py`. Fixtures per NGFF
  version live in `tests/test_ngff.py`.
- **Viv upgrades** touch `package.json` + rebuild. Viv API usage stays confined
  to `zarr-source.js`, `buildImageLayer.js`, `VivCanvas.jsx`. The bridge
  implements Viv's `PixelSource` contract (`getTile`, `getRaster`, `shape`,
  `dtype`, `labels`, `tileSize`), stable since Viv 0.14.
- No strict-validation metadata library. `ome-zarr-models` rejects
  `examples/image.zarr` (empty `coordinateTransformations`); real-world
  writers are sloppy, a viewer must be lenient. `ngff-zarr` is lenient but
  pulls itkwasm/dask/rich. Store handling is delegated to `zarr-python>=3`
  (v2 + v3, local + fsspec).

## Architecture

```
set_image(x)  (viv backend)
 ├─ http(s) *.zarr URL           → _set_zarr_url()        → _zarr_source={mode:"url", url, headers}
 │                                                            (unchanged, browser-direct via loadOmeZarr)
 ├─ local path / s3:// / gs:// *.zarr, or zarr.Group
 │     → ngff.open_image(x)      → NgffImage
 │     → ZarrBridgeMixin._attach_bridge(img)
 │                                → _zarr_source={mode:"bridge", levels:[{shape,chunks}], labels, dtype}
 │       JS: one AnywidgetPixelSource per level → MultiscaleImageLayer
 │       JS→Py  model.send {kind:"chunk", requestId, level, t, c, z, tx, ty, tileSize}
 │       Py→JS  {kind:"chunk", requestId, ok, w, h} + buffers=[raw bytes]
 └─ numpy / BioImage / non-zarr  → Canvas2D pipeline (unchanged)
```

- Canvas2D backend (`render_backend="canvas2d"`, the default) is untouched.
  Local zarr on Canvas2D still goes through bioio as on `main`.
- `set_plate()` on the viv backend uses the bridge per FOV for non-http plates,
  mirroring the existing http plate path that swaps the `_zarr_source` subpath.
- Pyramid = the store's native multiscale levels. A single-level store still
  works: Viv tiles a single level.

### Chunk-aware cache (key performance rule)

`examples/image.zarr` has chunks `(10, 16, 512, 512)`. zarr-python decodes
whole chunks, so a 512² tile read costs the same as reading every T×Z inside
that chunk (measured: 445 ms vs 453 ms). The bridge therefore:

1. On a tile miss, computes the enclosing chunk block: the tile's y/x extent
   plus the full chunk span along every non-spatial axis.
2. Reads that block once, converts to native little-endian C-contiguous bytes,
   and inserts one cache entry per `(level, t, c, z, ty, tx)` it covers.
3. Serves the requested tile and every sibling from the cache.

Cache is a byte-budgeted LRU (default 256 MB, `viewer.bridge_cache_bytes`).
Cleared on new image and on plate FOV change.

**Measured (2026-09-02, `examples/image.zarr`, 10T x 3Z x 2048² `>u2`, levels
s0/s1/s2, chunks `(10, 16, 512, 512)`).** Kernel-side, driving
`_handle_custom_msg` directly with `{"kind":"chunk", ...}` requests and timing
until the reply is produced:

| request | time |
| --- | --- |
| level 2, t=0 z=0, tile (0,0) — cold | 452 ms |
| level 2, t=1 z=0, same tile — sibling in the same chunk block | 1.2 ms |
| level 2, t=0 z=1, same tile — sibling in the same chunk block | 1.1 ms |
| level 0, t=0 z=0, tile (0,0) — cold | 470 ms |
| level 0, t=1 z=0, same tile — sibling | 1.2 ms |

Two cold block reads populated 60 cache entries / 30 MB, i.e. one 452 ms read
buys 30 sibling tiles at ~1 ms each — the chunk-aware rule holds. Replies carry
512x512 uint16 = 524288 raw bytes and decode to sane pixel values
(level 0 tile (0,0): min 85, max 129, mean 102.3).

**Browser status: not yet rendering under marimo (blocked).** In headless
chromium against `examples/viv_local_zarr_demo.py` the Viv canvas mounts
correctly (Canvas2D hidden, WebGL2 context live, `MultiscaleImageLayer` built
with `selections=[{c:0,t:0,z:0}]`, `contrastLimits=[[77,299]]`, viewState
centred on 2048²) and the frontend does issue chunk requests — but every tile
stays unloaded and the canvas is blank. Root cause is on the marimo host side,
not in the bridge logic: `_serve_chunk` runs on a `zarr-bridge` worker thread,
and marimo's runtime context is a `threading.local`
(`marimo._runtime.context.types._THREAD_LOCAL_CONTEXT`), so
`MarimoComm._broadcast` -> `broadcast_notification` hits
`ContextNotInitializedError`, logs `No context initialized.` at DEBUG and drops
the reply. Kernel debug log shows the pairing directly: `Handling message for
comm <id>` (request received) then `Sending comm message <id>` immediately
followed by `No context initialized.` for each tile. The fix belongs in the
bridge: reply from the kernel thread (or copy the marimo runtime context into
the worker threads).

## Python components

### `anybioimage/ngff.py` (new, no widget dependencies)

```python
@dataclass
class NgffImage:
    group: zarr.Group
    version: str                 # "0.4", "0.5", ... or "unknown"
    axes: list[str]              # e.g. ["t","c","z","y","x"]; lenient default
    levels: list[zarr.Array]     # multiscales[0].datasets in order, level 0 first
    dtype: np.dtype              # level-0 dtype, native byte order
    omero_channels: list[dict]   # raw omero.channels entries, [] if absent

def open_group(src, storage_options=None) -> zarr.Group
def read_ome_attrs(group) -> tuple[str, dict]      # (version, attrs) — v0.4 top-level or v0.5+ attrs["ome"]
def open_image(src, storage_options=None) -> NgffImage
def is_plate(group) -> bool
def plate_layout(group) -> dict                     # rows, columns, wells[{path}], used by set_plate
```

- `open_group` accepts `str`/`Path`/`zarr.Group`; scheme-less strings are
  local paths. `s3://`/`gs://` go through zarr's fsspec store; a missing
  `s3fs`/`gcsfs` surfaces as `ImportError("pip install anybioimage[remote]")`.
- Leniency rules: missing `axes` → trailing `["t","c","z","y","x"][-ndim:]`;
  missing/empty `coordinateTransformations` ignored; datasets whose path is
  not an array are skipped with a warning; no `multiscales` → `ValueError`.
- `_fetch_zarr_ome_metadata` and `_zarr_url_is_plate` (urllib, v2-only) are
  deleted. The http URL probe in `_set_zarr_url` calls
  `open_group(url, headers)` + `read_ome_attrs`, one code path for all stores.
  `_channel_settings_from_omero` stays and is fed from `NgffImage`.

### `anybioimage/mixins/zarr_bridge.py` (new) — `ZarrBridgeMixin`

- `_attach_bridge(img: NgffImage)`: cancels Canvas2D precompute, clears
  `_bioimage`/`_full_array`, sets `dim_*`/`height`/`width`/`_channel_settings`
  (omero if present, else default colors + dtype range) under
  `hold_trait_notifications`, resets `_render_ready`, then sets
  `_zarr_source = {"mode": "bridge", "levels": [{"shape": [...], "chunks": [...]}, ...],
  "labels": axes, "dtype": "uint16"}`.
- `_on_bridge_msg(content, buffers)`: registered via `self.on_msg`; ignores
  anything without `kind == "chunk"`. Submits to a 4-worker
  `ThreadPoolExecutor`; reply via `self.send(meta, buffers=[bytes])`. Any
  exception → `{kind:"chunk", requestId, ok: False, error: str(e)}`.
- `_read_tile(level, t, c, z, tx, ty, size) -> (w, h, bytes)`: cache lookup,
  else chunk-block read + fill as above. Selection uses `img.axes` so stores
  without `t`/`c`/`z` index only the axes they have.
- `_BridgeCache`: `OrderedDict` keyed `(level,t,c,z,ty,tx)` → `bytes`;
  evicts oldest until under budget; `clear()`.
- Supported dtypes: uint8/uint16/uint32/float32 (Viv's set). Others are cast
  to float32 with a warning.

### Dispatch changes

`image_loading.set_image(data, headers=None, storage_options=None)`:

1. `http(s)` string ending `.zarr`/`.ome.zarr` → existing url path (viv) or
   bioio (canvas2d).
2. `zarr.Group`, or `str`/`Path` ending `.zarr`/`.ome.zarr` (local, `s3://`,
   `gs://`) → viv: `_attach_bridge(open_image(...))`, falling back to bioio on
   any exception with one `INFO` log (existing convention); canvas2d: bioio
   as today.
3. Plate detected via `is_plate` in cases 1–2 → `ValueError` pointing to
   `set_plate` (existing message).
4. Else → existing numpy / BioImage dispatch.

`plate_loading._load_plate_image`: viv branch now covers any plate the bridge
can open (not only http); http plates keep browser-direct.

### Dependencies

- `zarr>=3.0` into core dependencies (already transitively present via
  `bioio-ome-zarr`).
- New optional extra `remote = ["s3fs", "gcsfs"]`; included in `all`.

## JS components (`anybioimage/frontend/viewer/src/`)

1. `render/pixel-sources/anywidget-source.js` + `anywidget-source.test.js`:
   ported from the `feature/viv-backend` worktree (LRU cap 512, in-flight
   dedup, `setTimeout(0)` batching, abort handling). `labels` are passed in
   from `_zarr_source.labels`; `level` is per instance.
2. `render/pixel-sources/bridge-source.js` (new): `openBridge(model, zarrSource)`
   → `AnywidgetPixelSource[]`, one per level, sharing one `msg:custom`
   listener registration per source (as ported). `tileSize` = the yx chunk
   size when square and a power of two in `[256, 1024]`, else 512.
   `dtype` mapped via `AnywidgetPixelSource.dtypeFromPython`.
3. `VivCanvas.jsx`: the source effect branches on `zarrSource.mode`
   (`"url"` → `openOmeZarr`, `"bridge"` → `openBridge`); cleanup calls
   `destroy()` on bridge sources. Downstream (`buildImageLayerProps`,
   `MultiscaleImageLayer`, view state, `_render_ready`) unchanged.
4. `entry.js`: `syncMode` keys on `_zarr_source.mode` being set instead of
   `.url`.
5. `canvas2d-chrome.js`: its two inert guards key on `_zarr_source.url`;
   change to `mode` so Canvas2D `renderCanvas()`/`requestTiles()` stand down
   in bridge mode too.
6. Rebuild `dist/viewer-bundle.js`; `size-limit` and `bundle.yml` freshness
   gates unchanged.

## Error handling

| Situation | Behaviour |
|---|---|
| Store open / metadata parse fails (viv) | `logger.info`, fall back to Canvas2D via bioio |
| Plate passed to `set_image` | `ValueError` → use `set_plate` |
| `s3://`/`gs://` without fsspec backend | `ImportError` with `anybioimage[remote]` hint |
| Single chunk read fails | `{ok:false,error}` → tile rejected; Viv `onTileError` logs; other tiles render |
| Widget disposed / new image mid-flight | `destroy()` rejects pending; cache cleared; late replies ignored |

## Testing

- `tests/test_ngff.py`: tmp fixtures — v0.4 zarr-v2 big-endian, no `c` axis,
  empty transforms (mirrors `examples/image.zarr`); v0.5 zarr-v3 with `ome`
  key, full TCZYX, omero; v0.4 plate. Assert version, axes, levels, dtype,
  omero, `is_plate`, `plate_layout`.
- `tests/test_zarr_bridge.py`: `send` mocked; tile bytes length/dtype/
  endianness; chunk-block prefill (sibling `(t,z)` tile = cache hit, zarr not
  re-read); byte-budget eviction; error reply; `set_image(path)` on viv sets
  `mode:"bridge"` and on canvas2d leaves `_zarr_source` empty; plate FOV
  switch updates `_zarr_source`; store without `t`/`z` axes.
- `tests/test_zarr_metadata.py` rewritten onto `ngff.py` (same assertions).
- Full existing suite stays green — Canvas2D no-regression gate.
- vitest: ported `anywidget-source.test.js`; `bridge-source.test.js` for the
  `tileSize` rule and per-level construction.
- Browser (playwright, per CLAUDE.md): `examples/image.zarr` on viv —
  first tile ≈450 ms, sibling T/Z tiles from cache, console clean.
