import { describe, it, expect, vi } from 'vitest';
import { makeHoverHandler } from './onHoverPixelInfo.js';

describe('makeHoverHandler', () => {
  it('reads intensity from a fake source and fires setHover', async () => {
    const raster = new Uint16Array([10, 20, 30, 40]);
    const src = { shape: [1,1,1,2,2], labels: ['t','c','z','y','x'],
      async getRaster() { return { data: raster, width: 2, height: 2 }; } };
    const setHover = vi.fn();
    const h = makeHoverHandler({ getSources: () => [src], getSelections: () => [{t:0,c:0,z:0}], setHover });
    await h({ coordinate: [1, 1] });
    expect(setHover).toHaveBeenCalledWith({ x: 1, y: 1, intensities: [40] });
  });

  it('throttles consecutive calls', async () => {
    const setHover = vi.fn();
    const h = makeHoverHandler({ getSources: () => [], getSelections: () => [], setHover });
    await h({ coordinate: [0, 0] });
    await h({ coordinate: [0, 0] });
    // Second call at the same moment suppressed by the throttle.
    expect(setHover).toHaveBeenCalledTimes(1);
  });
});
