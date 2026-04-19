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
