import { describe, it, expect, vi } from 'vitest';
vi.mock('@deck.gl/layers', () => {
  class BitmapLayer { constructor(p) { this.props = p; this.type = 'BitmapLayer'; } }
  return { BitmapLayer };
});
import { buildMaskLayers } from './buildMaskLayers.js';

function mask(id, extra = {}) {
  return { id, name: id, visible: true, opacity: 0.5,
           color: '#ff0000', width: 4, height: 4, ...extra };
}

describe('buildMaskLayers', () => {
  it('returns no layers when masks list is empty', () => {
    expect(buildMaskLayers({ masks: [], bridge: { get: () => null } })).toEqual([]);
  });

  it('returns one BitmapLayer per visible mask with a cached bitmap', () => {
    const fakeBitmap = {};
    const bridge = { get: (id) => id === 'm1'
      ? { width: 4, height: 4, bitmap: fakeBitmap } : null };
    const layers = buildMaskLayers({ masks: [mask('m1')], bridge });
    expect(layers).toHaveLength(1);
    expect(layers[0].props.image).toBe(fakeBitmap);
    expect(layers[0].props.bounds).toEqual([0, 0, 4, 4]);
    expect(layers[0].props.opacity).toBe(0.5);
  });

  it('skips invisible masks', () => {
    const bridge = { get: () => ({ width: 4, height: 4, bitmap: {} }) };
    const layers = buildMaskLayers({
      masks: [mask('m1', { visible: false }), mask('m2')], bridge,
    });
    expect(layers).toHaveLength(1);
    expect(layers[0].props.id).toBe('mask-m2');
  });

  it('skips masks whose bitmap is not yet loaded', () => {
    const bridge = { get: () => null };
    expect(buildMaskLayers({ masks: [mask('m1')], bridge })).toEqual([]);
  });
});
