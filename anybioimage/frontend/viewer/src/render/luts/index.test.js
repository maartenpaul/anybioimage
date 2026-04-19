/** @vitest-environment jsdom */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { getLutTexture, listLuts } from './index.js';

describe('LUT registry', () => {
  beforeEach(() => {
    // Mock Image decode so we can run headless.
    globalThis.Image = class {
      constructor() { this.width = 256; this.height = 1; }
      set src(_v) { queueMicrotask(() => this.onload && this.onload()); }
      decode() { return Promise.resolve(); }
    };

    // Mock canvas getContext('2d') since jsdom doesn't implement it.
    const fakeImageData = new Uint8ClampedArray(256 * 4).fill(128);
    const fakeCtx = {
      drawImage: vi.fn(),
      getImageData: vi.fn(() => ({ data: fakeImageData })),
    };
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(fakeCtx);
  });

  it('lists all shipped LUT names', () => {
    const names = listLuts();
    expect(names).toContain('viridis');
    expect(names).toContain('gray');
    expect(names).toContain('red');
    expect(names.length).toBe(15);
  });

  it('caches the same Uint8Array across repeated calls', async () => {
    const a = await getLutTexture('viridis');
    const b = await getLutTexture('viridis');
    expect(a).toBe(b); // same reference
    expect(a.length).toBe(256 * 4);
  });
});
