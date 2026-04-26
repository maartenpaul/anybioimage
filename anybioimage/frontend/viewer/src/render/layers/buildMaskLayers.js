/** buildMaskLayers — one `BitmapLayer` per visible mask whose bitmap has
 *  arrived from Python via MaskSourceBridge. [spec §3] */
import { BitmapLayer } from '@deck.gl/layers';

export function buildMaskLayers({ masks = [], bridge }) {
  const out = [];
  for (const m of masks) {
    if (!m || m.visible === false) continue;
    const entry = bridge?.get(m.id);
    if (!entry || !entry.bitmap) continue;
    out.push(new BitmapLayer({
      id: `mask-${m.id}`,
      image: entry.bitmap,
      bounds: [0, 0, entry.width, entry.height],
      opacity: m.opacity ?? 0.5,
      pickable: false,
    }));
  }
  return out;
}
