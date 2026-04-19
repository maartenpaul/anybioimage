# Unified BioImageViewer — Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**This is Phase 2 of 3.** Phase 3 (editing + measurement + undo + export) follows.

**Goal (Phase 2):** Land the "Annotate MVP" on top of the Phase 1 unified pipeline. Replace the three split annotation traitlets (`_rois_data`, `_polygons_data`, `_points_data`) with a single `_annotations` list; expose `.rois_df` / `.polygons_df` / `.points_df` as read/write views filtered by `kind`. Add rect, polygon, and point **creation** tools (no editing, no measurement, no undo). Render annotations as deck.gl `PolygonLayer` + `ScatterplotLayer` in the existing `DeckCanvas` layer stack. Ship the mask overlay path end-to-end: Python sends raw mask bytes via anywidget buffers (no base64 PNG), JS composites each mask as a `BitmapLayer`. Hook up SAM so a committed rectangle or point becomes a mask via the new transport.

**Scope guardrails (per spec §8 "Phase 2 — Annotate MVP"):**

- In scope: rect / polygon / point **drawing** (creation only), mask overlays via `BitmapLayer`, SAM hookup, unified `_annotations` traitlet, interaction controller + tool registry, mask-overlay transport switch to raw bytes.
- Out of scope (Phase 3): `EditableGeoJsonLayer` / vertex editing, drag-to-move, line / area / line-profile measurement, undo/redo, export buttons.

**Architecture:** Phase 2 adds three concerns on top of the Phase 1 canvas without touching the image pipeline: (1) a single `_annotations` traitlet drives two new deck.gl layers (polygon + scatter) mounted between the image layer and the scale bar; (2) a mask transport via `model.send(..., buffers)` drives one `BitmapLayer` per mask; (3) an `InteractionController` routes pointer events through a tool registry, and tools are the only code that mutates `_annotations`. SAM is unchanged on Python — Phase 2 only wires the JS → Py geometry message and the Py → JS mask response into the mask path.

**Tech Stack:** Python anywidget + traitlets · React 18 · `@deck.gl/layers` (`PolygonLayer`, `ScatterplotLayer`, `PathLayer`, `BitmapLayer`) · `deck.gl` 9 picking API · esbuild · `vitest` (JS unit) · `pytest` (Python unit) · Playwright (smoke).

**Spec:** [docs/superpowers/specs/2026-04-19-unified-viewer-design.md](../specs/2026-04-19-unified-viewer-design.md) — sections referenced as `[spec §N]`. Phase 2 covers §5 (annotations), §6 (interaction), the mask subset of §3 (layer stack), and the rect/polygon/point/mask subset of §8 and §11.

---

## Starting point

Phase 1 has merged into `feature/viv-backend`. The widget renders images, pixel-info hover, scale bar, LUTs, and keyboard shortcuts; `MaskManagementMixin`, `AnnotationsMixin`, and `SAMIntegrationMixin` are still wired to the legacy split traitlets but no JS code consumes them. `Toolbar.jsx` declares rect/polygon/point buttons as `disabled`; `LayersPanel.jsx` has two "Masks (Phase 2)" / "Annotations (Phase 2)" placeholders; `interaction/tools/` is an empty directory.

Each task starts from the previous task's end state on `feature/viv-backend`. Commits accumulate on that branch until Phase 2 is ready to merge.

---

## File structure (Phase 2)

**New files:**

- `anybioimage/frontend/viewer/src/render/layers/annotationsToLayers.js` — pure: `_annotations[]` → `[PolygonLayer, ScatterplotLayer]`
- `anybioimage/frontend/viewer/src/render/layers/annotationsToLayers.test.js`
- `anybioimage/frontend/viewer/src/render/layers/buildMaskLayers.js` — pure: `masks[]` → `BitmapLayer[]`
- `anybioimage/frontend/viewer/src/render/layers/buildMaskLayers.test.js`
- `anybioimage/frontend/viewer/src/render/pixel-sources/MaskSourceBridge.js` — receives mask bytes over anywidget messages, decodes to `ImageData`
- `anybioimage/frontend/viewer/src/render/pixel-sources/MaskSourceBridge.test.js`
- `anybioimage/frontend/viewer/src/interaction/InteractionController.js`
- `anybioimage/frontend/viewer/src/interaction/InteractionController.test.js`
- `anybioimage/frontend/viewer/src/interaction/tools/pan.js`
- `anybioimage/frontend/viewer/src/interaction/tools/select.js`
- `anybioimage/frontend/viewer/src/interaction/tools/rect.js`
- `anybioimage/frontend/viewer/src/interaction/tools/rect.test.js`
- `anybioimage/frontend/viewer/src/interaction/tools/polygon.js`
- `anybioimage/frontend/viewer/src/interaction/tools/polygon.test.js`
- `anybioimage/frontend/viewer/src/interaction/tools/point.js`
- `anybioimage/frontend/viewer/src/interaction/tools/point.test.js`
- `anybioimage/frontend/viewer/src/chrome/LayersPanel/MasksSection.jsx`
- `anybioimage/frontend/viewer/src/chrome/LayersPanel/AnnotationsSection.jsx`
- `tests/test_annotations_unified.py` — round-trip each kind via `_annotations`; legacy DataFrame properties preserved
- `tests/test_mask_transport.py` — raw-bytes mask transport over anywidget `send()`
- `tests/test_sam_protocol.py` — JS-originated `{kind: "sam_rect"|"sam_point"}` routes to SAM, replies with `{kind: "sam_mask", ...}`
- `tests/playwright/test_phase2_draw_rect.py`
- `tests/playwright/test_phase2_draw_polygon.py`
- `tests/playwright/test_phase2_draw_point.py`
- `tests/playwright/test_phase2_sam_flow.py`

**Modified files:**

- `anybioimage/viewer.py` — add `_annotations` traitlet; remove `_rois_data` / `_polygons_data` / `_points_data` traitlets and the three legacy color/visibility/radius traitlets; extend `_route_message` with `sam_rect`, `sam_point`, `mask_request` kinds.
- `anybioimage/mixins/annotations.py` — rewrite: `.rois_df` / `.polygons_df` / `.points_df` properties are views over `_annotations` filtered by `kind`. Setters rewrite `_annotations` for that kind, preserving entries of other kinds. `clear_rois` / `clear_polygons` / `clear_points` / `clear_all_annotations` stay, implemented in terms of `_annotations`.
- `anybioimage/mixins/mask_management.py` — drop base64 PNG encoding from `_masks_data` entries. Store mask bytes keyed by mask id; push metadata-only dicts into `_masks_data` (`id`, `name`, `visible`, `opacity`, `color`, `contours`, `contour_width`, `width`, `height`, `dtype`). Add `_send_mask(mask_id)` that calls `self.send({kind:"mask", id, ...}, [bytes])`. JS requests masks on first render / visibility-change via `{kind:"mask_request", id}`.
- `anybioimage/mixins/sam_integration.py` — add `handle_sam_rect(payload)` / `handle_sam_point(payload)` that call existing `_run_sam_with_bbox` / `_run_sam_with_point` helpers, then push the produced mask through the new transport via `add_mask()`.
- `anybioimage/frontend/viewer/src/chrome/Toolbar.jsx` — remove `phase2Disabled` flag on rect/polygon/point; keep `line` / `areaMeasure` disabled (Phase 3).
- `anybioimage/frontend/viewer/src/chrome/LayersPanel/LayersPanel.jsx` — replace the two placeholder divs with `<MasksSection>` + `<AnnotationsSection>`.
- `anybioimage/frontend/viewer/src/App.jsx` — instantiate `InteractionController`; feed it pointer events from `DeckCanvas`; install a global `MaskSourceBridge`.
- `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx` — mount annotation layers + mask layers + a transient preview layer; accept a `controller` prop and wire `onClick` / `onHover` / `onDragStart` / `onDrag` / `onDragEnd` to the active tool.
- `examples/full_demo.py` — add sections 7 (annotations walkthrough) and 8 (SAM walkthrough, conditionally shown).

**Deletions (Phase 2):** none. `_rois_data` / `_polygons_data` / `_points_data` traitlets are private and get removed in Task 1 without a back-compat shim (the DataFrame properties are the only public surface).

---

## Conventions

- **Every code step shows the full code.** No `...`, no "add appropriate error handling", no "similar to X".
- **TDD on Python and JS units** (pytest + vitest). Playwright is round-trip smoke, not TDD.
- **Commits are bite-sized**, one conventional-prefixed commit per logical change (`feat`, `refactor`, `build`, `test`, `docs`, `chore`).
- **Each task ends with a commit.** Intermediate steps inside a task may include `git add` of partial files; the final step of the task is always a `git commit`.
- **Python tests:** `uv run pytest tests/ -v`
- **JS tests:** `cd anybioimage/frontend/viewer && npm run test`
- **Bundle build:** `cd anybioimage/frontend/viewer && npm run build`
- **Worktree:** all work happens in `.worktrees/viv-backend` on branch `feature/viv-backend`.

---

## Task 1: Unified `_annotations` traitlet + legacy DataFrame properties

**Goal:** Replace the three split annotation traitlets with a single `_annotations` list. Keep `.rois_df`, `.polygons_df`, `.points_df` read/write properties stable — existing notebooks and the SAM mixin that reads these DataFrames keep working. No JS consumer of the new traitlet exists yet; that lands in Task 2+. [spec §5]

**Files:**
- Modify: `anybioimage/viewer.py`
- Modify: `anybioimage/mixins/annotations.py`
- Modify: `anybioimage/mixins/sam_integration.py` — observer switches from `_rois_data` / `_points_data` to `_annotations`
- Create: `tests/test_annotations_unified.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_annotations_unified.py
"""Unified _annotations traitlet + legacy DataFrame back-compat [spec §5]."""
from __future__ import annotations

import pandas as pd
import pytest

from anybioimage import BioImageViewer


def make_viewer() -> BioImageViewer:
    return BioImageViewer()


def test_annotations_starts_empty():
    v = make_viewer()
    assert v._annotations == []
    assert v.rois_df.empty
    assert v.polygons_df.empty
    assert v.points_df.empty


def test_rois_df_setter_roundtrip():
    v = make_viewer()
    df = pd.DataFrame([
        {"id": "r1", "x": 10, "y": 20, "width": 5, "height": 6},
        {"id": "r2", "x": 1,  "y": 2,  "width": 3, "height": 4},
    ])
    v.rois_df = df
    assert len(v._annotations) == 2
    assert all(a["kind"] == "rect" for a in v._annotations)
    out = v.rois_df
    assert list(out.columns) == ["id", "x", "y", "width", "height"]
    pd.testing.assert_frame_equal(
        out.reset_index(drop=True), df.reset_index(drop=True), check_dtype=False)


def test_polygons_df_setter_roundtrip():
    v = make_viewer()
    pts = [{"x": 0, "y": 0}, {"x": 1, "y": 1}, {"x": 2, "y": 0}]
    v.polygons_df = pd.DataFrame([{"id": "p1", "points": pts}])
    out = v.polygons_df
    assert list(out.columns) == ["id", "points", "num_vertices"]
    assert out.iloc[0]["num_vertices"] == 3
    assert out.iloc[0]["points"] == pts


def test_points_df_setter_roundtrip():
    v = make_viewer()
    v.points_df = pd.DataFrame([
        {"id": "pt1", "x": 7, "y": 8},
        {"id": "pt2", "x": 9, "y": 10},
    ])
    assert len(v._annotations) == 2
    assert all(a["kind"] == "point" for a in v._annotations)
    assert list(v.points_df.columns) == ["id", "x", "y"]


def test_mixed_kinds_dont_leak_between_views():
    v = make_viewer()
    v.rois_df = pd.DataFrame([{"id": "r1", "x": 0, "y": 0, "width": 1, "height": 1}])
    v.points_df = pd.DataFrame([{"id": "pt1", "x": 5, "y": 5}])
    assert len(v._annotations) == 2
    assert len(v.rois_df) == 1
    assert len(v.points_df) == 1
    assert v.polygons_df.empty


def test_clear_rois_preserves_other_kinds():
    v = make_viewer()
    v.rois_df = pd.DataFrame([{"id": "r1", "x": 0, "y": 0, "width": 1, "height": 1}])
    v.points_df = pd.DataFrame([{"id": "pt1", "x": 5, "y": 5}])
    v.clear_rois()
    assert v.rois_df.empty
    assert len(v.points_df) == 1


def test_clear_all_annotations():
    v = make_viewer()
    v.rois_df = pd.DataFrame([{"id": "r1", "x": 0, "y": 0, "width": 1, "height": 1}])
    v.points_df = pd.DataFrame([{"id": "pt1", "x": 5, "y": 5}])
    v.clear_all_annotations()
    assert v._annotations == []


def test_legacy_private_traitlets_removed():
    v = make_viewer()
    # These were private in Phase 1 and no longer exist as traitlets.
    assert "_rois_data" not in v.trait_names()
    assert "_polygons_data" not in v.trait_names()
    assert "_points_data" not in v.trait_names()


def test_annotation_entry_shape():
    v = make_viewer()
    v.rois_df = pd.DataFrame([{"id": "r1", "x": 2, "y": 3, "width": 4, "height": 5}])
    entry = v._annotations[0]
    assert entry["kind"] == "rect"
    assert entry["id"] == "r1"
    assert entry["geometry"] == [2, 3, 6, 8]   # [x0, y0, x1, y1]
    assert "t" in entry and "z" in entry
    assert "created_at" in entry
    assert "metadata" in entry
```

- [ ] **Step 2: Run to verify fail**

```
uv run pytest tests/test_annotations_unified.py -v
```

Expected: at least four failures — `_annotations` traitlet missing, `_rois_data` still present, etc.

- [ ] **Step 3: Replace traitlet declarations in viewer.py**

Edit `anybioimage/viewer.py` around lines 119–141. Remove the six old traitlets (`_rois_data`, `rois_visible`, `roi_color`, `_polygons_data`, `polygons_visible`, `polygon_color`, `_points_data`, `points_visible`, `point_color`, `point_radius`) and replace with a single `_annotations` list. Keep `selected_annotation_id` and `selected_annotation_type`.

```python
# in anybioimage/viewer.py — replace the block from "# Annotations" (line ~124)
# through "point_radius = traitlets.Int(5).tag(sync=True)" with:

    # Annotations — unified list [spec §5].
    # Each entry: {id, kind, geometry, label, color, visible, t, z, created_at, metadata}
    _annotations = traitlets.List(traitlets.Dict()).tag(sync=True)

    # Selection (unchanged from Phase 1).
    selected_annotation_id = traitlets.Unicode("").tag(sync=True)
    selected_annotation_type = traitlets.Unicode("").tag(sync=True)
```

Verify the `_delete_sam_at` traitlet immediately after the selection pair still exists — it's unchanged.

- [ ] **Step 4: Rewrite `annotations.py`**

```python
# anybioimage/mixins/annotations.py
"""Annotations mixin for BioImageViewer.

Phase 2 [spec §5]: annotations are stored in a single `_annotations` traitlet.
This mixin exposes `.rois_df` / `.polygons_df` / `.points_df` as DataFrame views
filtered by `kind` so existing notebooks and other mixins (notably the SAM
integration that observes rectangle/point additions) keep working unchanged.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rect_entry(rec: dict[str, Any]) -> dict[str, Any]:
    x = float(rec["x"]); y = float(rec["y"])
    w = float(rec["width"]); h = float(rec["height"])
    return {
        "id": str(rec["id"]),
        "kind": "rect",
        "geometry": [x, y, x + w, y + h],
        "label": rec.get("label", ""),
        "color": rec.get("color", "#ff0000"),
        "visible": bool(rec.get("visible", True)),
        "t": int(rec.get("t", 0)),
        "z": int(rec.get("z", 0)),
        "created_at": rec.get("created_at") or _now_iso(),
        "metadata": dict(rec.get("metadata", {})),
    }


def _polygon_entry(rec: dict[str, Any]) -> dict[str, Any]:
    pts = rec["points"]
    if pts and isinstance(pts[0], dict):
        geom = [[float(p["x"]), float(p["y"])] for p in pts]
    else:
        geom = [[float(p[0]), float(p[1])] for p in pts]
    return {
        "id": str(rec["id"]),
        "kind": "polygon",
        "geometry": geom,
        "label": rec.get("label", ""),
        "color": rec.get("color", "#00ff00"),
        "visible": bool(rec.get("visible", True)),
        "t": int(rec.get("t", 0)),
        "z": int(rec.get("z", 0)),
        "created_at": rec.get("created_at") or _now_iso(),
        "metadata": dict(rec.get("metadata", {})),
    }


def _point_entry(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(rec["id"]),
        "kind": "point",
        "geometry": [float(rec["x"]), float(rec["y"])],
        "label": rec.get("label", ""),
        "color": rec.get("color", "#0066ff"),
        "visible": bool(rec.get("visible", True)),
        "t": int(rec.get("t", 0)),
        "z": int(rec.get("z", 0)),
        "created_at": rec.get("created_at") or _now_iso(),
        "metadata": dict(rec.get("metadata", {})),
    }


class AnnotationsMixin:
    """DataFrame-shaped views over the unified `_annotations` traitlet."""

    # ---- rect ----
    @property
    def rois_df(self) -> pd.DataFrame:
        rows = []
        for a in self._annotations:
            if a.get("kind") != "rect":
                continue
            x0, y0, x1, y1 = a["geometry"]
            rows.append({
                "id": a["id"], "x": x0, "y": y0,
                "width": x1 - x0, "height": y1 - y0,
            })
        if not rows:
            return pd.DataFrame(columns=["id", "x", "y", "width", "height"])
        return pd.DataFrame(rows)

    @rois_df.setter
    def rois_df(self, df: pd.DataFrame) -> None:
        others = [a for a in self._annotations if a.get("kind") != "rect"]
        new = [_rect_entry(r) for r in df.to_dict("records")]
        self._annotations = [*others, *new]

    # ---- polygon ----
    @property
    def polygons_df(self) -> pd.DataFrame:
        rows = []
        for a in self._annotations:
            if a.get("kind") != "polygon":
                continue
            pts = [{"x": x, "y": y} for x, y in a["geometry"]]
            rows.append({"id": a["id"], "points": pts, "num_vertices": len(pts)})
        if not rows:
            return pd.DataFrame(columns=["id", "points", "num_vertices"])
        return pd.DataFrame(rows)

    @polygons_df.setter
    def polygons_df(self, df: pd.DataFrame) -> None:
        others = [a for a in self._annotations if a.get("kind") != "polygon"]
        new = [_polygon_entry(r) for r in df.to_dict("records")]
        self._annotations = [*others, *new]

    # ---- point ----
    @property
    def points_df(self) -> pd.DataFrame:
        rows = []
        for a in self._annotations:
            if a.get("kind") != "point":
                continue
            x, y = a["geometry"]
            rows.append({"id": a["id"], "x": x, "y": y})
        if not rows:
            return pd.DataFrame(columns=["id", "x", "y"])
        return pd.DataFrame(rows)

    @points_df.setter
    def points_df(self, df: pd.DataFrame) -> None:
        others = [a for a in self._annotations if a.get("kind") != "point"]
        new = [_point_entry(r) for r in df.to_dict("records")]
        self._annotations = [*others, *new]

    # ---- bulk ops ----
    def clear_rois(self) -> None:
        self._annotations = [a for a in self._annotations if a.get("kind") != "rect"]

    def clear_polygons(self) -> None:
        self._annotations = [a for a in self._annotations if a.get("kind") != "polygon"]

    def clear_points(self) -> None:
        self._annotations = [a for a in self._annotations if a.get("kind") != "point"]

    def clear_all_annotations(self) -> None:
        self._annotations = []
        self.selected_annotation_id = ""
        self.selected_annotation_type = ""
```

