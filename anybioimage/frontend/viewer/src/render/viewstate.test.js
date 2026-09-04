import { describe, it, expect } from 'vitest';

// Mirrors the extentKey memo in VivCanvas.jsx: view state is kept across
// sources whose image extent is unchanged (HCS well/field switches) and reset
// only when the extent really differs.
function extentKey(sources) {
  if (!sources || !sources.length) return null;
  const { shape = [], labels = [] } = sources[0];
  return `${shape[labels.indexOf('y')]}x${shape[labels.indexOf('x')]}x${sources.length}`;
}

const field = (h, w, levels = 4, labels = ['c', 'y', 'x']) =>
  Array.from({ length: levels }, (_, i) => ({ shape: [5, h >> i, w >> i], labels }));

describe('extentKey', () => {
  it('is stable across well/field switches of the same size', () => {
    expect(extentKey(field(520, 696))).toBe(extentKey(field(520, 696)));
  });

  it('changes when the field size changes', () => {
    expect(extentKey(field(520, 696))).not.toBe(extentKey(field(1024, 1024)));
  });

  it('changes when the pyramid depth changes', () => {
    expect(extentKey(field(520, 696, 4))).not.toBe(extentKey(field(520, 696, 3)));
  });

  it('finds y/x through the labels, not fixed positions', () => {
    const tczyx = [{ shape: [10, 3, 2, 520, 696], labels: ['t', 'c', 'z', 'y', 'x'] }];
    expect(extentKey(tczyx)).toBe('520x696x1');
  });

  it('is null without sources', () => {
    expect(extentKey(null)).toBeNull();
    expect(extentKey([])).toBeNull();
  });
});
