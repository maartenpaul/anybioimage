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