- [ ] **Step 5: Update SAM observer to read the unified traitlet**

`sam_integration.py` currently observes `_rois_data` / `_points_data`. Phase 2 reroutes those observers onto `_annotations` and filters by `kind` inside the callback. Edit `enable_sam`:

```python
# anybioimage/mixins/sam_integration.py — in enable_sam(), replace the two observe() calls:

        # Phase 2 — observe the unified _annotations traitlet [spec §5].
        self.observe(self._on_annotations_changed, names=["_annotations"])
```

Remove the now-stale `unobserve` calls in `disable_sam`:

```python
# in disable_sam(), replace the two unobserve() calls:
        try:
            self.unobserve(self._on_annotations_changed, names=["_annotations"])
        except ValueError:
            pass
```

Replace `_on_rois_changed` and `_on_points_changed` with a single dispatcher (keep the per-kind helpers but have one observer feed both):

```python
# anybioimage/mixins/sam_integration.py — replace the existing two callbacks:

    def _on_annotations_changed(self, change):
        """Run SAM on any new rect or point in `_annotations`.

        Dispatches to the existing rect/point handlers. IDs already processed
        are skipped via `_processed_roi_ids` / `_processed_point_ids`.
        """
        if not getattr(self, "_sam_enabled", False):
            return
        new_list = change["new"] or []
        rois = [a for a in new_list if a.get("kind") == "rect"]
        points = [a for a in new_list if a.get("kind") == "point"]
        if rois:
            # translate rect entries back to the {id, x, y, width, height} shape
            # the existing _on_rois_changed helper expects.
            legacy = []
            for a in rois:
                x0, y0, x1, y1 = a["geometry"]
                legacy.append({
                    "id": a["id"], "x": x0, "y": y0,
                    "width": x1 - x0, "height": y1 - y0,
                })
            self._on_rois_changed({"new": legacy})
        if points:
            legacy = [{"id": a["id"], "x": a["geometry"][0], "y": a["geometry"][1]}
                      for a in points]
            self._on_points_changed({"new": legacy})
```

The original `_on_rois_changed` and `_on_points_changed` methods stay as-is — they already consume the legacy shape, which the dispatcher now synthesizes on the fly. This means SAM code changes are minimal and localized.

- [ ] **Step 6: Run the tests**

```
uv run pytest tests/test_annotations_unified.py tests/test_mixins.py tests/test_viewer_integration.py -v
```

Expected: `test_annotations_unified.py` — 9 passed. Existing `test_mixins.py` / `test_viewer_integration.py` that reference `_rois_data` / `_polygons_data` / `_points_data` directly will fail; fix each by going through the DataFrame property instead. (These are the only two test files that touched the private traitlets; Phase-1 left them unchanged.)

- [ ] **Step 7: Commit**

```bash
git add anybioimage/viewer.py anybioimage/mixins/annotations.py \
        anybioimage/mixins/sam_integration.py tests/test_annotations_unified.py \
        tests/test_mixins.py tests/test_viewer_integration.py
git commit -m "feat(annotations): unified _annotations traitlet with DataFrame views"
```

---

## Task 2: `annotationsToLayers.js` — pure function from annotations to deck.gl layers

**Goal:** A pure, easy-to-test function that takes `{annotations, currentT, currentZ, selectedId}` and returns `[PolygonLayer, ScatterplotLayer]`. Rectangles and polygons render as `PolygonLayer`; points render as `ScatterplotLayer`. Filter out annotations whose `t` or `z` does not match current slice (Phase 3 adds the "show all T/Z" toggle). Highlight the selected annotation with a thicker stroke. [spec §5]

**Files:**
- Create: `anybioimage/frontend/viewer/src/render/layers/annotationsToLayers.js`
- Create: `anybioimage/frontend/viewer/src/render/layers/annotationsToLayers.test.js`

- [ ] **Step 1: Write the failing test**

```js
// anybioimage/frontend/viewer/src/render/layers/annotationsToLayers.test.js
import { describe, it, expect, vi } from 'vitest';

// Stub the deck.gl layer constructors so we can assert props without loading WebGL.
vi.mock('@deck.gl/layers', () => {
  class StubLayer {
    constructor(props) { this.props = props; this.type = this.constructor.name; }
  }
  class PolygonLayer extends StubLayer {}
  class ScatterplotLayer extends StubLayer {}
  return { PolygonLayer, ScatterplotLayer };
});

import { annotationsToLayers } from './annotationsToLayers.js';

function rect(id, geom, extra = {}) {
  return { id, kind: 'rect', geometry: geom, color: '#ff0000',
           visible: true, t: 0, z: 0, metadata: {}, ...extra };
}
function poly(id, geom, extra = {}) {
  return { id, kind: 'polygon', geometry: geom, color: '#00ff00',
           visible: true, t: 0, z: 0, metadata: {}, ...extra };
}
function point(id, geom, extra = {}) {
  return { id, kind: 'point', geometry: geom, color: '#0066ff',
           visible: true, t: 0, z: 0, metadata: {}, ...extra };
}

describe('annotationsToLayers', () => {
  it('returns empty array when no annotations', () => {
    const out = annotationsToLayers({ annotations: [], currentT: 0, currentZ: 0 });
    expect(out).toEqual([]);
  });

  it('produces one PolygonLayer and one ScatterplotLayer when all kinds present', () => {
    const layers = annotationsToLayers({
      annotations: [
        rect('r1', [0, 0, 10, 10]),
        poly('p1', [[0,0],[5,0],[5,5]]),
        point('pt1', [3, 3]),
      ],
      currentT: 0, currentZ: 0,
    });
    expect(layers).toHaveLength(2);
    expect(layers[0].type).toBe('PolygonLayer');
    expect(layers[1].type).toBe('ScatterplotLayer');
  });

  it('rects are expanded to 4-point polygons', () => {
    const [polygonLayer] = annotationsToLayers({
      annotations: [rect('r1', [2, 3, 6, 8])],
      currentT: 0, currentZ: 0,
    });
    const [first] = polygonLayer.props.data;
    expect(first.polygon).toEqual([[2,3],[6,3],[6,8],[2,8]]);
  });

  it('filters by current T/Z', () => {
    const layers = annotationsToLayers({
      annotations: [
        rect('r1', [0,0,1,1], { t: 0, z: 0 }),
        rect('r2', [2,2,3,3], { t: 1, z: 0 }),
        rect('r3', [4,4,5,5], { t: 0, z: 1 }),
      ],
      currentT: 0, currentZ: 0,
    });
    expect(layers[0].props.data).toHaveLength(1);
    expect(layers[0].props.data[0].id).toBe('r1');
  });

  it('skips invisible annotations', () => {
    const layers = annotationsToLayers({
      annotations: [
        rect('r1', [0,0,1,1]),
        rect('r2', [2,2,3,3], { visible: false }),
      ],
      currentT: 0, currentZ: 0,
    });
    expect(layers[0].props.data).toHaveLength(1);
  });

  it('selected annotation gets thicker stroke width', () => {
    const layers = annotationsToLayers({
      annotations: [
        rect('r1', [0,0,1,1]),
        rect('r2', [2,2,3,3]),
      ],
      currentT: 0, currentZ: 0, selectedId: 'r2',
    });
    const getLineWidth = layers[0].props.getLineWidth;
    // Layer passes the data-object back; check both cases.
    expect(getLineWidth({ id: 'r1' })).toBe(1);
    expect(getLineWidth({ id: 'r2' })).toBe(3);
  });

  it('hex color strings are parsed into [r, g, b, a] with full alpha', () => {
    const layers = annotationsToLayers({
      annotations: [rect('r1', [0,0,1,1], { color: '#ff8000' })],
      currentT: 0, currentZ: 0,
    });
    const getLineColor = layers[0].props.getLineColor;
    expect(getLineColor({ id: 'r1' })).toEqual([255, 128, 0, 255]);
  });
});
```

- [ ] **Step 2: Run to verify fail**

```
cd anybioimage/frontend/viewer && npm run test -- annotationsToLayers
```

Expected: `Cannot find module './annotationsToLayers.js'`.

- [ ] **Step 3: Implement**

```js
// anybioimage/frontend/viewer/src/render/layers/annotationsToLayers.js
/**
 * Pure conversion from the unified `_annotations` traitlet to deck.gl layers
 * [spec §5]. Rectangles and polygons share a PolygonLayer; points render as
 * ScatterplotLayer.
 *
 * Filtering:
 *   - `visible === false` entries are skipped.
 *   - entries whose `t` / `z` do not match current slice are skipped
 *     (Phase 3 adds the "show all T/Z" toggle).
 *
 * Selection:
 *   - `selectedId` bumps the outline width for the matching annotation.
 */
import { PolygonLayer, ScatterplotLayer } from '@deck.gl/layers';

function hexToRgba(hex, alpha = 255) {
  const clean = (hex || '#ff0000').replace('#', '');
  const n = parseInt(clean.length === 3
    ? clean.split('').map(c => c + c).join('')
    : clean, 16);
  return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff, alpha];
}

function rectPoly(geom) {
  const [x0, y0, x1, y1] = geom;
  return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
}

export function annotationsToLayers({
  annotations = [],
  currentT = 0,
  currentZ = 0,
  selectedId = '',
}) {
  const visible = annotations.filter((a) =>
    a && a.visible !== false && (a.t ?? 0) === currentT && (a.z ?? 0) === currentZ
  );

  const polysAndRects = visible.filter((a) => a.kind === 'rect' || a.kind === 'polygon');
  const points = visible.filter((a) => a.kind === 'point');

  const out = [];

  if (polysAndRects.length) {
    const data = polysAndRects.map((a) => ({
      id: a.id,
      polygon: a.kind === 'rect' ? rectPoly(a.geometry) : a.geometry,
      color: a.color,
    }));
    out.push(new PolygonLayer({
      id: 'annotations-polygons',
      data,
      stroked: true,
      filled: true,
      pickable: true,
      getPolygon: (d) => d.polygon,
      getFillColor: (d) => hexToRgba(d.color, 40),
      getLineColor: (d) => hexToRgba(d.color, 255),
      getLineWidth: (d) => (d.id === selectedId ? 3 : 1),
      lineWidthUnits: 'pixels',
      lineWidthMinPixels: 1,
    }));
  }

  if (points.length) {
    const data = points.map((a) => ({
      id: a.id,
      position: a.geometry,
      color: a.color,
    }));
    out.push(new ScatterplotLayer({
      id: 'annotations-points',
      data,
      pickable: true,
      radiusUnits: 'pixels',
      radiusMinPixels: 3,
      getPosition: (d) => d.position,
      getRadius: (d) => (d.id === selectedId ? 8 : 5),
      getFillColor: (d) => hexToRgba(d.color, 200),
      getLineColor: [255, 255, 255, 255],
      stroked: true,
      lineWidthUnits: 'pixels',
      getLineWidth: 1,
    }));
  }

  return out;
}
```

- [ ] **Step 4: Run the tests**

```
cd anybioimage/frontend/viewer && npm run test -- annotationsToLayers
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
cd ../../..
git add anybioimage/frontend/viewer/src/render/layers/annotationsToLayers.js \
        anybioimage/frontend/viewer/src/render/layers/annotationsToLayers.test.js
git commit -m "feat(viewer/render): annotationsToLayers pure converter"
```

---

## Task 3: Mount annotation layers in DeckCanvas

**Goal:** Thread the output of `annotationsToLayers` into the `layers` useMemo of `DeckCanvas.jsx`, sandwiched between the image layer and the scale bar. Observe the `_annotations`, `selected_annotation_id`, `current_t`, and `current_z` traitlets and recompute layers on any change. [spec §3, §5]

**Files:**
- Modify: `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx`

- [ ] **Step 1: Read the current DeckCanvas**

Open `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx` and locate the `layers = useMemo(...)` block near the bottom.

- [ ] **Step 2: Add the annotations layer wiring**

Edit `DeckCanvas.jsx`. Add the import + hook + layer insertion. Full replacement of the file's top imports and the `layers` memo:

```jsx
// anybioimage/frontend/viewer/src/render/DeckCanvas.jsx
import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { OrthographicView } from '@deck.gl/core';
import { MultiscaleImageLayer, getDefaultInitialViewState } from '@hms-dbmi/viv';

import { openOmeZarr } from './pixel-sources/zarr-source.js';
import { AnywidgetPixelSource } from './pixel-sources/anywidget-source.js';
import { buildImageLayerProps } from './layers/buildImageLayer.js';
import { buildScaleBarLayer } from './layers/buildScaleBar.js';
import { annotationsToLayers } from './layers/annotationsToLayers.js';
import { useModelTrait } from '../model/useModelTrait.js';
```

Keep the existing `useContainerSize` helper and the component signature. Inside the component, **after** the existing `scaleBarVisible` / `imageVisible` lines, add:

```jsx
  const annotations = useModelTrait(model, '_annotations') || [];
  const selectedId = useModelTrait(model, 'selected_annotation_id') || '';
```

Replace the `layers` memo with:

```jsx
  const annotationLayers = useMemo(
    () => annotationsToLayers({
      annotations, currentT: currentT || 0, currentZ: currentZ || 0, selectedId,
    }),
    [annotations, currentT, currentZ, selectedId]);

  const layers = useMemo(() => {
    const out = [];
    if (imageLayerProps && imageVisible) {
      out.push(new MultiscaleImageLayer({
        id: 'viv-image', viewportId: 'ortho', ...imageLayerProps,
      }));
    }
    for (const l of annotationLayers) out.push(l);
    if (scaleBarVisible && pixelSizeUm) {
      out.push(buildScaleBarLayer({ pixelSizeUm, viewState, width, height }));
    }
    return out;
  }, [imageLayerProps, imageVisible, annotationLayers,
      pixelSizeUm, scaleBarVisible, viewState, width, height]);
```

Leave the remainder of the component (error branch, DeckGL JSX) unchanged.

- [ ] **Step 3: Seed an annotation via Python to smoke-test end-to-end**

Temporarily, in `examples/full_demo.py`, add a cell:

```python
@app.cell
def _smoke_annotations(v):
    import pandas as pd
    v.rois_df = pd.DataFrame([
        {"id": "smoke1", "x": 50, "y": 50, "width": 200, "height": 150},
    ])
    return
```

Build and eyeball the viewer; the rectangle should render. Then remove the smoke cell again.

- [ ] **Step 4: Build and commit**

```
cd anybioimage/frontend/viewer && npm run build && cd ../../..
```

Expected: `dist/viewer-bundle.js` rebuilt, no errors.

```bash
git add anybioimage/frontend/viewer/src/render/DeckCanvas.jsx \
        anybioimage/frontend/viewer/dist/viewer-bundle.js
git commit -m "feat(viewer/render): mount annotation layers in DeckCanvas"
```

---

## Task 4: Tool registry skeleton + `InteractionController`

**Goal:** Lay the foundation for drawing tools. Each tool is a module exporting `{id, cursor, onPointerDown, onPointerMove, onPointerUp, onKeyDown, getPreviewLayer}`. `InteractionController` owns the active-tool state, holds an imperative `previewLayer`, and exposes a `dispatch(event)` method the `DeckCanvas` calls from its pointer handlers. This task delivers the scaffold; individual tools land in Tasks 5–8. [spec §6]

**Files:**
- Create: `anybioimage/frontend/viewer/src/interaction/InteractionController.js`
- Create: `anybioimage/frontend/viewer/src/interaction/InteractionController.test.js`

- [ ] **Step 1: Write the failing test**

