# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-11-22

### Added
- Masks can follow the T/Z sliders: `add_mask` accepts a (T, Y, X), (Z, Y, X) or (T, Z, Y, X)
  label stack (or TCZYX with one channel) and shows the frame for the current position.
  `dims="TYX"` / `"ZYX"` resolves images with as many time points as z-planes.
- Opt-in `render_backend="viv"`: remote OME-Zarr rendered via WebGL2 with
  browser-direct chunk fetch (no Python tile round-trips). Main UI unchanged.
- `set_image(url, headers=...)` accepts URL-schemed `.zarr`/`.ome.zarr` strings
  on both backends (Canvas2D routes them through bioio).
- HCS plates on the viv backend: FOV switching swaps the zarr subpath browser-side.
- Viv backend: kernel chunk bridge renders local / `s3://` / `gs://` OME-Zarr stores and `zarr.Group` inputs of any size (zarr v2 + v3, NGFF v0.4/v0.5); chunk-aware tile cache (`bridge_cache_bytes`).
- New `anybioimage.ngff` module: lenient OME-NGFF metadata reader used by every zarr path (replaces the urllib-only probe).
- `set_image(..., storage_options=)` / `set_plate(..., storage_options=)` for fsspec credentials; new `remote` extra (s3fs, gcsfs).

### Changed
- `add_mask` raises `ValueError` for a label stack that does not fit the image's T/Z sizes;
  before, it silently showed the first frame on every plane.
- Canvas2D ESM extracted verbatim to `anybioimage/frontend/viewer/src/canvas2d-chrome.js`
  (served raw — behavior identical; no Node needed for the default backend).
- zarr support is an optional extra: `pip install "anybioimage[zarr]"` (`zarr>=3.1`,
  `bioio>=3.0`, `bioio-ome-zarr>=3.0`). The base install no longer pulls zarr, dask or xarray.
  Loading a zarr store without the extra raises an ImportError naming the install command.
  Browser-direct `http(s)` URLs on the viv backend need no extra.
- `requires-python` is now `>=3.11`.
- Dependency floors raised to tested versions: `numpy>=1.26`, `pandas>=1.5`, `pillow>=9.2`,
  `bioio>=3.0` in the `bioio` extra.
- An unreachable zarr host now raises `ConnectionError` naming the URL instead of a
  bioio "unsupported file format" traceback.
- Example notebooks point at the new IDR host (`livingobjects.ebi.ac.uk`).

### Fixed
- T/Z sliders now update the picture on images under 1 megapixel; before, the status text
  moved but the canvas stayed on the old plane.

### Performance
- Canvas2D tiles: one tile request in flight at a time, visible plane before prefetch, and a
  faster base64 decode. Measured in marimo on a 2048x2048 OME-Zarr: first visit to a plane
  2.0 s median instead of 2.9 s (worst 2.3 s instead of 4.2 s), longest page freeze 0.66 s
  instead of 1.6 s. Tiles requested before a channel colour/contrast change are discarded,
  so no tile in the old colour can stay on screen.

### Build
- `anybioimage/frontend/viewer/` esbuild bundle for the viv backend; pre-built
  bundle committed and shipped in the wheel (no Node at install time).
- CI: bundle freshness + size gates (`.github/workflows/bundle.yml`).

## [0.3.1] - 2026-05-22

### Fixed
- Unified rendering pipeline to fix contrast and auto-contrast bugs
- SAM mask size mismatch: resize predicted mask to image dimensions before adding overlay

### Changed
- Updated documentation and README with improved examples and images

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
