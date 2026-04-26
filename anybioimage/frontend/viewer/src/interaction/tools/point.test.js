import { describe, it, expect, vi, beforeEach } from 'vitest';
import { makePointTool } from './point.js';

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

describe('makePointTool', () => {
  let model;
  let pointTool;
  beforeEach(() => {
    model = fakeModel();
    // Each test gets a fresh tool instance — no shared module state.
    pointTool = makePointTool();
  });

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

  it('two tool instances have independent down-state', () => {
    const model2 = fakeModel();
    const tool2 = makePointTool();
    // Register pointer-down in tool1 only
    pointTool.onPointerDown({ x: 10, y: 10 }, ctx(model));
    // tool2 has no pending down — pointer-up should be a no-op
    tool2.onPointerUp({ x: 10, y: 10 }, ctx(model2));
    expect(model2._state._annotations).toHaveLength(0);
    // tool1 still has the pending down
    pointTool.onPointerUp({ x: 10, y: 10 }, ctx(model));
    expect(model._state._annotations).toHaveLength(1);
  });
});
