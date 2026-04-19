import { describe, it, expect } from 'vitest';
import { buildImageLayerProps } from './buildImageLayer.js';

describe('buildImageLayerProps', () => {
  const sources = [{ shape: [1, 3, 1, 2048, 2048], labels: ['t','c','z','y','x'] }];
  const channels = [
    { index: 0, visible: true, color_kind: 'solid', color: '#ff0000',
      data_min: 0, data_max: 65535, min: 0.1, max: 0.9 },
    { index: 1, visible: false, color_kind: 'solid', color: '#00ff00',
      data_min: 0, data_max: 65535, min: 0, max: 1 },
    { index: 2, visible: true, color_kind: 'lut', lut: 'viridis',
      data_min: 0, data_max: 65535, min: 0, max: 1 },
  ];

  it('maps visible channels to selections/colors/contrastLimits', () => {
    const props = buildImageLayerProps({
      sources, channels, currentT: 2, currentZ: 0, displayMode: 'composite',
    });
    expect(props.selections).toEqual([
      { t: 2, c: 0, z: 0 },
      { t: 2, c: 2, z: 0 },
    ]);
    expect(props.contrastLimits[0]).toEqual([6553.5, 58981.5]);
    expect(props.channelsVisible).toEqual([true, true]);
  });

  it('single mode keeps only the active channel', () => {
    const props = buildImageLayerProps({
      sources, channels, currentT: 0, currentZ: 0, displayMode: 'single', activeChannel: 2,
    });
    expect(props.selections).toEqual([{ t: 0, c: 2, z: 0 }]);
  });

  it('clamps to 6 channels and sets exceeded flag', () => {
    const many = Array.from({ length: 8 }, (_, i) => ({
      index: i, visible: true, color_kind: 'solid', color: '#ffffff',
      data_min: 0, data_max: 255, min: 0, max: 1,
    }));
    const props = buildImageLayerProps({
      sources, channels: many, currentT: 0, currentZ: 0, displayMode: 'composite',
    });
    expect(props.selections.length).toBe(6);
    expect(props.exceeded).toBe(true);
  });
});
