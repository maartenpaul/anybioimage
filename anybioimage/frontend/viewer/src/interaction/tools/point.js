/** Point tool factory — call makePointTool() to get a per-widget instance whose
 *  drag-detection state never bleeds into another widget [spec §5.4].
 *
 *  Click to place a point annotation. Drags (pointer-up far from pointer-down)
 *  are discarded so accidental click-and-slide does not fire.
 */

// Module-level counter is fine: IDs are per-widget (each widget has its own
// model), and the counter only needs to be monotone within a JS session.
let _nextId = 1;

function makeId() { return `point_${Date.now().toString(36)}_${_nextId++}`; }

export function makePointTool() {
  const _state = { downX: null, downY: null };

  return {
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
      if (ctx.model.get('sam_enabled')) {
        ctx.model.send({ kind: 'sam_point', id: entry.id, x: event.x, y: event.y, t, z });
      }
    },

    onKeyDown() {},
    getPreviewLayer() { return null; },

    reset() {
      _state.downX = null;
      _state.downY = null;
    },
  };
}
