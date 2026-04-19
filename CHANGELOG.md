# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
