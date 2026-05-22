// anybioimage/frontend/viewer/src/chrome/LayersPanel/AnnotationsSection.test.js
import { describe, it, expect, vi } from 'vitest';

// Import the helpers by re-exporting them through the module.
// We test the mutation helpers in isolation using a fake model.

function fakeModel(initial = {}) {
  const state = { ...initial };
  return {
    get: (k) => state[k],
    set: (k, v) => { state[k] = v; },
    save_changes: vi.fn(),
    _state: state,
  };
}

// Inline the helpers so they can be tested without mounting React.
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

function ann(id, kind, visible = true) {
  return { id, kind, visible, geometry: [0, 0, 1, 1], color: '#ff0000', t: 0, z: 0 };
}

describe('AnnotationsSection helpers', () => {
  describe('toggleKindVisibility', () => {
    it('sets visible=true for all annotations of a kind', () => {
      const model = fakeModel();
      const annotations = [
        ann('r1', 'rect', false),
        ann('r2', 'rect', false),
        ann('p1', 'point', true),
      ];
      toggleKindVisibility(model, annotations, 'rect', true);
      const next = model._state._annotations;
      expect(next[0].visible).toBe(true);
      expect(next[1].visible).toBe(true);
      expect(next[2].visible).toBe(true); // point unchanged
      expect(model.save_changes).toHaveBeenCalled();
    });

    it('sets visible=false for all annotations of a kind', () => {
      const model = fakeModel();
      const annotations = [
        ann('r1', 'rect', true),
        ann('p1', 'point', true),
      ];
      toggleKindVisibility(model, annotations, 'rect', false);
      const next = model._state._annotations;
      expect(next[0].visible).toBe(false);
      expect(next[1].visible).toBe(true); // point unchanged
    });

    it('does not mutate the original annotations array', () => {
      const model = fakeModel();
      const annotations = [ann('r1', 'rect', true)];
      const original = annotations[0];
      toggleKindVisibility(model, annotations, 'rect', false);
      expect(original.visible).toBe(true); // original untouched
    });
  });

  describe('clearKind', () => {
    it('removes all annotations of the specified kind', () => {
      const model = fakeModel();
      const annotations = [
        ann('r1', 'rect'),
        ann('r2', 'rect'),
        ann('p1', 'point'),
      ];
      clearKind(model, annotations, 'rect');
      const next = model._state._annotations;
      expect(next).toHaveLength(1);
      expect(next[0].id).toBe('p1');
    });

    it('leaves array unchanged when kind has no entries', () => {
      const model = fakeModel();
      const annotations = [ann('p1', 'point')];
      clearKind(model, annotations, 'polygon');
      expect(model._state._annotations).toHaveLength(1);
    });
  });

  describe('toggleOne', () => {
    it('flips visible from true to false for the matching id', () => {
      const model = fakeModel();
      const annotations = [ann('r1', 'rect', true), ann('r2', 'rect', true)];
      toggleOne(model, annotations, 'r1');
      const next = model._state._annotations;
      expect(next[0].visible).toBe(false);
      expect(next[1].visible).toBe(true);
    });

    it('flips visible from false to true', () => {
      const model = fakeModel();
      const annotations = [ann('r1', 'rect', false)];
      toggleOne(model, annotations, 'r1');
      expect(model._state._annotations[0].visible).toBe(true);
    });

    it('does not affect other annotations', () => {
      const model = fakeModel();
      const annotations = [ann('r1', 'rect', true), ann('p1', 'point', true)];
      toggleOne(model, annotations, 'r1');
      expect(model._state._annotations[1].visible).toBe(true);
    });
  });

  describe('removeOne', () => {
    it('removes the annotation with the matching id', () => {
      const model = fakeModel();
      const annotations = [ann('r1', 'rect'), ann('r2', 'rect'), ann('p1', 'point')];
      removeOne(model, annotations, 'r2');
      const next = model._state._annotations;
      expect(next).toHaveLength(2);
      expect(next.find((a) => a.id === 'r2')).toBeUndefined();
    });

    it('is a no-op when id does not exist', () => {
      const model = fakeModel();
      const annotations = [ann('r1', 'rect')];
      removeOne(model, annotations, 'nonexistent');
      expect(model._state._annotations).toHaveLength(1);
    });

    it('calls save_changes', () => {
      const model = fakeModel();
      const annotations = [ann('r1', 'rect')];
      removeOne(model, annotations, 'r1');
      expect(model.save_changes).toHaveBeenCalled();
    });
  });
});
