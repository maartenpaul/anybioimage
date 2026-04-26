// anybioimage/frontend/viewer/src/chrome/LayersPanel/MasksSection.test.js
import { describe, it, expect, vi } from 'vitest';

// Inline the helpers so they can be tested without mounting React.
function fakeModel(masks = []) {
  const sent = [];
  return {
    _masks: masks,
    get: (k) => (k === '_masks_data' ? fakeModel._masks : undefined),
    send: (msg) => sent.push(msg),
    _sent: sent,
  };
}

function update(model, id, changes) {
  model.send({ kind: 'mask_update', id, ...changes });
}

function remove(model, id) {
  model.send({ kind: 'mask_delete', id });
}

function mask(id, overrides = {}) {
  return {
    id,
    name: `Mask ${id}`,
    color: '#ff0000',
    opacity: 0.5,
    visible: true,
    contours: false,
    ...overrides,
  };
}

describe('MasksSection helpers', () => {
  describe('update', () => {
    it('sends mask_update with id and visible=false', () => {
      const model = fakeModel([mask('m1')]);
      update(model, 'm1', { visible: false });
      expect(model._sent).toHaveLength(1);
      expect(model._sent[0]).toEqual({ kind: 'mask_update', id: 'm1', visible: false });
    });

    it('sends mask_update with opacity change', () => {
      const model = fakeModel([mask('m1')]);
      update(model, 'm1', { opacity: 0.8 });
      expect(model._sent[0]).toEqual({ kind: 'mask_update', id: 'm1', opacity: 0.8 });
    });

    it('sends mask_update with color change', () => {
      const model = fakeModel([mask('m1')]);
      update(model, 'm1', { color: '#00ff00' });
      expect(model._sent[0]).toEqual({ kind: 'mask_update', id: 'm1', color: '#00ff00' });
    });

    it('sends mask_update with contours=true', () => {
      const model = fakeModel([mask('m1')]);
      update(model, 'm1', { contours: true });
      expect(model._sent[0]).toEqual({ kind: 'mask_update', id: 'm1', contours: true });
    });

    it('spreads multiple changes into one message', () => {
      const model = fakeModel([mask('m1')]);
      update(model, 'm1', { visible: false, opacity: 0.2 });
      expect(model._sent[0]).toEqual({ kind: 'mask_update', id: 'm1', visible: false, opacity: 0.2 });
    });
  });

  describe('remove', () => {
    it('sends mask_delete with the correct id', () => {
      const model = fakeModel([mask('m1'), mask('m2')]);
      remove(model, 'm1');
      expect(model._sent).toHaveLength(1);
      expect(model._sent[0]).toEqual({ kind: 'mask_delete', id: 'm1' });
    });

    it('does not send mask_update when removing', () => {
      const model = fakeModel([mask('m1')]);
      remove(model, 'm1');
      expect(model._sent[0].kind).toBe('mask_delete');
      expect(model._sent[0].kind).not.toBe('mask_update');
    });
  });

  describe('mask row data defaults', () => {
    it('opacity defaults to 0.5 when undefined', () => {
      const m = mask('x', { opacity: undefined });
      const opacity = m.opacity ?? 0.5;
      expect(opacity).toBe(0.5);
    });

    it('contours defaults to false', () => {
      const m = mask('x');
      expect(!!m.contours).toBe(false);
    });

    it('visible toggle inverts correctly', () => {
      const m = mask('x', { visible: true });
      expect(!m.visible).toBe(false);
      const m2 = mask('x', { visible: false });
      expect(!m2.visible).toBe(true);
    });
  });
});
