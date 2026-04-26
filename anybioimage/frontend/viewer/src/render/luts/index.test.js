import { describe, it, expect } from 'vitest';
import { listLuts } from './index.js';

describe('LUT registry', () => {
  it('lists Viv built-in colormaps', () => {
    const names = listLuts();
    expect(names).toContain('viridis');
    expect(names).toContain('magma');
    expect(names.length).toBeGreaterThan(5);
  });
});
