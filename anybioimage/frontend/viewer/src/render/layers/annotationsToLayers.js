/**
 * Pure conversion from the unified `_annotations` traitlet to deck.gl layers
 * [spec §5]. Rectangles and polygons share a PolygonLayer; points render as
 * ScatterplotLayer.
 *
 * Filtering:
 *   - `visible === false` entries are skipped.
 *   - entries whose `t` / `z` do not match current slice are skipped
 *     (Phase 3 adds the "show all T/Z" toggle).
 *
 * Selection:
 *   - `selectedId` bumps the outline width for the matching annotation.
 */
import { PolygonLayer, ScatterplotLayer } from '@deck.gl/layers';

function hexToRgba(hex, alpha = 255) {
  const clean = (hex || '#ff0000').replace('#', '');
  const n = parseInt(clean.length === 3
    ? clean.split('').map(c => c + c).join('')
    : clean, 16);
  return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff, alpha];
}

function rectPoly(geom) {
  const [x0, y0, x1, y1] = geom;
  return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
}

export function annotationsToLayers({
  annotations = [],
  currentT = 0,
  currentZ = 0,
  selectedId = '',
}) {
  const visible = annotations.filter((a) =>
    a && a.visible !== false && (a.t ?? 0) === currentT && (a.z ?? 0) === currentZ
  );

  const polysAndRects = visible.filter((a) => a.kind === 'rect' || a.kind === 'polygon');
  const points = visible.filter((a) => a.kind === 'point');

  const out = [];

  if (polysAndRects.length) {
    const colorById = Object.fromEntries(polysAndRects.map((a) => [a.id, a.color]));
    const data = polysAndRects.map((a) => ({
      id: a.id,
      polygon: a.kind === 'rect' ? rectPoly(a.geometry) : a.geometry,
      color: a.color,
    }));
    out.push(new PolygonLayer({
      id: 'annotations-polygons',
      data,
      stroked: true,
      filled: true,
      pickable: true,
      getPolygon: (d) => d.polygon,
      getFillColor: (d) => hexToRgba(colorById[d.id] ?? d.color, 40),
      getLineColor: (d) => hexToRgba(colorById[d.id] ?? d.color, 255),
      getLineWidth: (d) => (d.id === selectedId ? 3 : 1),
      lineWidthUnits: 'pixels',
      lineWidthMinPixels: 1,
    }));
  }

  if (points.length) {
    const colorById = Object.fromEntries(points.map((a) => [a.id, a.color]));
    const data = points.map((a) => ({
      id: a.id,
      position: a.geometry,
      color: a.color,
    }));
    out.push(new ScatterplotLayer({
      id: 'annotations-points',
      data,
      pickable: true,
      radiusUnits: 'pixels',
      radiusMinPixels: 3,
      getPosition: (d) => d.position,
      getRadius: (d) => (d.id === selectedId ? 8 : 5),
      getFillColor: (d) => hexToRgba(colorById[d.id] ?? d.color, 200),
      getLineColor: [255, 255, 255, 255],
      stroked: true,
      lineWidthUnits: 'pixels',
      getLineWidth: 1,
    }));
  }

  return out;
}
