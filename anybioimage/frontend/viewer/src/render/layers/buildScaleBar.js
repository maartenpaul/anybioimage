// anybioimage/frontend/viewer/src/render/layers/buildScaleBar.js
// Full implementation in Task 14. Phase-1 stub so DeckCanvas compiles.
import { CompositeLayer } from '@deck.gl/core';

class _StubScaleBarLayer extends CompositeLayer {
  renderLayers() { return []; }
}
_StubScaleBarLayer.layerName = 'ScaleBarLayer';

export function buildScaleBarLayer() {
  return new _StubScaleBarLayer({ id: 'scale-bar' });
}
