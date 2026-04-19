// anybioimage/frontend/viewer/src/render/layers/buildScaleBar.js
import { CompositeLayer } from '@deck.gl/core';
import { SolidPolygonLayer, TextLayer } from '@deck.gl/layers';

const STEPS = [1, 2, 5];   // × 10^n

export function pickNiceMicrons(pixelsPerMicron) {
  const targetPx = 120;   // aim for 120-ish, clamped to [60, 200]
  let bestMicrons = 1;
  let bestDelta = Infinity;
  for (let exp = -3; exp <= 6; exp++) {
    for (const step of STEPS) {
      const microns = step * Math.pow(10, exp);
      const px = microns * pixelsPerMicron;
      if (px < 60 || px > 200) continue;
      const delta = Math.abs(px - targetPx);
      if (delta < bestDelta) { bestDelta = delta; bestMicrons = microns; }
    }
  }
  return { microns: bestMicrons, pixels: bestMicrons * pixelsPerMicron };
}

class ScaleBarLayer extends CompositeLayer {
  renderLayers() {
    const { pixelSizeUm, viewState, width, height } = this.props;
    if (!pixelSizeUm || !viewState) return [];
    const scale = Math.pow(2, viewState.zoom);      // px / world-unit (image px)
    const pixelsPerMicron = scale / pixelSizeUm;    // screen px / µm
    const { microns, pixels } = pickNiceMicrons(pixelsPerMicron);

    // Place the bar at bottom-left, 16 px inside.
    const margin = 16;
    const barXstart = margin;
    const barXend = margin + pixels;
    const barY = height - margin;

    // Rough world-space conversion: screen (px) → world via viewport center.
    const target = viewState.target || [0, 0, 0];
    const cx = target[0]; const cy = target[1];
    const worldPerPx = 1 / scale;
    const screenToWorld = (sx, sy) => [
      cx + (sx - width / 2) * worldPerPx,
      cy + (sy - height / 2) * worldPerPx,
    ];
    const [wx0, wy0] = screenToWorld(barXstart, barY - 2);
    const [wx1, wy1] = screenToWorld(barXend, barY);

    return [
      new SolidPolygonLayer({
        id: `${this.props.id}-rect`,
        data: [{ polygon: [[wx0, wy0], [wx1, wy0], [wx1, wy1], [wx0, wy1]] }],
        getPolygon: (d) => d.polygon,
        getFillColor: [255, 255, 255, 230],
      }),
      new TextLayer({
        id: `${this.props.id}-label`,
        data: [{ position: screenToWorld((barXstart + barXend) / 2, barY - 10) }],
        // deck.gl's default font atlas is ASCII-only; use "um" for µm.
        getText: () => microns >= 1000 ? `${microns / 1000} mm`
                      : microns < 1 ? `${microns * 1000} nm` : `${microns} um`,
        getPosition: (d) => d.position,
        getColor: [255, 255, 255, 230],
        sizeUnits: 'pixels',
        getSize: 14,
        getTextAnchor: 'middle',
        getAlignmentBaseline: 'bottom',
      }),
    ];
  }
}
ScaleBarLayer.layerName = 'ScaleBarLayer';

export function buildScaleBarLayer({ pixelSizeUm, viewState, width, height }) {
  return new ScaleBarLayer({
    id: 'scale-bar', pixelSizeUm, viewState, width, height,
  });
}
