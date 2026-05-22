import { describe, it, expect } from 'vitest';
import { pickNiceMicrons } from './buildScaleBar.js';

describe('pickNiceMicrons', () => {
  it('picks a bar whose pixel width is in [60, 200]', () => {
    for (const pxPerUm of [0.1, 0.5, 1, 2, 5, 10, 40]) {
      const { microns, pixels } = pickNiceMicrons(pxPerUm);
      expect(pixels).toBeGreaterThanOrEqual(60);
      expect(pixels).toBeLessThanOrEqual(200);
      expect(microns).toBeGreaterThan(0);
    }
  });

  it('returns a "nice" value (1/2/5 × 10^n)', () => {
    const NICE = new Set(
      [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 0.1, 0.2, 0.5],
    );
    for (const pxPerUm of [0.3, 1.7, 4.4, 12.1, 33.0]) {
      const { microns } = pickNiceMicrons(pxPerUm);
      expect(NICE.has(microns)).toBe(true);
    }
  });
});
