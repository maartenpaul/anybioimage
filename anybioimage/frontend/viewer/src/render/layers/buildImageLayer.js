const MAX_CHANNELS = 6;

function hexToRgb(hex) {
  const clean = (hex || '#ffffff').replace('#', '');
  const n = parseInt(clean, 16);
  return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff];
}

function contrastFor(channel) {
  const dmin = channel.data_min ?? 0;
  const dmax = channel.data_max ?? 65535;
  const span = Math.max(dmax - dmin, 1);
  return [dmin + (channel.min ?? 0) * span, dmin + (channel.max ?? 1) * span];
}

export function buildImageLayerProps({
  sources, channels, currentT, currentZ,
  displayMode = 'composite', activeChannel = 0,
}) {
  const visibleChannels = (channels || [])
    .map((ch, idx) => ({ ...ch, index: ch.index ?? idx }))
    .filter((ch) => ch.visible);

  let active = visibleChannels;
  if (displayMode === 'single') {
    const pick = visibleChannels.find((ch) => ch.index === activeChannel)
              ?? visibleChannels[0];
    active = pick ? [pick] : [];
  }

  const clipped = active.slice(0, MAX_CHANNELS);
  const exceeded = active.length > MAX_CHANNELS;

  const selections = clipped.map((ch) => ({ t: currentT, c: ch.index, z: currentZ }));
  const colors = clipped.map((ch) => hexToRgb(ch.color));
  const contrastLimits = clipped.map(contrastFor);
  const channelsVisible = clipped.map(() => true);
  const useLut = clipped.map((ch) => ch.color_kind === 'lut' ? (ch.lut || 'viridis') : null);

  return {
    loader: sources,
    selections,
    colors,
    contrastLimits,
    channelsVisible,
    useLut,           // consumed by VivLutExtension in Task 9
    exceeded,
  };
}
