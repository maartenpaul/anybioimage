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
