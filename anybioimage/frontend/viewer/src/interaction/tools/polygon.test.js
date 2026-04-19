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
