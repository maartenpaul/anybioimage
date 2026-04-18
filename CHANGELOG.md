# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- Added bundle freshness + `size-limit` CI guards (4 MB gzip cap).

### Known limitations in v0.7.0-alpha
- No channel panel UI on the Viv path yet (min/max/contrast sliders land in v0.7.1).
- T slider may not always trigger a full re-render in edge cases; being investigated.
- Mask overlays, annotations, SAM deferred to v0.7.1–v0.7.2.

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
