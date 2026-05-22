# Roadmap

Planned features and improvements for anybioimage, organized by milestone.

## Delivered

| Release | Description |
|---|---|
| v0.7.0 | **Unified pipeline + channel LUTs + scale bar + metadata panel + pixel-info hover** — single WebGL2 rendering path (Viv + deck.gl) for every input format: remote OME-Zarr, local OME-Zarr, numpy, bioio TIFF/CZI/ND2. 15-LUT registry, per-channel gamma, scale bar, pixel-info hover, metadata panel. |

Previously planned in v0.4.0 (colormap/LUT, scale bar, pixel info) are delivered in v0.7.0.

---

## Phase 2 — Overlays

| Release | Description |
|---|---|
| v0.7.1 | Read-only mask overlays on the unified pipeline |
| v0.7.2 | Annotations + SAM on the unified pipeline |

---

## Phase 3 — Measurement & Editing

Merges v0.7.3 (projections, deferred) + v0.5.0 items:

- **MIP / projections** — Maximum intensity projection and orthogonal views.
- **Measurement tools** — Distance (line), area (polygon), and intensity line profile tools with results displayed in the UI.
- **Image metadata panel** — Display file info, dimensions, pixel size, and acquisition metadata in a sidebar panel.
- **Undo/redo for annotations** — Maintain an undo stack for annotation creation, deletion, and modification.
- **Annotation editing** — Modify existing annotations: move vertices, resize rectangles, reposition points (via `nebula.gl`).
- **Export annotations UI** — Built-in buttons to export annotations as CSV or JSON files directly from the widget.

---

## v0.8.x — Extended Sources

| Release | Description |
|---|---|
| v0.8.0 | Measurement, annotation editing, undo/redo |
| v0.8.x | Orthogonal views |
| v0.9.0 | OMERO data source (its own spec + plan cycle) |

---

## v1.0 — Stability & Ecosystem

- **Touch / mobile support** — Touch event handlers for tablets: pinch-to-zoom, drag-to-pan, long-press context actions.
- **ARIA accessibility** — Proper ARIA labels, roles, and keyboard navigation for all interactive controls (toolbar buttons, sliders, panels).
- **Volume raycasting** — Full 3D volume visualization beyond Z-slice navigation.
- **CSS custom properties** — Refactor hardcoded colors to CSS variables for theming and dark mode improvements.
- **Plugin architecture** — Allow dynamic feature registration beyond static mixins, enabling third-party extensions.
- **Multi-view / linked views** — Side-by-side synchronized panels for comparing channels, timepoints, or different images.

---

## Contributing

Want to help with any of these features? See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and architecture details. Feature discussions and proposals are welcome via [GitHub Issues](https://github.com/maartenpaul/anybioimage/issues).
