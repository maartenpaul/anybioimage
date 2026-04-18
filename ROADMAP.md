# Roadmap

Planned features and improvements for anybioimage, organized by milestone.

## Viv backend (WebGL2 rendering for OME-Zarr)

### Delivered

| Release | Description |
|---|---|
| v0.7.0-alpha | Core zarr rendering + HCS plates (**delivered**) |

### Planned

| Release | Adds on Viv backend |
|---|---|
| v0.7.1 | Read-only mask overlays |
| v0.7.2 | Annotations + SAM |
| v0.7.3 | MIP / projections |
| v0.8.0 | Measurement, annotation editing, undo/redo (Canvas2D first, port) |
| v0.8.x | Orthogonal views |
| v0.9.0 | OMERO data source (its own spec + plan cycle) |
| v1.0 | Volume raycasting |

---

## v0.4.0 — Display Enhancements

- **Colormap / LUT support** — Standard scientific colormaps (viridis, plasma, magma, inferno, etc.) in addition to basic channel colors. Allow users to select colormaps per channel.
- **Scale bar display** — Render a physical scale bar on the canvas using pixel size metadata from BioImage objects.
- **Pixel info on hover** — Show coordinates (x, y) and intensity values under the cursor in a status bar.

## v0.5.0 — Measurement & Annotation Improvements

- **Measurement tools** — Distance (line), area (polygon), and intensity line profile tools with results displayed in the UI.
- **Image metadata panel** — Display file info, dimensions, pixel size, and acquisition metadata in a sidebar panel.
- **Undo/redo for annotations** — Maintain an undo stack for annotation creation, deletion, and modification.
- **Annotation editing** — Modify existing annotations: move vertices, resize rectangles, reposition points.
- **Export annotations UI** — Built-in buttons to export annotations as CSV or JSON files directly from the widget.

## v1.0 — Stability & Ecosystem

- **Touch / mobile support** — Touch event handlers for tablets: pinch-to-zoom, drag-to-pan, long-press context actions.
- **ARIA accessibility** — Proper ARIA labels, roles, and keyboard navigation for all interactive controls (toolbar buttons, sliders, panels).
- **3D volume rendering** — Basic volume visualization beyond Z-slice navigation (maximum intensity projection, orthogonal views).
- **CSS custom properties** — Refactor hardcoded colors to CSS variables for theming and dark mode improvements.
- **Plugin architecture** — Allow dynamic feature registration beyond static mixins, enabling third-party extensions.
- **Multi-view / linked views** — Side-by-side synchronized panels for comparing channels, timepoints, or different images.

## Contributing

Want to help with any of these features? See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and architecture details. Feature discussions and proposals are welcome via [GitHub Issues](https://github.com/maartenpaul/anybioimage/issues).
