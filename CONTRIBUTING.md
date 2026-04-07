# Contributing to anybioimage

Thank you for your interest in contributing to anybioimage!

## Development Setup

```bash
# Clone the repository
git clone https://github.com/maartenpaul/anybioimage.git
cd anybioimage

# Install with development dependencies
uv pip install -e ".[all]"
```

## Running Tests

```bash
uv run pytest tests/ -v
```

## Code Style

This project uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
uv run ruff check anybioimage/       # lint
uv run ruff check --fix anybioimage/  # auto-fix
```

## Architecture

### Mixin Pattern

BioImageViewer is composed of several mixins, each providing a specific capability:

```
BioImageViewer(
    ImageLoadingMixin,       # Image loading, caching, tile-based rendering
    PlateLoadingMixin,       # HCS OME-Zarr plate navigation
    MaskManagementMixin,     # Mask overlay layer management
    AnnotationsMixin,        # Annotation tools (rectangles, polygons, points)
    SAMIntegrationMixin,     # Segment Anything Model integration
    anywidget.AnyWidget,     # Base widget class (must be last)
)
```

**Mixin order matters.** `ImageLoadingMixin` must be first because other mixins depend on methods it provides (e.g., `_set_bioimage`). `anywidget.AnyWidget` must be last per Python MRO rules.

Each mixin documents the attributes it expects from the main class in its docstring. When adding a new mixin:

1. Create a new file in `anybioimage/mixins/`
2. Document expected attributes in the class docstring
3. Add the mixin to `anybioimage/mixins/__init__.py`
4. Add it to the `BioImageViewer` class definition in `viewer.py`

### Frontend (JavaScript/CSS)

The widget frontend is embedded in `viewer.py` as `_esm` (JavaScript) and `_css` (CSS) class attributes, following the [anywidget](https://anywidget.dev) pattern. The JavaScript `render()` function receives a `model` object for bidirectional communication with Python via traitlets.

### Traitlet Communication

All Python-JS communication uses traitlets tagged with `.tag(sync=True)`. Key patterns:

- **Python → JS**: Set a traitlet value, JS listens with `model.on('change:name', callback)`
- **JS → Python**: JS calls `model.set('name', value); model.save_changes()`, Python observes with `self.observe(callback, names=['name'])`

## Submitting Changes

1. Fork the repository and create a feature branch
2. Make your changes with clear commit messages
3. Ensure tests pass and ruff is clean
4. Submit a pull request with a description of your changes
