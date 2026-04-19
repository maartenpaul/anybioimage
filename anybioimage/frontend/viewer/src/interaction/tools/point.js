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
