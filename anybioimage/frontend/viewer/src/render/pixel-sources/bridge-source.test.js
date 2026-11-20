import { describe, it, expect } from 'vitest';
import { openBridge, pickTileSize, cacheSizePerLevel } from './bridge-source.js';

const LABELS = ['t', 'c', 'z', 'y', 'x'];

function mockModel() {
  return { send: () => {}, on: () => {}, off: () => {} };
}

describe('pickTileSize', () => {
  it('uses square power-of-two yx chunks within [256, 1024]', () => {
    expect(pickTileSize([10, 16, 512, 512], ['t', 'z', 'y', 'x'])).toBe(512);
    expect(pickTileSize([1, 1, 1, 256, 256], LABELS)).toBe(256);
    expect(pickTileSize([1, 1, 1, 1024, 1024], LABELS)).toBe(1024);
  });
  it('falls back to 512 otherwise', () => {
    expect(pickTileSize([1, 1, 1, 32, 32], LABELS)).toBe(512);     // too small
    expect(pickTileSize([1, 1, 1, 2048, 2048], LABELS)).toBe(512); // too big
    expect(pickTileSize([1, 1, 1, 512, 256], LABELS)).toBe(512);   // not square
    expect(pickTileSize([1, 1, 1, 300, 300], LABELS)).toBe(512);   // not pow2
    expect(pickTileSize(undefined, LABELS)).toBe(512);
  });
});

describe('cacheSizePerLevel', () => {
  it('divides the total budget across levels with a floor', () => {
    expect(cacheSizePerLevel(1)).toBe(256);
    expect(cacheSizePerLevel(2)).toBe(128);
    expect(cacheSizePerLevel(16)).toBe(32);   // floor
    expect(cacheSizePerLevel(0)).toBe(256);
  });
});

describe('openBridge', () => {
  it('builds one source per level with shared tileSize/dtype/labels', () => {
    const srcs = openBridge(mockModel(), {
      mode: 'bridge', dtype: 'uint16', labels: ['t', 'z', 'y', 'x'],
      levels: [
        { shape: [10, 3, 2048, 2048], chunks: [10, 16, 512, 512] },
        { shape: [10, 3, 1024, 1024], chunks: [10, 16, 512, 512] },
      ],
    });
    expect(srcs).toHaveLength(2);
    expect(srcs[0].shape).toEqual([10, 3, 2048, 2048]);
    expect(srcs[1].shape).toEqual([10, 3, 1024, 1024]);
    expect(srcs[0].tileSize).toBe(512);
    expect(srcs[1].tileSize).toBe(512);
    expect(srcs[0].dtype).toBe('Uint16');
    expect(srcs[0].labels).toEqual(['t', 'z', 'y', 'x']);
    expect(srcs[1]._level).toBe(1);
    expect(srcs[0]._cacheSize).toBe(128);
  });
  it('throws for a source without levels', () => {
    expect(() => openBridge(mockModel(), { mode: 'bridge' })).toThrow(/no pyramid levels/);
  });
});
