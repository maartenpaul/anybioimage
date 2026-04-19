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
