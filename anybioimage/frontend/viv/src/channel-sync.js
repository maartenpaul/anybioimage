// anybioimage/frontend/viv/src/channel-sync.js
const MAX_CHANNELS = 6;

function hexToRgb(hex) {
  const clean = (hex || '#ffffff').replace('#', '');
  const n = parseInt(clean, 16);
  return [(n >> 16) & 0xff, (n >> 8) & 0xff, n & 0xff];
}

export function channelSettingsToVivProps(channelSettings) {
  const visible = channelSettingsVisible(channelSettings);
  const active = visible.slice(0, MAX_CHANNELS);

  const selections = active.map((entry) => ({
    c: entry.index,
    t: 0,
    z: 0,
  }));
  const colors = active.map((entry) => hexToRgb(entry.color));
  const contrastLimits = active.map((entry) => {
    const dmin = entry.data_min ?? 0;
    const dmax = entry.data_max ?? 65535;
    const span = Math.max(dmax - dmin, 1);
    return [dmin + entry.min * span, dmin + entry.max * span];
  });
  const channelsVisible = active.map(() => true);
  return { selections, colors, contrastLimits, channelsVisible, exceeded: visible.length > MAX_CHANNELS };
}

export function channelSettingsVisible(channelSettings) {
  return (channelSettings || [])
    .map((ch, index) => ({ ...ch, index }))
    .filter((ch) => ch.visible);
}

export function withTimeAndZ(selections, t, z) {
  return selections.map((s) => ({ ...s, t, z }));
}