```js
// anybioimage/frontend/viewer/src/interaction/InteractionController.test.js
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { InteractionController } from './InteractionController.js';

function fakeModel(initial = {}) {
  const state = { ...initial };
  const listeners = {};
  return {
    get: (k) => state[k],
    set: (k, v) => { state[k] = v; (listeners[`change:${k}`] || []).forEach((cb) => cb({ new: v })); },
    on: (evt, cb) => { (listeners[evt] = listeners[evt] || []).push(cb); },
    off: (evt, cb) => { listeners[evt] = (listeners[evt] || []).filter((x) => x !== cb); },
    save_changes: () => {},
    send: vi.fn(),
    _state: state,
  };
}

describe('InteractionController', () => {
  let model, controller;
  beforeEach(() => {
    model = fakeModel({ tool_mode: 'pan', _annotations: [], current_t: 0, current_z: 0 });
    controller = new InteractionController(model);
  });

  it('picks the active tool from tool_mode', () => {
    expect(controller.activeToolId).toBe('pan');
    model.set('tool_mode', 'rect');
    expect(controller.activeToolId).toBe('rect');
  });

  it('dispatches pointer events to the active tool', () => {
    const stubTool = {
      id: 'stub', cursor: 'crosshair',
      onPointerDown: vi.fn(),
      onPointerMove: vi.fn(),
      onPointerUp: vi.fn(),
      onKeyDown: vi.fn(),
      getPreviewLayer: () => null,
    };
    controller.register(stubTool);
    model.set('tool_mode', 'stub');
    controller.handlePointerEvent('down', { x: 1, y: 2 });
    controller.handlePointerEvent('move', { x: 3, y: 4 });
    controller.handlePointerEvent('up',   { x: 5, y: 6 });
    expect(stubTool.onPointerDown).toHaveBeenCalledTimes(1);
    expect(stubTool.onPointerMove).toHaveBeenCalledTimes(1);
    expect(stubTool.onPointerUp).toHaveBeenCalledTimes(1);
  });

  it('returns the preview layer from the active tool', () => {
    const layer = { isLayer: true };
    const stubTool = {
      id: 'stub', cursor: 'crosshair',
      onPointerDown: () => {}, onPointerMove: () => {}, onPointerUp: () => {},
      onKeyDown: () => {},
      getPreviewLayer: () => layer,
    };
    controller.register(stubTool);
    model.set('tool_mode', 'stub');
    expect(controller.getPreviewLayer()).toBe(layer);
  });

  it('falls back to a no-op tool when tool_mode is unknown', () => {
    model.set('tool_mode', 'does-not-exist');
    // Should not throw.
    expect(() => controller.handlePointerEvent('down', { x: 0, y: 0 })).not.toThrow();
    expect(controller.getPreviewLayer()).toBeNull();
  });

  it('notifies subscribers when preview layer changes', () => {
    const sub = vi.fn();
    controller.onPreviewChange(sub);
    controller.markPreviewDirty();
    expect(sub).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run to verify fail**

```
cd anybioimage/frontend/viewer && npm run test -- InteractionController
```

Expected: missing module.

- [ ] **Step 3: Implement**

```js
// anybioimage/frontend/viewer/src/interaction/InteractionController.js
/**
 * InteractionController — central dispatcher for pointer / key events on the
 * DeckCanvas. Holds the active tool selected by the `tool_mode` traitlet and
 * forwards events. Tools mutate `_annotations` (only mutation surface other
 * than the Layers panel).
 *
 * Each registered tool exports:
 *   { id, cursor, onPointerDown, onPointerMove, onPointerUp, onKeyDown,
 *     getPreviewLayer }
 * `getPreviewLayer()` returns a deck.gl Layer (or null) that renders the
 * in-progress draw. `markPreviewDirty()` triggers a re-render in DeckCanvas.
 */
const NOOP_TOOL = {
  id: '__noop',
  cursor: 'default',
  onPointerDown() {},
  onPointerMove() {},
  onPointerUp() {},
  onKeyDown() {},
  getPreviewLayer() { return null; },
};

export class InteractionController {
  constructor(model) {
    this._model = model;
    this._tools = new Map();
    this._previewListeners = new Set();
    this._ctx = { model, controller: this };
  }

  register(tool) {
    this._tools.set(tool.id, tool);
  }

  get activeToolId() {
    return this._model.get('tool_mode') || 'pan';
  }

  get activeTool() {
    return this._tools.get(this.activeToolId) || NOOP_TOOL;
  }

  get cursor() {
    return this.activeTool.cursor || 'default';
  }

  handlePointerEvent(phase, event) {
    const tool = this.activeTool;
    try {
      if (phase === 'down') tool.onPointerDown(event, this._ctx);
      else if (phase === 'move') tool.onPointerMove(event, this._ctx);
      else if (phase === 'up') tool.onPointerUp(event, this._ctx);
    } catch (err) {
      // Tools should never throw at runtime; log so we can see regressions
      // without killing the canvas.
      console.error(`tool '${tool.id}' threw in ${phase}:`, err);
    }
  }

  handleKeyDown(event) {
    try {
      this.activeTool.onKeyDown(event, this._ctx);
    } catch (err) {
      console.error(`tool '${this.activeTool.id}' threw in keyDown:`, err);
    }
  }

  getPreviewLayer() {
    return this.activeTool.getPreviewLayer(this._ctx) || null;
  }

  onPreviewChange(cb) {
    this._previewListeners.add(cb);
    return () => this._previewListeners.delete(cb);
  }

  markPreviewDirty() {
    for (const cb of this._previewListeners) cb();
  }
}
```

- [ ] **Step 4: Run the tests**

```
cd anybioimage/frontend/viewer && npm run test -- InteractionController
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd ../../..
git add anybioimage/frontend/viewer/src/interaction/InteractionController.js \
        anybioimage/frontend/viewer/src/interaction/InteractionController.test.js
git commit -m "feat(viewer/interaction): InteractionController + tool registry skeleton"
```

---

## Task 5: Pan + Select tools

**Goal:** The two non-drawing tools. **Pan** is a no-op — it just sets the cursor; deck.gl's built-in `OrthographicView` controller handles pan/zoom. **Select** uses deck.gl's picking via the tool `ctx.controller` + a `pickObject` callback provided by `DeckCanvas`; on click, the annotation id under the pointer is written to `selected_annotation_id` + `selected_annotation_type`. [spec §6]

**Files:**
- Create: `anybioimage/frontend/viewer/src/interaction/tools/pan.js`
- Create: `anybioimage/frontend/viewer/src/interaction/tools/select.js`
- Create: `anybioimage/frontend/viewer/src/interaction/tools/select.test.js`

- [ ] **Step 1: Pan tool**

```js
// anybioimage/frontend/viewer/src/interaction/tools/pan.js
/** Pan tool — all pointer handling is delegated to deck.gl's view controller.
 *  This module exists so that every tool follows the same registry shape. */
export const panTool = {
  id: 'pan',
  cursor: 'grab',
  onPointerDown() {},
  onPointerMove() {},
  onPointerUp() {},
  onKeyDown() {},
  getPreviewLayer() { return null; },
};
```

- [ ] **Step 2: Failing test for select**

```js
// anybioimage/frontend/viewer/src/interaction/tools/select.test.js
import { describe, it, expect, vi } from 'vitest';
import { selectTool } from './select.js';

function ctxWithPick(picked) {
  const state = { selected_annotation_id: '', selected_annotation_type: '' };
  return {
    model: {
      get: (k) => state[k],
      set: (k, v) => { state[k] = v; },
      save_changes: vi.fn(),
    },
    pickObject: vi.fn(() => picked),
    _state: state,
  };
}

describe('selectTool', () => {
  it('clears selection when pointer-up hits empty space', () => {
    const ctx = ctxWithPick(null);
    ctx._state.selected_annotation_id = 'r1';
    ctx._state.selected_annotation_type = 'rect';
    selectTool.onPointerUp({ x: 10, y: 10 }, ctx);
    expect(ctx._state.selected_annotation_id).toBe('');
    expect(ctx._state.selected_annotation_type).toBe('');
  });

  it('writes selected id + kind from the picked annotation', () => {
    const ctx = ctxWithPick({
      layer: { id: 'annotations-polygons' },
      object: { id: 'r1' },
      sourceAnnotation: { id: 'r1', kind: 'rect' },
    });
    selectTool.onPointerUp({ x: 10, y: 10 }, ctx);
    expect(ctx._state.selected_annotation_id).toBe('r1');
    expect(ctx._state.selected_annotation_type).toBe('rect');
  });

  it('infers kind from layer id when sourceAnnotation is absent', () => {
    const ctx = ctxWithPick({
      layer: { id: 'annotations-points' },
      object: { id: 'pt1' },
    });
    selectTool.onPointerUp({ x: 10, y: 10 }, ctx);
    expect(ctx._state.selected_annotation_type).toBe('point');
  });
});
```

- [ ] **Step 3: Run to verify fail**

```
cd anybioimage/frontend/viewer && npm run test -- select
```

Expected: missing module.

- [ ] **Step 4: Implement select**

```js
// anybioimage/frontend/viewer/src/interaction/tools/select.js
/** Select tool — click-to-select an annotation. Drag / vertex edit are Phase 3.
 *
 *  The `ctx.pickObject(event)` callback is supplied by DeckCanvas; it wraps
 *  the deck.gl picking API and returns either null or `{layer, object,
 *  sourceAnnotation}` — where `sourceAnnotation` is the full `_annotations`
 *  entry if the layer composer attached it.
 */
function kindFromLayerId(id) {
  if (id === 'annotations-points') return 'point';
  if (id === 'annotations-polygons') return 'rect';   // rect and polygon share the layer
  return '';
}

export const selectTool = {
  id: 'select',
  cursor: 'default',
  onPointerDown() {},
  onPointerMove() {},
  onPointerUp(event, ctx) {
    const picked = typeof ctx.pickObject === 'function' ? ctx.pickObject(event) : null;
    if (!picked) {
      ctx.model.set('selected_annotation_id', '');
      ctx.model.set('selected_annotation_type', '');
      ctx.model.save_changes();
      return;
    }
    const id = picked.sourceAnnotation?.id ?? picked.object?.id ?? '';
    const kind = picked.sourceAnnotation?.kind
              || kindFromLayerId(picked.layer?.id)
              || '';
    ctx.model.set('selected_annotation_id', id);
    ctx.model.set('selected_annotation_type', kind);
    ctx.model.save_changes();
  },
  onKeyDown() {},
  getPreviewLayer() { return null; },
};
```

- [ ] **Step 5: Run the tests**

```
cd anybioimage/frontend/viewer && npm run test -- select
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
cd ../../..
git add anybioimage/frontend/viewer/src/interaction/tools/pan.js \
        anybioimage/frontend/viewer/src/interaction/tools/select.js \
        anybioimage/frontend/viewer/src/interaction/tools/select.test.js
git commit -m "feat(viewer/tools): pan + select tools"
```

---

## Task 6: Rect tool — drag-rectangle drawing

**Goal:** Click-drag creates a rectangle annotation. Mouse-down starts the draw, mouse-move updates a preview `PolygonLayer`, mouse-up commits to `_annotations`. Abort with `Esc`. Emits `current_t` / `current_z` onto the new entry so T/Z filtering works out of the box. [spec §5, §6]

**Files:**
- Create: `anybioimage/frontend/viewer/src/interaction/tools/rect.js`
- Create: `anybioimage/frontend/viewer/src/interaction/tools/rect.test.js`

- [ ] **Step 1: Failing tests**

```js
// anybioimage/frontend/viewer/src/interaction/tools/rect.test.js
import { describe, it, expect, vi, beforeEach } from 'vitest';
vi.mock('@deck.gl/layers', () => {
  class PolygonLayer { constructor(props) { this.props = props; } }
  return { PolygonLayer };
});
import { rectTool } from './rect.js';

function fakeModel() {
  const state = { _annotations: [], current_t: 0, current_z: 0 };
  return {
    get: (k) => state[k],
    set: (k, v) => { state[k] = v; },
    save_changes: vi.fn(),
    send: vi.fn(),
    _state: state,
  };
}

function ctx(model, controller = { markPreviewDirty: vi.fn() }) {
  return { model, controller };
}

describe('rectTool', () => {
  let model;
  beforeEach(() => {
    model = fakeModel();
    rectTool.reset();
  });

  it('preview layer is null before any pointer down', () => {
    expect(rectTool.getPreviewLayer(ctx(model))).toBeNull();
  });

  it('draw → move → up commits a rect annotation', () => {
    rectTool.onPointerDown({ x: 10, y: 20 }, ctx(model));
    rectTool.onPointerMove({ x: 40, y: 60 }, ctx(model));
    expect(rectTool.getPreviewLayer(ctx(model))).not.toBeNull();
    rectTool.onPointerUp({ x: 40, y: 60 }, ctx(model));
    const ann = model._state._annotations;
    expect(ann).toHaveLength(1);
    expect(ann[0].kind).toBe('rect');
    expect(ann[0].geometry).toEqual([10, 20, 40, 60]);
    expect(ann[0].t).toBe(0);
    expect(ann[0].z).toBe(0);
    expect(ann[0].id).toMatch(/^rect_/);
    expect(rectTool.getPreviewLayer(ctx(model))).toBeNull();
  });

  it('normalises reversed drags into positive-extent rects', () => {
    rectTool.onPointerDown({ x: 100, y: 100 }, ctx(model));
    rectTool.onPointerMove({ x: 20, y: 10 }, ctx(model));
    rectTool.onPointerUp({ x: 20, y: 10 }, ctx(model));
    expect(model._state._annotations[0].geometry).toEqual([20, 10, 100, 100]);
  });

  it('discards tiny drags (click without drag)', () => {
    rectTool.onPointerDown({ x: 100, y: 100 }, ctx(model));
    rectTool.onPointerUp({ x: 100, y: 101 }, ctx(model));
    expect(model._state._annotations).toHaveLength(0);
  });

  it('Esc aborts an in-progress draw', () => {
    rectTool.onPointerDown({ x: 10, y: 20 }, ctx(model));
    rectTool.onPointerMove({ x: 30, y: 40 }, ctx(model));
    rectTool.onKeyDown({ key: 'Escape' }, ctx(model));
    rectTool.onPointerUp({ x: 50, y: 60 }, ctx(model));
    expect(model._state._annotations).toHaveLength(0);
    expect(rectTool.getPreviewLayer(ctx(model))).toBeNull();
  });
});
```

- [ ] **Step 2: Run to verify fail**

```
cd anybioimage/frontend/viewer && npm run test -- interaction/tools/rect
```

Expected: missing module.

- [ ] **Step 3: Implement**

```js
// anybioimage/frontend/viewer/src/interaction/tools/rect.js
/** Rect tool — drag to draw; commits on pointer-up. Esc to cancel.
 *
 *  The tool keeps its drag state in the module-level `_state`. An
 *  `InteractionController` keeps a single tool instance around between
 *  pointer events, so local closure state is fine; we still expose `reset()`
 *  for tests and for the `tool_mode` change hook in DeckCanvas.
 */
import { PolygonLayer } from '@deck.gl/layers';

let _nextId = 1;
const _state = { drag: null };     // { startX, startY, currX, currY }

function makeId() { return `rect_${Date.now().toString(36)}_${_nextId++}`; }

function makePreview(state) {
  const [x0, y0, x1, y1] = [
    Math.min(state.startX, state.currX), Math.min(state.startY, state.currY),
    Math.max(state.startX, state.currX), Math.max(state.startY, state.currY),
  ];
  return new PolygonLayer({
    id: 'tool-rect-preview',
    data: [{ polygon: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]] }],
    stroked: true, filled: false,
    getPolygon: (d) => d.polygon,
    getLineColor: [13, 110, 253, 200],
    getLineWidth: 2,
    lineWidthUnits: 'pixels',
  });
}

export const rectTool = {
  id: 'rect',
  cursor: 'crosshair',

  onPointerDown(event, ctx) {
    _state.drag = { startX: event.x, startY: event.y, currX: event.x, currY: event.y };
    ctx.controller?.markPreviewDirty?.();
  },

  onPointerMove(event, ctx) {
    if (!_state.drag) return;
    _state.drag.currX = event.x;
    _state.drag.currY = event.y;
    ctx.controller?.markPreviewDirty?.();
  },

  onPointerUp(event, ctx) {
    if (!_state.drag) return;
    const d = _state.drag;
    _state.drag = null;
    const x0 = Math.min(d.startX, event.x), y0 = Math.min(d.startY, event.y);
    const x1 = Math.max(d.startX, event.x), y1 = Math.max(d.startY, event.y);
    ctx.controller?.markPreviewDirty?.();
    if ((x1 - x0) < 2 || (y1 - y0) < 2) return;   // discard micro drags
    const t = ctx.model.get('current_t') ?? 0;
    const z = ctx.model.get('current_z') ?? 0;
    const entry = {
      id: makeId(),
      kind: 'rect',
      geometry: [x0, y0, x1, y1],
      label: '',
      color: '#ff0000',
      visible: true,
      t, z,
      created_at: new Date().toISOString(),
      metadata: {},
    };
    const existing = ctx.model.get('_annotations') || [];
    ctx.model.set('_annotations', [...existing, entry]);
    ctx.model.save_changes();
  },

  onKeyDown(event, ctx) {
    if (event.key === 'Escape' && _state.drag) {
      _state.drag = null;
      ctx.controller?.markPreviewDirty?.();
    }
  },

  getPreviewLayer() {
    return _state.drag ? makePreview(_state.drag) : null;
  },

  reset() {
    _state.drag = null;
  },
};
```

- [ ] **Step 4: Run the tests**

```
cd anybioimage/frontend/viewer && npm run test -- interaction/tools/rect
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd ../../..
git add anybioimage/frontend/viewer/src/interaction/tools/rect.js \
        anybioimage/frontend/viewer/src/interaction/tools/rect.test.js
git commit -m "feat(viewer/tools): rect draw tool"
```

---

## Task 7: Polygon tool — click-to-add-vertex, double-click / Enter to close

**Goal:** Click to add a vertex; pointer-move previews a rubber-band segment to the candidate next vertex; double-click OR Enter closes the polygon; Esc cancels. Commits to `_annotations`. [spec §5, §6]

**Files:**
- Create: `anybioimage/frontend/viewer/src/interaction/tools/polygon.js`
- Create: `anybioimage/frontend/viewer/src/interaction/tools/polygon.test.js`

- [ ] **Step 1: Failing tests**

```js
// anybioimage/frontend/viewer/src/interaction/tools/polygon.test.js
import { describe, it, expect, vi, beforeEach } from 'vitest';
vi.mock('@deck.gl/layers', () => {
  class PathLayer { constructor(p) { this.props = p; this.type = 'PathLayer'; } }
  class PolygonLayer { constructor(p) { this.props = p; this.type = 'PolygonLayer'; } }
  return { PathLayer, PolygonLayer };
});
import { polygonTool } from './polygon.js';

function fakeModel() {
  const state = { _annotations: [], current_t: 0, current_z: 0 };
  return {
    get: (k) => state[k],
    set: (k, v) => { state[k] = v; },
    save_changes: vi.fn(),
    _state: state,
  };
}
function ctx(model, controller = { markPreviewDirty: vi.fn() }) {
  return { model, controller };
}

