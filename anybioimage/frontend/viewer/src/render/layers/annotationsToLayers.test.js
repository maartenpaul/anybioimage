import { describe, it, expect, vi } from 'vitest';

// Stub the deck.gl layer constructors so we can assert props without loading WebGL.
vi.mock('@deck.gl/layers', () => {
  class StubLayer {
    constructor(props) { this.props = props; this.type = this.constructor.name; }
  }
  class PolygonLayer extends StubLayer {}
  class ScatterplotLayer extends StubLayer {}
  return { PolygonLayer, ScatterplotLayer };
});

import { annotationsToLayers } from './annotationsToLayers.js';

function rect(id, geom, extra = {}) {
  return { id, kind: 'rect', geometry: geom, color: '#ff0000',
           visible: true, t: 0, z: 0, metadata: {}, ...extra };
}
function poly(id, geom, extra = {}) {
  return { id, kind: 'polygon', geometry: geom, color: '#00ff00',
           visible: true, t: 0, z: 0, metadata: {}, ...extra };
}
function point(id, geom, extra = {}) {
  return { id, kind: 'point', geometry: geom, color: '#0066ff',
           visible: true, t: 0, z: 0, metadata: {}, ...extra };
}

describe('annotationsToLayers', () => {
  it('returns empty array when no annotations', () => {
    const out = annotationsToLayers({ annotations: [], currentT: 0, currentZ: 0 });
    expect(out).toEqual([]);
  });

  it('produces one PolygonLayer and one ScatterplotLayer when all kinds present', () => {
    const layers = annotationsToLayers({
      annotations: [
        rect('r1', [0, 0, 10, 10]),
        poly('p1', [[0,0],[5,0],[5,5]]),
        point('pt1', [3, 3]),
      ],
      currentT: 0, currentZ: 0,
    });
    expect(layers).toHaveLength(2);
    expect(layers[0].type).toBe('PolygonLayer');
    expect(layers[1].type).toBe('ScatterplotLayer');
  });

  it('rects are expanded to 4-point polygons', () => {
    const [polygonLayer] = annotationsToLayers({
      annotations: [rect('r1', [2, 3, 6, 8])],
      currentT: 0, currentZ: 0,
    });
    const [first] = polygonLayer.props.data;
    expect(first.polygon).toEqual([[2,3],[6,3],[6,8],[2,8]]);
  });

  it('filters by current T/Z', () => {
    const layers = annotationsToLayers({
      annotations: [
        rect('r1', [0,0,1,1], { t: 0, z: 0 }),
        rect('r2', [2,2,3,3], { t: 1, z: 0 }),
        rect('r3', [4,4,5,5], { t: 0, z: 1 }),
      ],
      currentT: 0, currentZ: 0,
    });
    expect(layers[0].props.data).toHaveLength(1);
    expect(layers[0].props.data[0].id).toBe('r1');
  });

  it('skips invisible annotations', () => {
    const layers = annotationsToLayers({
      annotations: [
        rect('r1', [0,0,1,1]),
        rect('r2', [2,2,3,3], { visible: false }),
      ],
      currentT: 0, currentZ: 0,
    });
    expect(layers[0].props.data).toHaveLength(1);
  });

  it('selected annotation gets thicker stroke width', () => {
    const layers = annotationsToLayers({
      annotations: [
        rect('r1', [0,0,1,1]),
        rect('r2', [2,2,3,3]),
      ],
      currentT: 0, currentZ: 0, selectedId: 'r2',
    });
    const getLineWidth = layers[0].props.getLineWidth;
    // Layer passes the data-object back; check both cases.
    expect(getLineWidth({ id: 'r1' })).toBe(1);
    expect(getLineWidth({ id: 'r2' })).toBe(3);
  });

  it('hex color strings are parsed into [r, g, b, a] with full alpha', () => {
    const layers = annotationsToLayers({
      annotations: [rect('r1', [0,0,1,1], { color: '#ff8000' })],
      currentT: 0, currentZ: 0,
    });
    const getLineColor = layers[0].props.getLineColor;
    expect(getLineColor({ id: 'r1' })).toEqual([255, 128, 0, 255]);
  });
});
