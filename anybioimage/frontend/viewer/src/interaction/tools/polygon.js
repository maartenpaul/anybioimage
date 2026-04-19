/** Polygon tool factory — each widget instance gets its own tool object via
 *  makePolygonTool(), so draw state never bleeds between two widgets on the
 *  same page [spec §5.4].
 *
 *  Click to add vertices; double-click / Enter to close;
 *  Esc to cancel. Emits a `kind: "polygon"` annotation entry on commit.
 */
import { PathLayer, PolygonLayer } from '@deck.gl/layers';

// Module-level counter is fine: IDs are per-widget (each widget has its own
// model), and the counter only needs to be monotone within a JS session.
let _nextId = 1;

function makeId() { return `poly_${Date.now().toString(36)}_${_nextId++}`; }

export function makePolygonTool() {
  const _state = {
    vertices: null,   // [[x,y], ...] while drawing; null when idle.
    hover: null,      // current pointer position for rubber-band preview
  };

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

  return {
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
}