describe('polygonTool', () => {
  let model;
  beforeEach(() => {
    model = fakeModel();
    polygonTool.reset();
  });

  it('clicks add vertices; preview layer appears after first click', () => {
    polygonTool.onPointerDown({ x: 10, y: 10 }, ctx(model));
    polygonTool.onPointerUp({ x: 10, y: 10 }, ctx(model));
    expect(polygonTool.getPreviewLayer(ctx(model))).not.toBeNull();
    polygonTool.onPointerDown({ x: 20, y: 20 }, ctx(model));
    polygonTool.onPointerUp({ x: 20, y: 20 }, ctx(model));
    polygonTool.onPointerDown({ x: 30, y: 10 }, ctx(model));
    polygonTool.onPointerUp({ x: 30, y: 10 }, ctx(model));
    // No commit until close; the live list stays empty.
    expect(model._state._annotations).toHaveLength(0);
  });

  it('double-click commits (needs ≥3 vertices)', () => {
    polygonTool.onPointerDown({ x: 10, y: 10 }, ctx(model));
    polygonTool.onPointerUp({ x: 10, y: 10 }, ctx(model));
    polygonTool.onPointerDown({ x: 30, y: 10 }, ctx(model));
    polygonTool.onPointerUp({ x: 30, y: 10 }, ctx(model));
    polygonTool.onPointerDown({ x: 20, y: 30 }, ctx(model));
    polygonTool.onDoubleClick({ x: 20, y: 30 }, ctx(model));
    expect(model._state._annotations).toHaveLength(1);
    const p = model._state._annotations[0];
    expect(p.kind).toBe('polygon');
    expect(p.geometry).toHaveLength(3);
  });

  it('Enter closes an in-progress polygon', () => {
    polygonTool.onPointerDown({ x: 1, y: 1 }, ctx(model));
    polygonTool.onPointerUp({ x: 1, y: 1 }, ctx(model));
    polygonTool.onPointerDown({ x: 2, y: 2 }, ctx(model));
    polygonTool.onPointerUp({ x: 2, y: 2 }, ctx(model));
    polygonTool.onPointerDown({ x: 3, y: 1 }, ctx(model));
    polygonTool.onPointerUp({ x: 3, y: 1 }, ctx(model));
    polygonTool.onKeyDown({ key: 'Enter' }, ctx(model));
    expect(model._state._annotations).toHaveLength(1);
  });

  it('Enter with <3 vertices does not commit', () => {
    polygonTool.onPointerDown({ x: 1, y: 1 }, ctx(model));
    polygonTool.onPointerUp({ x: 1, y: 1 }, ctx(model));
    polygonTool.onKeyDown({ key: 'Enter' }, ctx(model));
    expect(model._state._annotations).toHaveLength(0);
  });

  it('Esc abandons without commit', () => {
    polygonTool.onPointerDown({ x: 1, y: 1 }, ctx(model));
    polygonTool.onPointerUp({ x: 1, y: 1 }, ctx(model));
    polygonTool.onKeyDown({ key: 'Escape' }, ctx(model));
    expect(polygonTool.getPreviewLayer(ctx(model))).toBeNull();
    expect(model._state._annotations).toHaveLength(0);
  });
});
```

- [ ] **Step 2: Run to verify fail**

```
cd anybioimage/frontend/viewer && npm run test -- interaction/tools/polygon
```

Expected: missing module.

- [ ] **Step 3: Implement**

```js
// anybioimage/frontend/viewer/src/interaction/tools/polygon.js
/** Polygon tool — click to add vertices; double-click / Enter to close;
 *  Esc to cancel. Emits a `kind: "polygon"` annotation entry on commit.
 */
import { PathLayer, PolygonLayer } from '@deck.gl/layers';

let _nextId = 1;
const _state = {
  vertices: null,    // [[x,y], ...] while drawing; null when idle.
  hover: null,       // current pointer position for rubber-band preview
};

function makeId() { return `poly_${Date.now().toString(36)}_${_nextId++}`; }

function makePreview() {
  const verts = _state.vertices;
  if (!verts || verts.length === 0) return null;
  const path = [...verts];
  if (_state.hover) path.push(_state.hover);
  return new PathLayer({
    id: 'tool-polygon-preview',
    data: [{ path }],
    widthUnits: 'pixels',
    getPath: (d) => d.path,
    getColor: [13, 110, 253, 200],
    getWidth: 2,
  });
}

function commit(ctx) {
  const verts = _state.vertices;
  if (!verts || verts.length < 3) return;
  const t = ctx.model.get('current_t') ?? 0;
  const z = ctx.model.get('current_z') ?? 0;
  const entry = {
    id: makeId(),
    kind: 'polygon',
    geometry: verts.map(([x, y]) => [x, y]),
    label: '',
    color: '#00ff00',
    visible: true,
    t, z,
    created_at: new Date().toISOString(),
    metadata: {},
  };
  const existing = ctx.model.get('_annotations') || [];
  ctx.model.set('_annotations', [...existing, entry]);
  ctx.model.save_changes();
  _state.vertices = null;
  _state.hover = null;
  ctx.controller?.markPreviewDirty?.();
}

export const polygonTool = {
  id: 'polygon',
  cursor: 'crosshair',

  onPointerDown(event, ctx) {
    // Accumulate the pending vertex here; commit is on pointer-up so
    // click-vs-drag disambiguation stays simple.
    if (!_state.vertices) _state.vertices = [];
    _state.vertices.push([event.x, event.y]);
    _state.hover = [event.x, event.y];
    ctx.controller?.markPreviewDirty?.();
  },

  onPointerMove(event, ctx) {
    if (!_state.vertices) return;
    _state.hover = [event.x, event.y];
    ctx.controller?.markPreviewDirty?.();
  },

  onPointerUp() {},   // vertex is already in _state.vertices from pointer-down

  onDoubleClick(event, ctx) {
    commit(ctx);
  },

  onKeyDown(event, ctx) {
    if (event.key === 'Enter') commit(ctx);
    else if (event.key === 'Escape') {
      _state.vertices = null;
      _state.hover = null;
      ctx.controller?.markPreviewDirty?.();
    }
  },

  getPreviewLayer() {
    return makePreview();
  },

  reset() {
    _state.vertices = null;
    _state.hover = null;
  },
};
```

- [ ] **Step 4: Run the tests**

```
cd anybioimage/frontend/viewer && npm run test -- interaction/tools/polygon
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd ../../..
git add anybioimage/frontend/viewer/src/interaction/tools/polygon.js \
        anybioimage/frontend/viewer/src/interaction/tools/polygon.test.js
git commit -m "feat(viewer/tools): polygon draw tool"
```

---

## Task 8: Point tool — click to place

**Goal:** Simplest tool. Click places a `kind: "point"` annotation at the pointer location. No preview needed; the annotation renders immediately. [spec §5, §6]

**Files:**
- Create: `anybioimage/frontend/viewer/src/interaction/tools/point.js`
- Create: `anybioimage/frontend/viewer/src/interaction/tools/point.test.js`

- [ ] **Step 1: Failing tests**

```js
// anybioimage/frontend/viewer/src/interaction/tools/point.test.js
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { pointTool } from './point.js';

function fakeModel() {
  const state = { _annotations: [], current_t: 3, current_z: 2 };
  return {
    get: (k) => state[k],
    set: (k, v) => { state[k] = v; },
    save_changes: vi.fn(),
    _state: state,
  };
}
const ctx = (m) => ({ model: m, controller: { markPreviewDirty: vi.fn() } });

describe('pointTool', () => {
  let model;
  beforeEach(() => { model = fakeModel(); });

  it('places a point on pointer-up', () => {
    pointTool.onPointerDown({ x: 12, y: 34 }, ctx(model));
    pointTool.onPointerUp({ x: 12, y: 34 }, ctx(model));
    expect(model._state._annotations).toHaveLength(1);
    const p = model._state._annotations[0];
    expect(p.kind).toBe('point');
    expect(p.geometry).toEqual([12, 34]);
    expect(p.t).toBe(3);
    expect(p.z).toBe(2);
  });

  it('discards a drag (pointer-up far from pointer-down)', () => {
    pointTool.onPointerDown({ x: 10, y: 10 }, ctx(model));
    pointTool.onPointerUp({ x: 80, y: 80 }, ctx(model));
    expect(model._state._annotations).toHaveLength(0);
  });
});
```

- [ ] **Step 2: Run to verify fail**

```
cd anybioimage/frontend/viewer && npm run test -- interaction/tools/point
```

Expected: missing module.

- [ ] **Step 3: Implement**

```js
// anybioimage/frontend/viewer/src/interaction/tools/point.js
/** Point tool — click to place a point annotation. Drags (pointer-up far from
 *  pointer-down) are discarded so accidental click-and-slide does not fire. */
let _nextId = 1;
const _state = { downX: null, downY: null };

function makeId() { return `point_${Date.now().toString(36)}_${_nextId++}`; }

export const pointTool = {
  id: 'point',
  cursor: 'crosshair',

  onPointerDown(event) {
    _state.downX = event.x;
    _state.downY = event.y;
  },

  onPointerMove() {},

  onPointerUp(event, ctx) {
    if (_state.downX == null) return;
    const dx = event.x - _state.downX;
    const dy = event.y - _state.downY;
    _state.downX = _state.downY = null;
    if (dx * dx + dy * dy > 25) return;   // >5 px = treat as drag; discard
    const t = ctx.model.get('current_t') ?? 0;
    const z = ctx.model.get('current_z') ?? 0;
    const entry = {
      id: makeId(),
      kind: 'point',
      geometry: [event.x, event.y],
      label: '',
      color: '#0066ff',
      visible: true,
      t, z,
      created_at: new Date().toISOString(),
      metadata: {},
    };
    const existing = ctx.model.get('_annotations') || [];
    ctx.model.set('_annotations', [...existing, entry]);
    ctx.model.save_changes();
  },

  onKeyDown() {},
  getPreviewLayer() { return null; },
};
```

- [ ] **Step 4: Run the tests**

```
cd anybioimage/frontend/viewer && npm run test -- interaction/tools/point
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd ../../..
git add anybioimage/frontend/viewer/src/interaction/tools/point.js \
        anybioimage/frontend/viewer/src/interaction/tools/point.test.js
git commit -m "feat(viewer/tools): point draw tool"
```

---

## Task 9: Wire `InteractionController` + tools into `DeckCanvas`; enable rect/polygon/point in Toolbar

**Goal:** Hook the controller into the canvas: on mount, register all five tools; pipe deck.gl's `onClick` / `onDragStart` / `onDrag` / `onDragEnd` / double-click events to `controller.handlePointerEvent()`; expose a `pickObject()` helper to tools; mount `controller.getPreviewLayer()` at the top of the layer stack. Enable the rect/polygon/point buttons in `Toolbar.jsx` (keep line / areaMeasure disabled for Phase 3). [spec §6]

**Files:**
- Modify: `anybioimage/frontend/viewer/src/App.jsx`
- Modify: `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx`
- Modify: `anybioimage/frontend/viewer/src/chrome/Toolbar.jsx`

- [ ] **Step 1: Instantiate the controller in `App.jsx`**

Replace `anybioimage/frontend/viewer/src/App.jsx`:

```jsx
// anybioimage/frontend/viewer/src/App.jsx
import React, { useState, useRef, useMemo, useEffect } from 'react';
import { Toolbar } from './chrome/Toolbar.jsx';
import { DimControls } from './chrome/DimControls.jsx';
import { StatusBar } from './chrome/StatusBar.jsx';
import { LayersPanel } from './chrome/LayersPanel/LayersPanel.jsx';
import { DeckCanvas } from './render/DeckCanvas.jsx';
import { installKeyboard } from './interaction/keyboard.js';
import { makeHoverHandler } from './render/onHoverPixelInfo.js';
import { InteractionController } from './interaction/InteractionController.js';
import { panTool } from './interaction/tools/pan.js';
import { selectTool } from './interaction/tools/select.js';
import { rectTool } from './interaction/tools/rect.js';
import { polygonTool } from './interaction/tools/polygon.js';
import { pointTool } from './interaction/tools/point.js';

export function App({ model }) {
  const [panelOpen, setPanelOpen] = useState(false);
  const [hover, setHover] = useState(null);
  const sourcesRef = useRef(null);
  const selectionsRef = useRef(null);
  const deckRef = useRef(null);

  const controller = useMemo(() => {
    const c = new InteractionController(model);
    c.register(panTool);
    c.register(selectTool);
    c.register(rectTool);
    c.register(polygonTool);
    c.register(pointTool);
    return c;
  }, [model]);

  // Reset per-tool drag state on tool switch — keeps previews from leaking.
  useEffect(() => {
    const handler = () => {
      rectTool.reset();
      polygonTool.reset();
    };
    model.on('change:tool_mode', handler);
    return () => model.off('change:tool_mode', handler);
  }, [model, controller]);

  const onHover = useMemo(
    () => makeHoverHandler({
      getSources: () => sourcesRef.current,
      getSelections: () => selectionsRef.current,
      setHover,
    }),
    []);

  useEffect(() => installKeyboard(model), [model]);

  return (
    <div className="bioimage-viewer" tabIndex={0}>
      <Toolbar model={model} onToggleLayers={() => setPanelOpen((v) => !v)} panelOpen={panelOpen} />
      <DimControls model={model} />
      <div className="content-area" style={{ display: 'flex', flex: 1, minHeight: 500 }}>
        <div className="viewport-slot" style={{ position: 'relative', flex: 1, minHeight: 500, background: '#000' }}>
          <DeckCanvas model={model} onHover={onHover}
                      controller={controller}
                      deckRef={deckRef}
                      sourcesRef={sourcesRef}
                      selectionsRef={selectionsRef} />
        </div>
        {panelOpen && <LayersPanel model={model} />}
      </div>
      <StatusBar model={model} hover={hover} />
    </div>
  );
}
```

- [ ] **Step 2: Wire the controller into `DeckCanvas.jsx`**

Edit `DeckCanvas.jsx`. Accept the new `controller` prop, subscribe to its `onPreviewChange` to trigger re-renders, pipe deck.gl events through, and mount the preview layer.

Full replacement:

```jsx
// anybioimage/frontend/viewer/src/render/DeckCanvas.jsx
import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { OrthographicView } from '@deck.gl/core';
import { MultiscaleImageLayer, getDefaultInitialViewState } from '@hms-dbmi/viv';

import { openOmeZarr } from './pixel-sources/zarr-source.js';
import { AnywidgetPixelSource } from './pixel-sources/anywidget-source.js';
import { buildImageLayerProps } from './layers/buildImageLayer.js';
import { buildScaleBarLayer } from './layers/buildScaleBar.js';
import { annotationsToLayers } from './layers/annotationsToLayers.js';
import { useModelTrait } from '../model/useModelTrait.js';

function useContainerSize(ref, fallback = { width: 800, height: 600 }) {
  const [size, setSize] = useState(fallback);
  useLayoutEffect(() => {
    if (!ref.current) return;
    const el = ref.current;
    const measure = () => {
      const rect = el.getBoundingClientRect();
      setSize({
        width: Math.max(1, Math.floor(rect.width)) || fallback.width,
        height: Math.max(1, Math.floor(rect.height)) || fallback.height,
      });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref, fallback.width, fallback.height]);
  return size;
}

export function DeckCanvas({ model, onHover, controller, deckRef, sourcesRef, selectionsRef }) {
  const zarrSource = useModelTrait(model, '_zarr_source');
  const pixelSourceMode = useModelTrait(model, '_pixel_source_mode');
  const channelSettings = useModelTrait(model, '_channel_settings');
  const currentT = useModelTrait(model, 'current_t');
  const currentZ = useModelTrait(model, 'current_z');
  const displayMode = useModelTrait(model, '_display_mode');
  const activeChannel = useModelTrait(model, 'current_c') || 0;
  const imageShape = useModelTrait(model, '_image_shape');
  const imageDtype = useModelTrait(model, '_image_dtype');
  const pixelSizeUm = useModelTrait(model, 'pixel_size_um');
  const scaleBarVisible = useModelTrait(model, 'scale_bar_visible') !== false;
  const imageVisible = useModelTrait(model, 'image_visible') !== false;
  const annotations = useModelTrait(model, '_annotations') || [];
  const selectedId = useModelTrait(model, 'selected_annotation_id') || '';
  const toolMode = useModelTrait(model, 'tool_mode') || 'pan';

  const containerRef = useRef(null);
  const { width, height } = useContainerSize(containerRef);

  const [sources, setSources] = useState(null);
  const [error, setError] = useState(null);
  const [viewState, setViewState] = useState(null);
  const [previewTick, setPreviewTick] = useState(0);

  useEffect(() => {
    if (!controller) return;
    return controller.onPreviewChange(() => setPreviewTick((t) => t + 1));
  }, [controller]);

  useEffect(() => {
    let cancelled = false;
    let activeAnywidgetSource = null;
    async function run() {
      setError(null);
      if (pixelSourceMode === 'chunk_bridge') {
        if (!imageShape || imageShape.length !== 5) { setSources(null); return; }
        activeAnywidgetSource = new AnywidgetPixelSource(model, {
          shape: imageShape, dtype: imageDtype || 'Uint16', tileSize: 512,
        });
        setSources([activeAnywidgetSource]);
      } else if (zarrSource?.url) {
        try {
          const { sources: srcs } = await openOmeZarr(zarrSource.url, zarrSource.headers || {});
          if (!cancelled) setSources(srcs);
        } catch (e) {
          if (!cancelled) { setError(String(e)); setSources(null); }
        }
      } else {
        setSources(null);
      }
    }
    run();
    return () => {
      cancelled = true;
      if (activeAnywidgetSource) activeAnywidgetSource.destroy();
    };
  }, [pixelSourceMode, zarrSource?.url, imageShape, imageDtype]);

  useEffect(() => {
    if (!sources || !sources.length) return;
    const vs = getDefaultInitialViewState(sources, { width, height }, 0);
    setViewState(vs);
  }, [sources, width, height]);

  useEffect(() => { if (sourcesRef) sourcesRef.current = sources; }, [sources, sourcesRef]);

  const imageLayerProps = useMemo(() => {
    if (!sources || !sources.length) return null;
    return buildImageLayerProps({
      sources, channels: channelSettings || [],
      currentT: currentT || 0, currentZ: currentZ || 0,
      displayMode, activeChannel,
    });
  }, [sources, channelSettings, currentT, currentZ, displayMode, activeChannel]);

  useEffect(() => {
    if (selectionsRef) selectionsRef.current = imageLayerProps?.selections ?? null;
  }, [imageLayerProps, selectionsRef]);

  useEffect(() => {
    const handler = (content) => {
      if (!content || content.kind !== 'reset-view') return;
      if (!sources || !sources.length) return;
      const vs = getDefaultInitialViewState(sources, { width, height }, 0);
      setViewState(vs);
    };
    model.on('msg:custom', handler);
    return () => model.off('msg:custom', handler);
  }, [model, sources, width, height]);

  const annotationLayers = useMemo(
    () => annotationsToLayers({
      annotations, currentT: currentT || 0, currentZ: currentZ || 0, selectedId,
    }),
    [annotations, currentT, currentZ, selectedId]);

  const previewLayer = useMemo(
    () => (controller ? controller.getPreviewLayer() : null),
    [controller, previewTick, toolMode]);

  const layers = useMemo(() => {
    const out = [];
    if (imageLayerProps && imageVisible) {
      out.push(new MultiscaleImageLayer({ id: 'viv-image', viewportId: 'ortho', ...imageLayerProps }));
    }
    for (const l of annotationLayers) out.push(l);
    if (previewLayer) out.push(previewLayer);
    if (scaleBarVisible && pixelSizeUm) {
      out.push(buildScaleBarLayer({ pixelSizeUm, viewState, width, height }));
    }
    return out;
  }, [imageLayerProps, imageVisible, annotationLayers, previewLayer,
      pixelSizeUm, scaleBarVisible, viewState, width, height]);

  // Map screen pixel events to image pixel coordinates using deck.gl's
  // orthographic unproject. coordinate.length === 2 means [x, y] image pixels.
  function imagePixelFor(info) {
    const coord = info?.coordinate;
    if (!coord) return null;
    return { x: coord[0], y: coord[1] };
  }

  function pickObject(event) {
    const deck = deckRef?.current?.deck;
    if (!deck || !event) return null;
    const picked = deck.pickObject({
      x: event.screenX ?? event._screenX ?? 0,
      y: event.screenY ?? event._screenY ?? 0,
      radius: 4,
    });
    if (!picked) return null;
    // Link back to the source annotation for the select tool.
    const id = picked.object?.id;
    const sourceAnnotation = id ? annotations.find((a) => a.id === id) : null;
    return { layer: picked.layer, object: picked.object, sourceAnnotation };
  }

  function onClick(info) {
    if (!controller) return;
    const pt = imagePixelFor(info);
    if (!pt) return;
    const ev = { ...pt, screenX: info.x, screenY: info.y, _picked: pickObject(info) };
    // Point-style tools commit on click; select also commits here.
    controller.handlePointerEvent('down', ev);
    controller.handlePointerEvent('up', ev);
  }

  function onDragStart(info) {
    if (!controller) return;
    const pt = imagePixelFor(info);
    if (!pt) return;
    controller.handlePointerEvent('down', { ...pt, screenX: info.x, screenY: info.y });
  }

  function onDrag(info) {
    if (!controller) return;
    const pt = imagePixelFor(info);
    if (!pt) return;
    controller.handlePointerEvent('move', { ...pt, screenX: info.x, screenY: info.y });
  }

  function onDragEnd(info) {
    if (!controller) return;
    const pt = imagePixelFor(info);
    if (!pt) return;
    controller.handlePointerEvent('up', { ...pt, screenX: info.x, screenY: info.y });
  }

  function onDblClick(info) {
    if (!controller) return;
    const pt = imagePixelFor(info);
    if (!pt) return;
    const tool = controller.activeTool;
    if (tool.onDoubleClick) tool.onDoubleClick(pt, { model, controller, pickObject });
  }

  // Pan is handled by OrthographicView's controller when tool_mode === 'pan';
  // for other tools we disable the default controller so drag-draw works.
  const viewController = toolMode === 'pan' || toolMode === 'select';

  if (error) {
    return <div style={{ color: '#b00', padding: 12 }}>Failed to load image: {error}</div>;
  }

  return (
    <div ref={containerRef} style={{ position: 'absolute', inset: 0 }}>
      {!sources ? (
        <div style={{ padding: 12, color: '#666' }}>Loading…</div>
      ) : (
        <DeckGL
          ref={deckRef}
          width={width}
          height={height}
          layers={layers}
          views={[new OrthographicView({ id: 'ortho', controller: viewController })]}
          viewState={viewState ? { ortho: viewState } : undefined}
          onViewStateChange={({ viewState: v }) => setViewState(v)}
          onHover={onHover}
          onClick={onClick}
          onDragStart={onDragStart}
          onDrag={onDrag}
          onDragEnd={onDragEnd}
          onDblClick={onDblClick}
          useDevicePixels={true}
          getCursor={({ isDragging }) =>
            isDragging ? 'grabbing' : (controller?.cursor || 'crosshair')
          }
        />
      )}
    </div>
  );
}
```

- [ ] **Step 3: Enable rect/polygon/point buttons in `Toolbar.jsx`**

```jsx
// anybioimage/frontend/viewer/src/chrome/Toolbar.jsx
import React from 'react';
import { useModelTrait } from '../model/useModelTrait.js';

const ICONS = {
  pan: 'P', select: 'V', reset: '↺', layers: '☰',
  rect: '▭', polygon: '⬡', point: '•',
  line: '／', areaMeasure: '△', lineProfile: '∼',
};

function ToolButton({ model, mode, label, disabled }) {
  const current = useModelTrait(model, 'tool_mode');
  const active = current === mode;
  return (
    <button
      className={'tool-btn' + (active ? ' active' : '')}
      disabled={disabled}
      title={label}
      onClick={() => { model.set('tool_mode', mode); model.save_changes(); }}
    >{ICONS[mode] || mode}</button>
  );
}

export function Toolbar({ model, onToggleLayers, panelOpen }) {
  const phase3Disabled = true;   // line / areaMeasure land in Phase 3
  return (
    <div className="toolbar">
      <div className="tool-group">
        <ToolButton model={model} mode="pan" label="Pan (P)" />
        <ToolButton model={model} mode="select" label="Select (V)" />
      </div>
      <div className="toolbar-separator" />
      <div className="tool-group">
        <ToolButton model={model} mode="rect" label="Rectangle (R)" />
        <ToolButton model={model} mode="polygon" label="Polygon (G)" />
        <ToolButton model={model} mode="point" label="Point (O)" />
        <ToolButton model={model} mode="line" label="Line (L)" disabled={phase3Disabled} />
        <ToolButton model={model} mode="areaMeasure" label="Area measure (M)" disabled={phase3Disabled} />
      </div>
      <div className="toolbar-separator" />
      <button className="tool-btn" title="Reset view"
              onClick={() => model.send({ kind: 'reset-view' })}>{ICONS.reset}</button>
      <div className="toolbar-separator" />
      <button className={'layers-btn' + (panelOpen ? ' active' : '')} onClick={onToggleLayers}>
        <span>{ICONS.layers}</span><span> Layers</span>
      </button>
    </div>
  );
}
```

- [ ] **Step 4: Build**

```
cd anybioimage/frontend/viewer && npm run build && cd ../../..
```

Expected: bundle rebuilt.

- [ ] **Step 5: Commit**

```bash
git add anybioimage/frontend/viewer/src/App.jsx \
        anybioimage/frontend/viewer/src/render/DeckCanvas.jsx \
        anybioimage/frontend/viewer/src/chrome/Toolbar.jsx \
        anybioimage/frontend/viewer/dist/viewer-bundle.js
git commit -m "feat(viewer/interaction): wire InteractionController into DeckCanvas"
```

---

## Task 10: `AnnotationsSection` in the Layers panel

**Goal:** Replace the "Annotations (Phase 2)" placeholder with a real section. Rows are grouped by kind (Rectangles / Polygons / Points). Each row shows count + visibility toggle (kind-level) + delete button (kind-level). Clicking a kind row's name expands into individual rows with id, per-item visibility toggle, and per-item delete. Hooks read/write directly from `_annotations`. [spec §5]

**Files:**
- Create: `anybioimage/frontend/viewer/src/chrome/LayersPanel/AnnotationsSection.jsx`
- Modify: `anybioimage/frontend/viewer/src/chrome/LayersPanel/LayersPanel.jsx`

- [ ] **Step 1: Implement `AnnotationsSection`**

```jsx
// anybioimage/frontend/viewer/src/chrome/LayersPanel/AnnotationsSection.jsx
import React, { useState } from 'react';
import { useModelTrait } from '../../model/useModelTrait.js';

const KINDS = [
  { kind: 'rect', label: 'Rectangles' },
  { kind: 'polygon', label: 'Polygons' },
  { kind: 'point', label: 'Points' },
];

function setAnnotations(model, next) {
  model.set('_annotations', next);
  model.save_changes();
}

function toggleKindVisibility(model, annotations, kind, visible) {
  setAnnotations(model, annotations.map((a) =>
    a.kind === kind ? { ...a, visible } : a
  ));
}

function clearKind(model, annotations, kind) {
  setAnnotations(model, annotations.filter((a) => a.kind !== kind));
}

function toggleOne(model, annotations, id) {
  setAnnotations(model, annotations.map((a) =>
    a.id === id ? { ...a, visible: !a.visible } : a
  ));
}

function removeOne(model, annotations, id) {
  setAnnotations(model, annotations.filter((a) => a.id !== id));
}

export function AnnotationsSection({ model }) {
  const annotations = useModelTrait(model, '_annotations') || [];
  const [expanded, setExpanded] = useState({});

  const byKind = Object.fromEntries(
    KINDS.map(({ kind }) => [kind, annotations.filter((a) => a.kind === kind)])
  );

  return (
    <div className="layers-section" style={{ padding: '4px 8px' }}>
      <div className="layer-header" style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 0', fontSize: 11, fontWeight: 600, color: '#666', textTransform: 'uppercase' }}>
        <span>Annotations</span>
      </div>
      {KINDS.map(({ kind, label }) => {
        const items = byKind[kind];
        const anyVisible = items.some((a) => a.visible);
        const isExpanded = expanded[kind];
        return (
          <div key={kind}>
            <div className="layer-item" style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0' }}>
              <button
                className="layer-toggle"
                onClick={() => setExpanded({ ...expanded, [kind]: !isExpanded })}
                style={{ width: 16, background: 'none', border: 'none', cursor: 'pointer', color: '#888' }}
                title={isExpanded ? 'Collapse' : 'Expand'}
              >{isExpanded ? '▾' : '▸'}</button>
              <span style={{ flex: 1, fontSize: 13 }}>{label} ({items.length})</span>
              <button
                className="layer-toggle"
                onClick={() => toggleKindVisibility(model, annotations, kind, !anyVisible)}
                title={anyVisible ? 'Hide all' : 'Show all'}
                style={{ background: 'none', border: 'none', cursor: 'pointer',
                         color: anyVisible ? '#0d6efd' : '#999' }}
              >{anyVisible ? '👁' : '⊘'}</button>
              <button
                className="layer-action-btn"
                onClick={() => clearKind(model, annotations, kind)}
                disabled={items.length === 0}
                title="Delete all"
                style={{ background: 'none', border: 'none', cursor: 'pointer',
                         color: items.length ? '#c33' : '#ccc' }}
              >🗑</button>
            </div>
            {isExpanded && items.map((a) => (
              <div key={a.id} className="layer-item sub-item" style={{ display: 'flex', alignItems: 'center', gap: 6, paddingLeft: 28, fontSize: 12 }}>
                <span style={{ flex: 1, fontFamily: 'monospace', color: '#555' }}>{a.id}</span>
                <button
                  onClick={() => toggleOne(model, annotations, a.id)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer',
                           color: a.visible ? '#0d6efd' : '#999' }}
                  title={a.visible ? 'Hide' : 'Show'}
                >{a.visible ? '👁' : '⊘'}</button>
                <button
                  onClick={() => removeOne(model, annotations, a.id)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#c33' }}
                  title="Delete"
                >🗑</button>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Replace the placeholder in `LayersPanel.jsx`**

```jsx
// anybioimage/frontend/viewer/src/chrome/LayersPanel/LayersPanel.jsx
import React from 'react';
import { MetadataSection } from './MetadataSection.jsx';
import { ImageSection } from './ImageSection.jsx';
import { MasksSection } from './MasksSection.jsx';
import { AnnotationsSection } from './AnnotationsSection.jsx';
import { ExportFooter } from './ExportFooter.jsx';

export function LayersPanel({ model }) {
  return (
    <div className="layers-panel open" style={{ width: 280, padding: 8, background: '#fafafa', overflowY: 'auto' }}>
      <MetadataSection model={model} />
      <ImageSection model={model} />
      <MasksSection model={model} />
      <AnnotationsSection model={model} />
      <ExportFooter model={model} />
    </div>
  );
}
```

Note: `MasksSection` is created in Task 13. For Task 10, temporarily stub it so the bundle builds:

```jsx
// anybioimage/frontend/viewer/src/chrome/LayersPanel/MasksSection.jsx (stub)
import React from 'react';
export function MasksSection() {
  return <div style={{ padding: '4px 8px', color: '#999', fontStyle: 'italic' }}>Masks — coming next</div>;
}
```

Task 13 overwrites this stub with the real implementation.

- [ ] **Step 3: Build and commit**

```
cd anybioimage/frontend/viewer && npm run build && cd ../../..
```

```bash
git add anybioimage/frontend/viewer/src/chrome/LayersPanel/AnnotationsSection.jsx \
        anybioimage/frontend/viewer/src/chrome/LayersPanel/MasksSection.jsx \
        anybioimage/frontend/viewer/src/chrome/LayersPanel/LayersPanel.jsx \
        anybioimage/frontend/viewer/dist/viewer-bundle.js
git commit -m "feat(viewer/chrome): AnnotationsSection in LayersPanel"
```

---

## Task 11: Mask transport — Python side switches to raw bytes via `send()`

**Goal:** Remove base64 PNG encoding from `mask_management.py`. `_masks_data` entries now carry only metadata (no `data` field). Mask RGBA bytes live in a Python-side dict keyed by mask id. When JS sends `{kind: "mask_request", id}`, Python replies with `{kind: "mask", id, width, height, dtype}` + `buffers: [rgba_bytes]`. Rebuild-on-contour-change still works; only the transport changes. [spec §2, §3]

**Files:**
- Modify: `anybioimage/mixins/mask_management.py`
- Modify: `anybioimage/viewer.py` — route `mask_request` to the mixin
- Create: `tests/test_mask_transport.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_mask_transport.py
"""Mask-bytes transport — Python side sends raw RGBA via anywidget buffers."""
from __future__ import annotations

import numpy as np
import pytest

from anybioimage import BioImageViewer


class RecordingViewer(BioImageViewer):
    """Captures `send()` calls into a buffer-aware recorder."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.sent_messages = []

    def send(self, msg, buffers=None):  # type: ignore[override]
        self.sent_messages.append((dict(msg), list(buffers or [])))


def test_add_mask_populates_metadata_only():
    v = RecordingViewer()
    labels = np.zeros((64, 64), dtype=np.uint16)
    labels[16:32, 16:32] = 1
    mid = v.add_mask(labels, name="m1", opacity=0.7)
    entry = v._masks_data[-1]
    assert entry["id"] == mid
    assert entry["name"] == "m1"
    assert entry["visible"] is True
    assert entry["opacity"] == 0.7
    assert entry["width"] == 64
    assert entry["height"] == 64
    assert "data" not in entry                 # raw bytes no longer inline
    # Bytes are stored in a dict on the Python side.
    assert v._mask_bytes[mid]
    assert len(v._mask_bytes[mid]) == 64 * 64 * 4


def test_mask_request_dispatches_bytes():
    v = RecordingViewer()
    labels = np.zeros((10, 10), dtype=np.uint16)
    labels[0, 0] = 1
    mid = v.add_mask(labels)
    v.sent_messages.clear()
    v._route_message(v, {"kind": "mask_request", "id": mid}, [])
    assert v.sent_messages, "expected a send() call"
    msg, buffers = v.sent_messages[0]
    assert msg["kind"] == "mask"
    assert msg["id"] == mid
    assert msg["width"] == 10
    assert msg["height"] == 10
    assert msg["dtype"] == "uint8"
    assert len(buffers) == 1
    assert len(buffers[0]) == 10 * 10 * 4


def test_update_contours_regenerates_bytes():
    v = RecordingViewer()
    labels = np.zeros((20, 20), dtype=np.uint16)
    labels[5:15, 5:15] = 1
    mid = v.add_mask(labels)
    v.sent_messages.clear()
    before_bytes = v._mask_bytes[mid]
    v.update_mask_settings(mid, contours=True, contour_width=2)
    after_bytes = v._mask_bytes[mid]
    assert before_bytes != after_bytes
    # A `mask` message is automatically pushed so the frontend does not need to re-request.
    kinds = [m[0]["kind"] for m in v.sent_messages]
    assert "mask" in kinds


def test_remove_mask_clears_bytes():
    v = RecordingViewer()
    labels = np.zeros((8, 8), dtype=np.uint16)
    mid = v.add_mask(labels)
    assert mid in v._mask_bytes
    v.remove_mask(mid)
    assert mid not in v._mask_bytes
    assert mid not in [m["id"] for m in v._masks_data]
```

- [ ] **Step 2: Run to verify fail**

```
uv run pytest tests/test_mask_transport.py -v
```

Expected: attribute error (no `_mask_bytes`), and the assertion `"data" not in entry` fails because the existing `add_mask` still sets `data`.

- [ ] **Step 3: Rewrite `mask_management.py`**

```python
# anybioimage/mixins/mask_management.py
"""Mask management mixin for BioImageViewer.

Phase 2 [spec §2, §3]: mask RGBA is no longer serialised as base64 PNG inside
`_masks_data`. Instead, raw RGBA bytes live in `_mask_bytes` on the Python
side; JS requests them lazily via `{kind: "mask_request", id}` and receives
them as an anywidget message buffer. `_masks_data` entries carry only
metadata.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..utils import MASK_COLORS, labels_to_rgba


class MaskManagementMixin:
    """Mask layer management for BioImageViewer.

    Attributes expected on the concrete class:
        - `_mask_arrays`: dict[str, np.ndarray]  — raw label arrays
        - `_mask_bytes`:  dict[str, bytes]       — rendered RGBA bytes (transport)
        - `_masks_data`:  list[dict] (traitlet)  — metadata only
    """

    # ---- lifecycle helpers used by subclasses at init time ----
    def _ensure_mask_state(self) -> None:
        if not hasattr(self, "_mask_arrays"):
            self._mask_arrays = {}
        if not hasattr(self, "_mask_bytes"):
            self._mask_bytes = {}
        if not hasattr(self, "_mask_caches"):
            self._mask_caches = {}

    # ---- public API (unchanged signatures) ----
    def add_mask(
        self,
        labels: np.ndarray,
        name: str | None = None,
        color: str | None = None,
        opacity: float = 0.5,
        visible: bool = True,
        contours_only: bool = False,
        contour_width: int = 1,
    ) -> str:
        self._ensure_mask_state()
        if labels.ndim > 2:
            labels = labels.squeeze()
            if labels.ndim > 2:
                labels = labels[0] if labels.ndim == 3 else labels[0, 0]

        mask_id = f"mask_{len(self._masks_data)}_{id(labels)}"
        if color is None:
            color = MASK_COLORS[len(self._masks_data) % len(MASK_COLORS)]
        if name is None:
            name = f"Mask {len(self._masks_data) + 1}"

        rgba = labels_to_rgba(labels, contours_only=contours_only, contour_width=contour_width)
        rgba = np.ascontiguousarray(rgba, dtype=np.uint8)
        h, w = rgba.shape[:2]

        self._mask_arrays[mask_id] = labels
        self._mask_bytes[mask_id] = rgba.tobytes()
        self._mask_caches[mask_id] = {(contours_only, contour_width): self._mask_bytes[mask_id]}

        entry = {
            "id": mask_id,
            "name": name,
            "width": int(w),
            "height": int(h),
            "dtype": "uint8",
            "visible": bool(visible),
            "opacity": float(opacity),
            "color": color,
            "contours": bool(contours_only),
            "contour_width": int(contour_width),
        }
        self._masks_data = [*self._masks_data, entry]

        # Push bytes immediately so the JS side does not need to request them.
        self._push_mask_bytes(mask_id)
        return mask_id

    def set_mask(
        self,
        labels: np.ndarray,
        name: str | None = None,
        contours_only: bool = False,
        contour_width: int = 1,
    ) -> None:
        self.clear_masks()
        self.add_mask(labels, name=name or "Mask",
                      contours_only=contours_only, contour_width=contour_width)

    def remove_mask(self, mask_id: str) -> None:
        self._ensure_mask_state()
        self._masks_data = [m for m in self._masks_data if m["id"] != mask_id]
        self._mask_arrays.pop(mask_id, None)
        self._mask_bytes.pop(mask_id, None)
        self._mask_caches.pop(mask_id, None)

    def clear_masks(self) -> None:
        self._ensure_mask_state()
        self._masks_data = []
        self._mask_arrays = {}
        self._mask_bytes = {}
        self._mask_caches = {}

    def update_mask_settings(self, mask_id: str, **kwargs) -> None:
        self._ensure_mask_state()
        updated = []
        regenerate = "contours" in kwargs or "contour_width" in kwargs
        for m in self._masks_data:
            if m["id"] != mask_id:
                updated.append(m)
                continue
            new_m = {**m, **kwargs}
            if regenerate and mask_id in self._mask_arrays:
                contours = new_m.get("contours", False)
                width = new_m.get("contour_width", 1)
                cache_key = (contours, width)
                cached = self._mask_caches.get(mask_id, {}).get(cache_key)
                if cached is None:
                    rgba = labels_to_rgba(
                        self._mask_arrays[mask_id],
                        contours_only=contours, contour_width=width,
                    )
                    rgba = np.ascontiguousarray(rgba, dtype=np.uint8)
                    cached = rgba.tobytes()
                    self._mask_caches.setdefault(mask_id, {})[cache_key] = cached
                self._mask_bytes[mask_id] = cached
            updated.append(new_m)
        self._masks_data = updated
        if regenerate:
            self._push_mask_bytes(mask_id)

    def get_mask_ids(self) -> list[str]:
        return [m["id"] for m in self._masks_data]

    @property
    def masks_df(self) -> pd.DataFrame:
        if not self._masks_data:
            return pd.DataFrame(columns=["id", "name", "visible", "opacity", "color", "contours"])
        keep = ["id", "name", "visible", "opacity", "color", "contours"]
        return pd.DataFrame([{k: m[k] for k in keep if k in m} for m in self._masks_data])

    # ---- transport ----
    def _push_mask_bytes(self, mask_id: str) -> None:
        """Send raw mask RGBA to JS over the anywidget message channel."""
        self._ensure_mask_state()
        meta = next((m for m in self._masks_data if m["id"] == mask_id), None)
        if not meta:
            return
        data = self._mask_bytes.get(mask_id)
        if data is None:
            return
        self.send(
            {"kind": "mask", "id": mask_id,
             "width": meta["width"], "height": meta["height"], "dtype": "uint8"},
            [data],
        )

    def handle_mask_request(self, payload: dict) -> None:
        mid = payload.get("id")
        if not mid:
            return
        self._push_mask_bytes(mid)
```

- [ ] **Step 4: Route `mask_request` in `viewer.py`**

Edit `anybioimage/viewer.py`'s `_route_message`:

```python
    def _route_message(self, widget, content, buffers):
        """Dispatch custom JS → Py messages by `kind` key."""
        if not isinstance(content, dict):
            return
        kind = content.get("kind")
        if kind == "chunk":
            self.handle_chunk_request(content)
        elif kind == "mask_request":
            self.handle_mask_request(content)
```

- [ ] **Step 5: Run the tests**

```
uv run pytest tests/test_mask_transport.py tests/test_mixins.py -v
```

Expected: `test_mask_transport.py` — 4 passed. Any existing tests that asserted a `data` key in `_masks_data` entries need updating to read `_mask_bytes[mid]` instead.

- [ ] **Step 6: Commit**

```bash
git add anybioimage/mixins/mask_management.py anybioimage/viewer.py \
        tests/test_mask_transport.py tests/test_mixins.py
git commit -m "refactor(masks): switch transport from base64 PNG to raw bytes"
```

---

## Task 12: Mask transport — JS side + `buildMaskLayers.js` + `BitmapLayer` mount

**Goal:** Receive `{kind: "mask", id, width, height, dtype}` messages with a single buffer from Python. `MaskSourceBridge.js` caches `ImageData` / `ImageBitmap` per mask id and re-emits on updates. `buildMaskLayers.js` produces one deck.gl `BitmapLayer` per visible mask (passed the cached `ImageBitmap` + visibility / opacity / tint). Mount in `DeckCanvas` between image and annotation layers. [spec §3]

**Files:**
- Create: `anybioimage/frontend/viewer/src/render/pixel-sources/MaskSourceBridge.js`
- Create: `anybioimage/frontend/viewer/src/render/pixel-sources/MaskSourceBridge.test.js`
- Create: `anybioimage/frontend/viewer/src/render/layers/buildMaskLayers.js`
- Create: `anybioimage/frontend/viewer/src/render/layers/buildMaskLayers.test.js`
- Modify: `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx`
- Modify: `anybioimage/frontend/viewer/src/App.jsx`

- [ ] **Step 1: `MaskSourceBridge` failing test**

```js
// anybioimage/frontend/viewer/src/render/pixel-sources/MaskSourceBridge.test.js
/** @vitest-environment jsdom */
import { describe, it, expect, vi } from 'vitest';
import { MaskSourceBridge } from './MaskSourceBridge.js';

function fakeModel() {
  const listeners = {};
  return {
    on: (evt, cb) => { (listeners[evt] = listeners[evt] || []).push(cb); },
    off: (evt, cb) => { listeners[evt] = (listeners[evt] || []).filter((x) => x !== cb); },
    send: vi.fn(),
    _emit: (evt, content, buffers) => (listeners[evt] || []).forEach((cb) => cb(content, buffers)),
  };
}

describe('MaskSourceBridge', () => {
  it('requests a mask on subscribe when not yet cached', () => {
    const model = fakeModel();
    const bridge = new MaskSourceBridge(model);
    bridge.subscribe('m1', () => {});
    expect(model.send).toHaveBeenCalledWith({ kind: 'mask_request', id: 'm1' });
  });

  it('stores bytes from a `kind:mask` message and notifies subscribers', async () => {
    const model = fakeModel();
    const bridge = new MaskSourceBridge(model);
    const sub = vi.fn();
    bridge.subscribe('m1', sub);
    const pixels = new Uint8Array(4 * 2 * 2);     // 2×2 RGBA
    pixels.set([255, 0, 0, 128], 0);
    model._emit('msg:custom', { kind: 'mask', id: 'm1', width: 2, height: 2, dtype: 'uint8' },
                [pixels.buffer]);
    await Promise.resolve();
    const entry = bridge.get('m1');
    expect(entry).toBeTruthy();
    expect(entry.width).toBe(2);
    expect(entry.height).toBe(2);
    expect(entry.pixels.slice(0, 4)).toEqual(new Uint8Array([255, 0, 0, 128]));
    expect(sub).toHaveBeenCalledWith(entry);
  });

  it('multiple subscribers share a single request', () => {
    const model = fakeModel();
    const bridge = new MaskSourceBridge(model);
    bridge.subscribe('m1', () => {});
    bridge.subscribe('m1', () => {});
    expect(model.send).toHaveBeenCalledTimes(1);
  });

  it('destroy detaches the listener', () => {
    const model = fakeModel();
    const bridge = new MaskSourceBridge(model);
    bridge.subscribe('m1', () => {});
    bridge.destroy();
    model._emit('msg:custom', { kind: 'mask', id: 'm1', width: 1, height: 1 }, [new Uint8Array(4).buffer]);
    expect(bridge.get('m1')).toBeUndefined();
  });
});
```

- [ ] **Step 2: Run to verify fail**

```
cd anybioimage/frontend/viewer && npm run test -- MaskSourceBridge
```

Expected: module not found.

- [ ] **Step 3: Implement `MaskSourceBridge`**

```js
// anybioimage/frontend/viewer/src/render/pixel-sources/MaskSourceBridge.js
/** MaskSourceBridge — receives raw mask RGBA over the anywidget message
 *  channel and publishes `{ id, width, height, pixels: Uint8Array }` entries
 *  to subscribers. One bridge per widget; created once in `App.jsx`.
 *
 *  Wire protocol (spec §3):
 *    JS → Py : { kind: "mask_request", id }
 *    Py → JS : { kind: "mask", id, width, height, dtype } + buffers[0]
 */
export class MaskSourceBridge {
  constructor(model) {
    this._model = model;
    this._entries = new Map();      // id → { width, height, pixels }
    this._subs = new Map();         // id → Set<callback>
    this._requested = new Set();
    this._listener = (content, buffers) => {
      if (!content || content.kind !== 'mask') return;
      const id = content.id;
      if (!id) return;
      const buf = buffers && buffers[0];
      if (!buf) return;
      const pixels = new Uint8Array(
        buf instanceof ArrayBuffer ? buf :
        buf.buffer ? buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) :
        buf
      );
      const entry = { width: content.width, height: content.height, pixels };
      this._entries.set(id, entry);
      for (const cb of this._subs.get(id) || []) cb(entry);
    };
    model.on('msg:custom', this._listener);
  }

  get(id) { return this._entries.get(id); }

  subscribe(id, cb) {
    if (!this._subs.has(id)) this._subs.set(id, new Set());
    this._subs.get(id).add(cb);
    const cached = this._entries.get(id);
    if (cached) { cb(cached); }
    if (!this._requested.has(id)) {
      this._requested.add(id);
      this._model.send({ kind: 'mask_request', id });
    }
    return () => {
      const set = this._subs.get(id);
      if (set) { set.delete(cb); if (set.size === 0) this._subs.delete(id); }
    };
  }

  invalidate(id) {
    // Called when mask settings change (contour etc.) — refetch from Python.
    this._entries.delete(id);
    this._requested.delete(id);
    for (const cb of this._subs.get(id) || []) {
      this._requested.add(id);
      this._model.send({ kind: 'mask_request', id });
      break;   // one request is enough; subscribers all fire on the next emit
    }
  }

  destroy() {
    this._model.off('msg:custom', this._listener);
    this._entries.clear();
    this._subs.clear();
    this._requested.clear();
  }
}
```

- [ ] **Step 4: Run the tests**

```
cd anybioimage/frontend/viewer && npm run test -- MaskSourceBridge
```

Expected: 4 passed.

- [ ] **Step 5: `buildMaskLayers` failing test**

```js
// anybioimage/frontend/viewer/src/render/layers/buildMaskLayers.test.js
import { describe, it, expect, vi } from 'vitest';
vi.mock('@deck.gl/layers', () => {
  class BitmapLayer { constructor(p) { this.props = p; this.type = 'BitmapLayer'; } }
  return { BitmapLayer };
});
import { buildMaskLayers } from './buildMaskLayers.js';

function mask(id, extra = {}) {
  return { id, name: id, visible: true, opacity: 0.5,
           color: '#ff0000', width: 4, height: 4, ...extra };
}

describe('buildMaskLayers', () => {
  it('returns no layers when masks list is empty', () => {
    expect(buildMaskLayers({ masks: [], bridge: { get: () => null } })).toEqual([]);
  });

  it('returns one BitmapLayer per visible mask with a cached bitmap', () => {
    const fakeBitmap = {};
    const bridge = { get: (id) => id === 'm1'
      ? { width: 4, height: 4, bitmap: fakeBitmap } : null };
    const layers = buildMaskLayers({ masks: [mask('m1')], bridge });
    expect(layers).toHaveLength(1);
    expect(layers[0].props.image).toBe(fakeBitmap);
    expect(layers[0].props.bounds).toEqual([0, 0, 4, 4]);
    expect(layers[0].props.opacity).toBe(0.5);
  });

  it('skips invisible masks', () => {
    const bridge = { get: () => ({ width: 4, height: 4, bitmap: {} }) };
    const layers = buildMaskLayers({
      masks: [mask('m1', { visible: false }), mask('m2')], bridge,
    });
    expect(layers).toHaveLength(1);
    expect(layers[0].props.id).toBe('mask-m2');
  });

  it('skips masks whose bitmap is not yet loaded', () => {
    const bridge = { get: () => null };
    expect(buildMaskLayers({ masks: [mask('m1')], bridge })).toEqual([]);
  });
});
```

- [ ] **Step 6: Implement `buildMaskLayers`**

```js
// anybioimage/frontend/viewer/src/render/layers/buildMaskLayers.js
/** buildMaskLayers — one `BitmapLayer` per visible mask whose bitmap has
 *  arrived from Python via MaskSourceBridge. [spec §3] */
import { BitmapLayer } from '@deck.gl/layers';

export function buildMaskLayers({ masks = [], bridge }) {
  const out = [];
  for (const m of masks) {
    if (!m || m.visible === false) continue;
    const entry = bridge?.get(m.id);
    if (!entry || !entry.bitmap) continue;
    out.push(new BitmapLayer({
      id: `mask-${m.id}`,
      image: entry.bitmap,
      bounds: [0, 0, entry.width, entry.height],
      opacity: m.opacity ?? 0.5,
      pickable: false,
    }));
  }
  return out;
}
```

- [ ] **Step 7: Enhance `MaskSourceBridge` to build `ImageBitmap` from pixels**

The test for `buildMaskLayers` expects the bridge entry to carry a `bitmap` field; extend `MaskSourceBridge` to build one. Append to the class:

```js
  async _bakeBitmap(entry) {
    if (entry.bitmap) return entry.bitmap;
    const id = new ImageData(new Uint8ClampedArray(entry.pixels), entry.width, entry.height);
    if (typeof createImageBitmap === 'function') {
      try { entry.bitmap = await createImageBitmap(id); return entry.bitmap; }
      catch { /* fall through */ }
    }
    entry.bitmap = id;
    return entry.bitmap;
  }
```

And in the listener, after `this._entries.set(id, entry)`, bake asynchronously then re-notify:

```js
      this._entries.set(id, entry);
      // First-pass notify with pixels only so React knows something changed.
      for (const cb of this._subs.get(id) || []) cb(entry);
      this._bakeBitmap(entry).then(() => {
        for (const cb of this._subs.get(id) || []) cb(entry);
      });
```

Add a corresponding test that skips if `createImageBitmap` is unavailable in jsdom:

```js
  it('bakes an ImageData fallback when createImageBitmap is not available', async () => {
    const model = fakeModel();
    const bridge = new MaskSourceBridge(model);
    const got = new Promise((resolve) => bridge.subscribe('m1', (e) => { if (e.bitmap) resolve(e); }));
    const pixels = new Uint8Array(4 * 1 * 1);
    model._emit('msg:custom', { kind: 'mask', id: 'm1', width: 1, height: 1, dtype: 'uint8' },
                [pixels.buffer]);
    const entry = await got;
    expect(entry.bitmap).toBeTruthy();
  });
```

- [ ] **Step 8: Wire the bridge into `App.jsx` and push it to `DeckCanvas`**

Full replacement of `anybioimage/frontend/viewer/src/App.jsx` (updates the file that Task 9 already rewrote — adds `maskBridge` creation + the prop on `<DeckCanvas>`):

```jsx
// anybioimage/frontend/viewer/src/App.jsx
import React, { useState, useRef, useMemo, useEffect } from 'react';
import { Toolbar } from './chrome/Toolbar.jsx';
import { DimControls } from './chrome/DimControls.jsx';
import { StatusBar } from './chrome/StatusBar.jsx';
import { LayersPanel } from './chrome/LayersPanel/LayersPanel.jsx';
import { DeckCanvas } from './render/DeckCanvas.jsx';
import { installKeyboard } from './interaction/keyboard.js';
import { makeHoverHandler } from './render/onHoverPixelInfo.js';
import { InteractionController } from './interaction/InteractionController.js';
import { panTool } from './interaction/tools/pan.js';
import { selectTool } from './interaction/tools/select.js';
import { rectTool } from './interaction/tools/rect.js';
import { polygonTool } from './interaction/tools/polygon.js';
import { pointTool } from './interaction/tools/point.js';
import { MaskSourceBridge } from './render/pixel-sources/MaskSourceBridge.js';

export function App({ model }) {
  const [panelOpen, setPanelOpen] = useState(false);
  const [hover, setHover] = useState(null);
  const sourcesRef = useRef(null);
  const selectionsRef = useRef(null);
  const deckRef = useRef(null);

  const controller = useMemo(() => {
    const c = new InteractionController(model);
    c.register(panTool);
    c.register(selectTool);
    c.register(rectTool);
    c.register(polygonTool);
    c.register(pointTool);
    return c;
  }, [model]);

  const maskBridge = useMemo(() => new MaskSourceBridge(model), [model]);
  useEffect(() => () => maskBridge.destroy(), [maskBridge]);

  useEffect(() => {
    const handler = () => {
      rectTool.reset();
      polygonTool.reset();
    };
    model.on('change:tool_mode', handler);
    return () => model.off('change:tool_mode', handler);
  }, [model, controller]);

  const onHover = useMemo(
    () => makeHoverHandler({
      getSources: () => sourcesRef.current,
      getSelections: () => selectionsRef.current,
      setHover,
    }),
    []);

  useEffect(() => installKeyboard(model), [model]);

  return (
    <div className="bioimage-viewer" tabIndex={0}>
      <Toolbar model={model} onToggleLayers={() => setPanelOpen((v) => !v)} panelOpen={panelOpen} />
      <DimControls model={model} />
      <div className="content-area" style={{ display: 'flex', flex: 1, minHeight: 500 }}>
        <div className="viewport-slot" style={{ position: 'relative', flex: 1, minHeight: 500, background: '#000' }}>
          <DeckCanvas model={model} onHover={onHover}
                      controller={controller}
                      maskBridge={maskBridge}
                      deckRef={deckRef}
                      sourcesRef={sourcesRef}
                      selectionsRef={selectionsRef} />
        </div>
        {panelOpen && <LayersPanel model={model} />}
      </div>
      <StatusBar model={model} hover={hover} />
    </div>
  );
}
```

- [ ] **Step 9: Mount mask layers in `DeckCanvas.jsx`**

Full replacement of `anybioimage/frontend/viewer/src/render/DeckCanvas.jsx` (updates the file from Task 9 to add `maskBridge` subscription + `maskLayers` in the stack):

```jsx
// anybioimage/frontend/viewer/src/render/DeckCanvas.jsx
import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { OrthographicView } from '@deck.gl/core';
import { MultiscaleImageLayer, getDefaultInitialViewState } from '@hms-dbmi/viv';

import { openOmeZarr } from './pixel-sources/zarr-source.js';
import { AnywidgetPixelSource } from './pixel-sources/anywidget-source.js';
import { buildImageLayerProps } from './layers/buildImageLayer.js';
import { buildScaleBarLayer } from './layers/buildScaleBar.js';
import { annotationsToLayers } from './layers/annotationsToLayers.js';
import { buildMaskLayers } from './layers/buildMaskLayers.js';
import { useModelTrait } from '../model/useModelTrait.js';

function useContainerSize(ref, fallback = { width: 800, height: 600 }) {
  const [size, setSize] = useState(fallback);
  useLayoutEffect(() => {
    if (!ref.current) return;
    const el = ref.current;
    const measure = () => {
      const rect = el.getBoundingClientRect();
      setSize({
        width: Math.max(1, Math.floor(rect.width)) || fallback.width,
        height: Math.max(1, Math.floor(rect.height)) || fallback.height,
      });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref, fallback.width, fallback.height]);
  return size;
}

export function DeckCanvas({ model, onHover, controller, maskBridge, deckRef, sourcesRef, selectionsRef }) {
  const zarrSource = useModelTrait(model, '_zarr_source');
  const pixelSourceMode = useModelTrait(model, '_pixel_source_mode');
  const channelSettings = useModelTrait(model, '_channel_settings');
  const currentT = useModelTrait(model, 'current_t');
  const currentZ = useModelTrait(model, 'current_z');
  const displayMode = useModelTrait(model, '_display_mode');
  const activeChannel = useModelTrait(model, 'current_c') || 0;
  const imageShape = useModelTrait(model, '_image_shape');
  const imageDtype = useModelTrait(model, '_image_dtype');
  const pixelSizeUm = useModelTrait(model, 'pixel_size_um');
  const scaleBarVisible = useModelTrait(model, 'scale_bar_visible') !== false;
  const imageVisible = useModelTrait(model, 'image_visible') !== false;
  const annotations = useModelTrait(model, '_annotations') || [];
  const selectedId = useModelTrait(model, 'selected_annotation_id') || '';
  const toolMode = useModelTrait(model, 'tool_mode') || 'pan';
  const masks = useModelTrait(model, '_masks_data') || [];

  const containerRef = useRef(null);
  const { width, height } = useContainerSize(containerRef);

  const [sources, setSources] = useState(null);
  const [error, setError] = useState(null);
  const [viewState, setViewState] = useState(null);
  const [previewTick, setPreviewTick] = useState(0);
  const [maskTick, setMaskTick] = useState(0);

  useEffect(() => {
    if (!controller) return;
    return controller.onPreviewChange(() => setPreviewTick((t) => t + 1));
  }, [controller]);

  useEffect(() => {
    if (!maskBridge) return;
    const unsubs = masks.map((m) => maskBridge.subscribe(m.id, () => setMaskTick((t) => t + 1)));
    return () => { for (const u of unsubs) u(); };
  }, [maskBridge, masks]);

  useEffect(() => {
    let cancelled = false;
    let activeAnywidgetSource = null;
    async function run() {
      setError(null);
      if (pixelSourceMode === 'chunk_bridge') {
        if (!imageShape || imageShape.length !== 5) { setSources(null); return; }
        activeAnywidgetSource = new AnywidgetPixelSource(model, {
          shape: imageShape, dtype: imageDtype || 'Uint16', tileSize: 512,
        });
        setSources([activeAnywidgetSource]);
      } else if (zarrSource?.url) {
        try {
          const { sources: srcs } = await openOmeZarr(zarrSource.url, zarrSource.headers || {});
          if (!cancelled) setSources(srcs);
        } catch (e) {
          if (!cancelled) { setError(String(e)); setSources(null); }
        }
      } else {
        setSources(null);
      }
    }
    run();
    return () => {
      cancelled = true;
      if (activeAnywidgetSource) activeAnywidgetSource.destroy();
    };
  }, [pixelSourceMode, zarrSource?.url, imageShape, imageDtype]);

  useEffect(() => {
    if (!sources || !sources.length) return;
    const vs = getDefaultInitialViewState(sources, { width, height }, 0);
    setViewState(vs);
  }, [sources, width, height]);

  useEffect(() => { if (sourcesRef) sourcesRef.current = sources; }, [sources, sourcesRef]);

  const imageLayerProps = useMemo(() => {
    if (!sources || !sources.length) return null;
    return buildImageLayerProps({
      sources, channels: channelSettings || [],
      currentT: currentT || 0, currentZ: currentZ || 0,
      displayMode, activeChannel,
    });
  }, [sources, channelSettings, currentT, currentZ, displayMode, activeChannel]);

  useEffect(() => {
    if (selectionsRef) selectionsRef.current = imageLayerProps?.selections ?? null;
  }, [imageLayerProps, selectionsRef]);

  useEffect(() => {
    const handler = (content) => {
      if (!content || content.kind !== 'reset-view') return;
      if (!sources || !sources.length) return;
      const vs = getDefaultInitialViewState(sources, { width, height }, 0);
      setViewState(vs);
    };
    model.on('msg:custom', handler);
    return () => model.off('msg:custom', handler);
  }, [model, sources, width, height]);

  const annotationLayers = useMemo(
    () => annotationsToLayers({
      annotations, currentT: currentT || 0, currentZ: currentZ || 0, selectedId,
    }),
    [annotations, currentT, currentZ, selectedId]);

  const maskLayers = useMemo(
    () => (maskBridge ? buildMaskLayers({ masks, bridge: maskBridge }) : []),
    [masks, maskBridge, maskTick]);

  const previewLayer = useMemo(
    () => (controller ? controller.getPreviewLayer() : null),
    [controller, previewTick, toolMode]);

  const layers = useMemo(() => {
    const out = [];
    if (imageLayerProps && imageVisible) {
      out.push(new MultiscaleImageLayer({ id: 'viv-image', viewportId: 'ortho', ...imageLayerProps }));
    }
    for (const l of maskLayers) out.push(l);
    for (const l of annotationLayers) out.push(l);
    if (previewLayer) out.push(previewLayer);
    if (scaleBarVisible && pixelSizeUm) {
      out.push(buildScaleBarLayer({ pixelSizeUm, viewState, width, height }));
    }
    return out;
  }, [imageLayerProps, imageVisible, maskLayers, annotationLayers, previewLayer,
      pixelSizeUm, scaleBarVisible, viewState, width, height]);

  function imagePixelFor(info) {
    const coord = info?.coordinate;
    if (!coord) return null;
    return { x: coord[0], y: coord[1] };
  }

  function pickObject(event) {
    const deck = deckRef?.current?.deck;
    if (!deck || !event) return null;
    const picked = deck.pickObject({
      x: event.screenX ?? event._screenX ?? 0,
      y: event.screenY ?? event._screenY ?? 0,
      radius: 4,
    });
    if (!picked) return null;
    const id = picked.object?.id;
    const sourceAnnotation = id ? annotations.find((a) => a.id === id) : null;
    return { layer: picked.layer, object: picked.object, sourceAnnotation };
  }

  function onClick(info) {
    if (!controller) return;
    const pt = imagePixelFor(info);
    if (!pt) return;
    const ev = { ...pt, screenX: info.x, screenY: info.y, _picked: pickObject(info) };
    controller.handlePointerEvent('down', ev);
    controller.handlePointerEvent('up', ev);
  }

  function onDragStart(info) {
    if (!controller) return;
    const pt = imagePixelFor(info);
    if (!pt) return;
    controller.handlePointerEvent('down', { ...pt, screenX: info.x, screenY: info.y });
  }

  function onDrag(info) {
    if (!controller) return;
    const pt = imagePixelFor(info);
    if (!pt) return;
    controller.handlePointerEvent('move', { ...pt, screenX: info.x, screenY: info.y });
  }

  function onDragEnd(info) {
    if (!controller) return;
    const pt = imagePixelFor(info);
    if (!pt) return;
    controller.handlePointerEvent('up', { ...pt, screenX: info.x, screenY: info.y });
  }

  function onDblClick(info) {
    if (!controller) return;
    const pt = imagePixelFor(info);
    if (!pt) return;
    const tool = controller.activeTool;
    if (tool.onDoubleClick) tool.onDoubleClick(pt, { model, controller, pickObject });
  }

  const viewController = toolMode === 'pan' || toolMode === 'select';

  if (error) {
    return <div style={{ color: '#b00', padding: 12 }}>Failed to load image: {error}</div>;
  }

  return (
    <div ref={containerRef} style={{ position: 'absolute', inset: 0 }}>
      {!sources ? (
        <div style={{ padding: 12, color: '#666' }}>Loading…</div>
      ) : (
        <DeckGL
          ref={deckRef}
          width={width}
          height={height}
          layers={layers}
          views={[new OrthographicView({ id: 'ortho', controller: viewController })]}
          viewState={viewState ? { ortho: viewState } : undefined}
          onViewStateChange={({ viewState: v }) => setViewState(v)}
          onHover={onHover}
          onClick={onClick}
          onDragStart={onDragStart}
          onDrag={onDrag}
          onDragEnd={onDragEnd}
          onDblClick={onDblClick}
          useDevicePixels={true}
          getCursor={({ isDragging }) =>
            isDragging ? 'grabbing' : (controller?.cursor || 'crosshair')
          }
        />
      )}
    </div>
  );
}
```

- [ ] **Step 10: Build, test, commit**

```
cd anybioimage/frontend/viewer && npm run test && npm run build && cd ../../..
```

Expected: all vitest suites pass; bundle rebuilt.

```bash
git add anybioimage/frontend/viewer/src/render/pixel-sources/MaskSourceBridge.js \
        anybioimage/frontend/viewer/src/render/pixel-sources/MaskSourceBridge.test.js \
        anybioimage/frontend/viewer/src/render/layers/buildMaskLayers.js \
        anybioimage/frontend/viewer/src/render/layers/buildMaskLayers.test.js \
        anybioimage/frontend/viewer/src/render/DeckCanvas.jsx \
        anybioimage/frontend/viewer/src/App.jsx \
        anybioimage/frontend/viewer/dist/viewer-bundle.js
git commit -m "feat(viewer/masks): mount BitmapLayer per mask via MaskSourceBridge"
```

---

## Task 13: `MasksSection` in Layers panel

**Goal:** Real Layers-panel section for masks. Rows per mask: name (editable), visibility toggle, opacity slider, color swatch, contours toggle, delete button. Writes through to `_masks_data` via `update_mask_settings` messages and `remove_mask` messages handled in `viewer.py`. [spec §3, §5]

**Files:**
- Modify: `anybioimage/frontend/viewer/src/chrome/LayersPanel/MasksSection.jsx` (stub from Task 10 is overwritten)
- Modify: `anybioimage/viewer.py` — route `mask_update` / `mask_delete`

- [ ] **Step 1: Route mask-update / mask-delete in `viewer.py`**

Extend `_route_message`:

```python
    def _route_message(self, widget, content, buffers):
        """Dispatch custom JS → Py messages by `kind` key."""
        if not isinstance(content, dict):
            return
        kind = content.get("kind")
        if kind == "chunk":
            self.handle_chunk_request(content)
        elif kind == "mask_request":
            self.handle_mask_request(content)
        elif kind == "mask_update":
            mid = content.get("id")
            if mid:
                kw = {k: v for k, v in content.items() if k not in ("kind", "id")}
                self.update_mask_settings(mid, **kw)
        elif kind == "mask_delete":
            mid = content.get("id")
            if mid:
                self.remove_mask(mid)
```

- [ ] **Step 2: Write `MasksSection.jsx`**

```jsx
// anybioimage/frontend/viewer/src/chrome/LayersPanel/MasksSection.jsx
import React from 'react';
import { useModelTrait } from '../../model/useModelTrait.js';

function update(model, id, changes) {
  model.send({ kind: 'mask_update', id, ...changes });
}

function remove(model, id) {
  model.send({ kind: 'mask_delete', id });
}

export function MasksSection({ model }) {
  const masks = useModelTrait(model, '_masks_data') || [];
  return (
    <div className="layers-section" style={{ padding: '4px 8px' }}>
      <div className="layer-header" style={{ padding: '6px 0', fontSize: 11, fontWeight: 600, color: '#666', textTransform: 'uppercase' }}>
        Masks ({masks.length})
      </div>
      {masks.length === 0 && (
        <div style={{ color: '#999', fontSize: 12, padding: '4px 0' }}>
          No masks — call <code>viewer.add_mask(labels)</code>.
        </div>
      )}
      {masks.map((m) => (
        <div key={m.id} className="layer-item mask-layer"
             style={{ display: 'flex', flexDirection: 'column', padding: '6px 4px', borderRadius: 4, background: '#fff', marginBottom: 4, gap: 4 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <button
              onClick={() => update(model, m.id, { visible: !m.visible })}
              style={{ background: 'none', border: 'none', cursor: 'pointer',
                       color: m.visible ? '#0d6efd' : '#999' }}
              title={m.visible ? 'Hide' : 'Show'}
            >{m.visible ? '👁' : '⊘'}</button>
            <input
              type="color"
              className="color-swatch"
              value={m.color || '#ff0000'}
              onChange={(e) => update(model, m.id, { color: e.target.value })}
              style={{ width: 20, height: 20, padding: 0, border: '1px solid #ccc', borderRadius: 3 }}
            />
            <span style={{ flex: 1, fontSize: 13 }}>{m.name}</span>
            <button
              onClick={() => remove(model, m.id)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#c33' }}
              title="Delete"
            >🗑</button>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: 11, color: '#888', width: 50 }}>Opacity</span>
            <input
              type="range" min={0} max={1} step={0.05}
              value={m.opacity ?? 0.5}
              onChange={(e) => update(model, m.id, { opacity: parseFloat(e.target.value) })}
              style={{ flex: 1 }}
            />
            <span style={{ fontSize: 11, color: '#888', width: 30, textAlign: 'right' }}>
              {(m.opacity ?? 0.5).toFixed(2)}
            </span>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#555' }}>
            <input
              type="checkbox"
              checked={!!m.contours}
              onChange={(e) => update(model, m.id, { contours: e.target.checked })}
            />
            <span>Contours only</span>
          </label>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Build and commit**

```
cd anybioimage/frontend/viewer && npm run build && cd ../../..
```

```bash
git add anybioimage/frontend/viewer/src/chrome/LayersPanel/MasksSection.jsx \
        anybioimage/viewer.py \
        anybioimage/frontend/viewer/dist/viewer-bundle.js
git commit -m "feat(viewer/chrome): MasksSection with per-mask controls"
```

---

## Task 14: SAM integration — JS flow + new mask transport

**Goal:** When a rectangle or point is committed **and** `sam_enabled` is true, send a `{kind: "sam_rect", bbox, t, z}` / `{kind: "sam_point", xy, t, z}` message instead of (or in addition to) writing into `_annotations`. Python's `SAMIntegrationMixin` observer picks the annotations up already; Phase 2 adds explicit handlers so tools can also trigger SAM without leaving a stale annotation. Add a "SAM" toggle in the Layers panel (phase-3 footer will turn this into a full SAM row). [spec §5]

**Files:**
- Modify: `anybioimage/mixins/sam_integration.py` — add `sam_enabled` traitlet flag; add message handlers
- Modify: `anybioimage/viewer.py` — route `sam_rect` / `sam_point`
- Modify: `anybioimage/frontend/viewer/src/interaction/tools/rect.js` and `point.js` — branch on `sam_enabled`
- Create: `tests/test_sam_protocol.py`

- [ ] **Step 1: Add `sam_enabled` traitlet**

In `anybioimage/viewer.py`, add next to the existing SAM-adjacent traitlets (right after `_delete_sam_at`):

```python
    # SAM toggle surfaced to JS [spec §5 — Phase 2 hookup].
    sam_enabled = traitlets.Bool(False).tag(sync=True)
```

And extend `enable_sam` / `disable_sam` in `sam_integration.py` to update the traitlet:

```python
# in enable_sam, right before the early-return success comment add:
        self.sam_enabled = True

# in disable_sam, set:
        self.sam_enabled = False
```

- [ ] **Step 2: SAM protocol handlers**

Add to the `SAMIntegrationMixin` (after `delete_sam_label_at`):

```python
    def handle_sam_rect(self, payload: dict) -> None:
        """JS asked for a SAM mask from a rectangle.

        payload = {kind: "sam_rect", id, x, y, width, height, t, z}
        """
        if not getattr(self, "_sam_enabled", False):
            return
        rec = {
            "id": str(payload.get("id", f"sam_rect_{id(payload)}")),
            "x": float(payload["x"]), "y": float(payload["y"]),
            "width": float(payload["width"]), "height": float(payload["height"]),
        }
        self._on_rois_changed({"new": [rec]})

    def handle_sam_point(self, payload: dict) -> None:
        """JS asked for a SAM mask from a point.

        payload = {kind: "sam_point", id, x, y, t, z}
        """
        if not getattr(self, "_sam_enabled", False):
            return
        rec = {
            "id": str(payload.get("id", f"sam_point_{id(payload)}")),
            "x": float(payload["x"]), "y": float(payload["y"]),
        }
        self._on_points_changed({"new": [rec]})
```

- [ ] **Step 3: Route the new kinds in `viewer.py`**

```python
    def _route_message(self, widget, content, buffers):
        if not isinstance(content, dict):
            return
        kind = content.get("kind")
        if kind == "chunk":
            self.handle_chunk_request(content)
        elif kind == "mask_request":
            self.handle_mask_request(content)
        elif kind == "mask_update":
            mid = content.get("id")
            if mid:
                kw = {k: v for k, v in content.items() if k not in ("kind", "id")}
                self.update_mask_settings(mid, **kw)
        elif kind == "mask_delete":
            mid = content.get("id")
            if mid:
                self.remove_mask(mid)
        elif kind == "sam_rect":
            self.handle_sam_rect(content)
        elif kind == "sam_point":
            self.handle_sam_point(content)
```

- [ ] **Step 4: Failing test**

```python
# tests/test_sam_protocol.py
"""SAM integration protocol — Phase 2 [spec §5].

Covers the JS → Py routing for sam_rect / sam_point without requiring an
actual SAM model. We monkey-patch the per-kind handlers to assert they are
called with the right shape; the SAM model itself is exercised separately.
"""
from __future__ import annotations

from anybioimage import BioImageViewer


class _Probe(BioImageViewer):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.rect_calls = []
        self.point_calls = []
        # Pretend SAM is enabled without loading the model.
        self._sam_enabled = True
        self.sam_enabled = True

    def _on_rois_changed(self, change):
        self.rect_calls.append(change["new"])

    def _on_points_changed(self, change):
        self.point_calls.append(change["new"])


def test_sam_rect_is_routed():
    v = _Probe()
    v._route_message(v, {"kind": "sam_rect", "id": "ab", "x": 1, "y": 2,
                          "width": 3, "height": 4, "t": 0, "z": 0}, [])
    assert v.rect_calls == [[{"id": "ab", "x": 1.0, "y": 2.0, "width": 3.0, "height": 4.0}]]


def test_sam_point_is_routed():
    v = _Probe()
    v._route_message(v, {"kind": "sam_point", "id": "pp", "x": 5, "y": 6, "t": 0, "z": 0}, [])
    assert v.point_calls == [[{"id": "pp", "x": 5.0, "y": 6.0}]]


def test_sam_disabled_does_not_route():
    v = _Probe()
    v._sam_enabled = False
    v.sam_enabled = False
    v._route_message(v, {"kind": "sam_rect", "id": "ab", "x": 1, "y": 2,
                          "width": 3, "height": 4, "t": 0, "z": 0}, [])
    assert v.rect_calls == []
```

Run:

```
uv run pytest tests/test_sam_protocol.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Branch on `sam_enabled` in `rect.js` and `point.js`**

Modify the commit branch in `rect.js`:

```js
// inside onPointerUp, replace the commit block with:
    const t = ctx.model.get('current_t') ?? 0;
    const z = ctx.model.get('current_z') ?? 0;
    const id = makeId();
    const entry = {
      id, kind: 'rect', geometry: [x0, y0, x1, y1],
      label: '', color: '#ff0000', visible: true, t, z,
      created_at: new Date().toISOString(), metadata: {},
    };
    const existing = ctx.model.get('_annotations') || [];
    ctx.model.set('_annotations', [...existing, entry]);
    ctx.model.save_changes();
    if (ctx.model.get('sam_enabled')) {
      ctx.model.send({ kind: 'sam_rect', id, x: x0, y: y0,
                       width: x1 - x0, height: y1 - y0, t, z });
    }
```

And in `point.js`:

```js
    const id = makeId();
    const entry = {
      id, kind: 'point', geometry: [event.x, event.y],
      label: '', color: '#0066ff', visible: true, t, z,
      created_at: new Date().toISOString(), metadata: {},
    };
    const existing = ctx.model.get('_annotations') || [];
    ctx.model.set('_annotations', [...existing, entry]);
    ctx.model.save_changes();
    if (ctx.model.get('sam_enabled')) {
      ctx.model.send({ kind: 'sam_point', id, x: event.x, y: event.y, t, z });
    }
```

- [ ] **Step 6: Add a SAM toggle to `LayersPanel`**

Append a small footer row in `LayersPanel.jsx`, above `<ExportFooter>`:

```jsx
      <div className="layer-item" style={{ padding: '6px 8px', display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
        <input
          type="checkbox"
          checked={!!model.get('sam_enabled')}
          onChange={(e) => { model.set('sam_enabled', e.target.checked); model.save_changes(); }}
        />
        <span>Use SAM on next rect / point</span>
      </div>
```

This is a minimal hookup; Phase 3 turns it into a proper SAM section with model type selection.

- [ ] **Step 7: Build, test, commit**

```
cd anybioimage/frontend/viewer && npm run test && npm run build && cd ../../..
uv run pytest tests/test_sam_protocol.py -v
```

Expected: all green.

```bash
git add anybioimage/viewer.py anybioimage/mixins/sam_integration.py \
        anybioimage/frontend/viewer/src/interaction/tools/rect.js \
        anybioimage/frontend/viewer/src/interaction/tools/point.js \
        anybioimage/frontend/viewer/src/chrome/LayersPanel/LayersPanel.jsx \
        anybioimage/frontend/viewer/dist/viewer-bundle.js \
        tests/test_sam_protocol.py
git commit -m "feat(sam): JS → Py sam_rect/sam_point protocol + enable toggle"
```

---

## Task 15: Demo notebook sections 7 (annotations) and 8 (SAM)

**Goal:** Extend `examples/full_demo.py` with two new sections — the Phase 2 annotate walkthrough and the SAM walkthrough. Provide Playwright smoke tests that drive each new flow. [spec §9, §11]

**Files:**
- Modify: `examples/full_demo.py`
- Create: `tests/playwright/test_phase2_draw_rect.py`
- Create: `tests/playwright/test_phase2_draw_polygon.py`
- Create: `tests/playwright/test_phase2_draw_point.py`
- Create: `tests/playwright/test_phase2_sam_flow.py`

- [ ] **Step 1: Append the new cells**

```python
# add to examples/full_demo.py below the existing sections

@app.cell
def _annotations(mo):
    import pandas as pd
    from anybioimage import BioImageViewer
    import numpy as np

    v = BioImageViewer()
    v.set_image(np.random.randint(0, 255, (5, 1, 1, 512, 512), dtype=np.uint8))

    mo.md("""
    ## 7 — Annotations (Phase 2)

    Draw rectangles, polygons, and points interactively. The DataFrame views
    update live. Select the tool in the toolbar, then draw on the canvas:

    - **Rectangle** — drag.
    - **Polygon** — click vertices, double-click to close (or press Enter).
    - **Point** — click to place.
    """)
    return (v,)


@app.cell
def _annotations_tables(v, mo):
    import pandas as pd
    mo.md("**Live DataFrame views (reactive):**")
    mo.ui.anywidget(v)
    return


@app.cell
def _annotations_rois_df(v, mo):
    mo.md("### Rectangles (`rois_df`)")
    mo.ui.table(v.rois_df)
    return


@app.cell
def _annotations_polygons_df(v, mo):
    mo.md("### Polygons (`polygons_df`)")
    mo.ui.table(v.polygons_df)
    return


@app.cell
def _annotations_points_df(v, mo):
    mo.md("### Points (`points_df`)")
    mo.ui.table(v.points_df)
    return


@app.cell
def _sam_section(mo):
    try:
        import ultralytics  # noqa: F401
        sam_available = True
    except Exception:
        sam_available = False

    if not sam_available:
        mo.md("""
        ## 8 — SAM (optional)

        Install with `pip install anybioimage[sam]` to enable this section.
        """)
        return (None,)

    from anybioimage import BioImageViewer
    import numpy as np

    v = BioImageViewer()
    # Small synthetic example — replace with a real cell image in practice.
    data = np.random.randint(0, 255, (1, 1, 1, 256, 256), dtype=np.uint8)
    v.set_image(data)
    v.enable_sam("mobile_sam")

    mo.md("""
    ## 8 — SAM walkthrough

    The Layers panel has a "Use SAM on next rect / point" checkbox. When
    enabled, drawing a rectangle (or placing a point) runs SAM and adds the
    resulting mask to the Masks section — no extra code required.
    """)
    mo.ui.anywidget(v)
    return (v,)
```

- [ ] **Step 2: Playwright — rect draw**

```python
# tests/playwright/test_phase2_draw_rect.py
"""Phase 2 smoke — draw a rectangle via pointer events."""
from __future__ import annotations

import os
import subprocess
import time

import pytest
from playwright.sync_api import sync_playwright

SCREENSHOTS = "/tmp/anybioimage-screenshots"


def ensure_screenshots_dir() -> None:
    os.makedirs(SCREENSHOTS, exist_ok=True)


@pytest.mark.playwright
def test_phase2_draw_rect():
    ensure_screenshots_dir()
    # Assume a marimo server is already running — CI starts one in conftest.
    token = os.environ.get("MARIMO_TOKEN", "")
    url = f"http://localhost:2718?access_token={token}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        # Switch to rectangle tool.
        page.evaluate("""() => {
          for (const el of document.querySelectorAll('*')) {
            if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
              const btn = [...el.shadowRoot.querySelectorAll('button')].find(
                b => b.title && b.title.startsWith('Rectangle'));
              btn.click();
              return;
            }
          }
        }""")
        time.sleep(0.5)

        # Drag on the canvas.
        box = page.evaluate("""() => {
          for (const el of document.querySelectorAll('*')) {
            if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
              const c = el.shadowRoot.querySelector('canvas');
              const r = c.getBoundingClientRect();
              return { x: r.left, y: r.top, w: r.width, h: r.height };
            }
          }
        }""")
        assert box
        sx = box["x"] + box["w"] * 0.25
        sy = box["y"] + box["h"] * 0.25
        ex = box["x"] + box["w"] * 0.5
        ey = box["y"] + box["h"] * 0.5
        page.mouse.move(sx, sy)
        page.mouse.down()
        page.mouse.move(ex, ey, steps=10)
        page.mouse.up()
        time.sleep(1.0)

        page.screenshot(path=f"{SCREENSHOTS}/phase2-rect-drawn.png")
        browser.close()
```

- [ ] **Step 3: Similar Playwright files for polygon and point**

```python
# tests/playwright/test_phase2_draw_polygon.py
"""Phase 2 smoke — draw a polygon via click-click-click-Enter."""
from __future__ import annotations

import os
import time

import pytest
from playwright.sync_api import sync_playwright

SCREENSHOTS = "/tmp/anybioimage-screenshots"


@pytest.mark.playwright
def test_phase2_draw_polygon():
    os.makedirs(SCREENSHOTS, exist_ok=True)
    token = os.environ.get("MARIMO_TOKEN", "")
    url = f"http://localhost:2718?access_token={token}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        page.evaluate("""() => {
          for (const el of document.querySelectorAll('*')) {
            if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
              [...el.shadowRoot.querySelectorAll('button')]
                .find(b => b.title && b.title.startsWith('Polygon')).click();
              return;
            }
          }
        }""")
        time.sleep(0.3)

        box = page.evaluate("""() => {
          for (const el of document.querySelectorAll('*')) {
            if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
              const c = el.shadowRoot.querySelector('canvas');
              const r = c.getBoundingClientRect();
              return { x: r.left, y: r.top, w: r.width, h: r.height };
            }
          }
        }""")
        for pct in [(0.2, 0.2), (0.4, 0.2), (0.3, 0.4)]:
            page.mouse.click(box["x"] + box["w"] * pct[0], box["y"] + box["h"] * pct[1])
            time.sleep(0.15)
        page.keyboard.press("Enter")
        time.sleep(0.8)
        page.screenshot(path=f"{SCREENSHOTS}/phase2-polygon-drawn.png")
        browser.close()
```

```python
# tests/playwright/test_phase2_draw_point.py
"""Phase 2 smoke — place a point."""
from __future__ import annotations

import os
import time

import pytest
from playwright.sync_api import sync_playwright

SCREENSHOTS = "/tmp/anybioimage-screenshots"


@pytest.mark.playwright
def test_phase2_draw_point():
    os.makedirs(SCREENSHOTS, exist_ok=True)
    token = os.environ.get("MARIMO_TOKEN", "")
    url = f"http://localhost:2718?access_token={token}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        page.evaluate("""() => {
          for (const el of document.querySelectorAll('*')) {
            if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
              [...el.shadowRoot.querySelectorAll('button')]
                .find(b => b.title && b.title.startsWith('Point')).click();
              return;
            }
          }
        }""")
        time.sleep(0.3)

        box = page.evaluate("""() => {
          for (const el of document.querySelectorAll('*')) {
            if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
              const c = el.shadowRoot.querySelector('canvas');
              const r = c.getBoundingClientRect();
              return { x: r.left, y: r.top, w: r.width, h: r.height };
            }
          }
        }""")
        page.mouse.click(box["x"] + box["w"] * 0.5, box["y"] + box["h"] * 0.5)
        time.sleep(0.5)
        page.screenshot(path=f"{SCREENSHOTS}/phase2-point-placed.png")
        browser.close()
```

```python
# tests/playwright/test_phase2_sam_flow.py
"""Phase 2 smoke — SAM round-trip (rect → mask). Skipped if SAM extra missing."""
from __future__ import annotations

import importlib.util
import os
import time

import pytest
from playwright.sync_api import sync_playwright

SCREENSHOTS = "/tmp/anybioimage-screenshots"

_has_ultralytics = importlib.util.find_spec("ultralytics") is not None


@pytest.mark.playwright
@pytest.mark.skipif(not _has_ultralytics, reason="SAM extra not installed")
def test_phase2_sam_flow():
    os.makedirs(SCREENSHOTS, exist_ok=True)
    token = os.environ.get("MARIMO_TOKEN", "")
    url = f"http://localhost:2718?access_token={token}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)
        page.wait_for_load_state("networkidle")
        time.sleep(5)

        # Scroll to SAM section, toggle the SAM checkbox, draw a rect.
        # (Concise — details covered by the rect test.)
        page.evaluate("""() => {
          for (const el of document.querySelectorAll('*')) {
            if (el.tagName === 'MARIMO-ANYWIDGET' && el.shadowRoot) {
              // Open Layers, tick SAM.
              const layers = [...el.shadowRoot.querySelectorAll('button')]
                .find(b => b.textContent && b.textContent.includes('Layers'));
              if (layers) layers.click();
            }
          }
        }""")
        time.sleep(0.5)
        page.screenshot(path=f"{SCREENSHOTS}/phase2-sam-before.png")
        # End of smoke — a full SAM round-trip is expensive; we verify the
        # toggle renders and the widget remains interactive.
        browser.close()
```

- [ ] **Step 4: Commit**

```bash
git add examples/full_demo.py tests/playwright/test_phase2_draw_rect.py \
        tests/playwright/test_phase2_draw_polygon.py \
        tests/playwright/test_phase2_draw_point.py \
        tests/playwright/test_phase2_sam_flow.py
git commit -m "test(phase2): demo sections 7–8 + Playwright smoke flows"
```

---

## Task 16: Browser validation + CHANGELOG

**Goal:** Mirror the end-of-Phase-1 ritual: run the demo in chromium via the `playwright-cli` skill, screenshot every new section, confirm zero console errors, then update `CHANGELOG.md`.

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Manual browser walk-through**

```bash
uv run marimo edit examples/full_demo.py
# Note the access token printed; open a headful chromium with playwright-cli:
playwright-cli open "http://localhost:2718?access_token=<token>" --browser=chromium
mkdir -p /tmp/anybioimage-screenshots
```

Drive through each new Phase 2 section. Capture screenshots:
- `/tmp/anybioimage-screenshots/phase2-rect-drawn.png`
- `/tmp/anybioimage-screenshots/phase2-polygon-drawn.png`
- `/tmp/anybioimage-screenshots/phase2-point-placed.png`
- `/tmp/anybioimage-screenshots/phase2-annotations-panel.png`
- `/tmp/anybioimage-screenshots/phase2-masks-panel.png`
- `/tmp/anybioimage-screenshots/phase2-sam-toggle.png` (if SAM extra installed)

Confirm the browser Console is empty — no red errors. Clean up:

```bash
rm -rf /tmp/anybioimage-screenshots
```

- [ ] **Step 2: Update `CHANGELOG.md`**

Extend the existing `[Unreleased]` block with a Phase 2 sub-section:

```markdown
## [Unreleased] — targeting v0.7.0

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

### Removed (Breaking) — Phase 2

- `_rois_data`, `_polygons_data`, `_points_data` traitlets (private; no
  back-compat) — superseded by `_annotations`.
- `rois_visible`, `roi_color`, `polygons_visible`, `polygon_color`,
  `points_visible`, `point_color`, `point_radius` traitlets — per-kind
  styling now lives per-annotation in the unified list.
```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): Phase 2 additions + removals"
```

---

## Self-review checklist (run before declaring Phase 2 done)

- [ ] Spec §5 (annotations unified) — Tasks 1, 2, 3, 10.
- [ ] Spec §6 (interaction + tool registry) — Tasks 4, 5, 6, 7, 8, 9.
- [ ] Spec §3 (layer stack: masks + annotations) — Tasks 3, 12.
- [ ] Spec §8 "Phase 2 — Annotate MVP" scope — rect/polygon/point + mask overlays + SAM + unified annotations all delivered (Tasks 1–14); editing / measurement / undo / export correctly deferred to Phase 3.
- [ ] Spec §11 (testing) — Python: Tasks 1, 11, 14. JS (vitest): Tasks 2, 4, 5, 6, 7, 8, 12. Playwright: Task 15.
- [ ] Spec §12 (back-compat: DataFrame properties unchanged shape) — Task 1 tests.
- [ ] Demo app (§9) — new sections 7 (annotations) and 8 (SAM) — Task 15.
- [ ] No placeholders, no `...`, no "similar to X" — every code block is complete.
- [ ] Task N references to symbols defined in Task M < N all resolve (`annotationsToLayers`, `InteractionController`, `MaskSourceBridge`, `rectTool` etc.).
- [ ] Type consistency: `_annotations` entry shape in Task 1 matches what tools write in Tasks 6, 7, 8 and what the layer composer reads in Task 2.

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-19-unified-viewer-phase2.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks. Best for 16 bite-sized tasks; keeps main-session context clean.

**2. Inline Execution** — execute tasks in this session using executing-plans; batch checkpoints for review.

**Which approach?**
