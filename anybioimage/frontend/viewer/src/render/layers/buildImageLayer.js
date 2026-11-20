import { AdditiveColormapExtension, MAX_CHANNELS } from '@hms-dbmi/viv';
import { trace } from '../../util/perf.js';

// Stateless; one shared instance avoids tearing down deck.gl's GPU pipeline
// on every channel-setting change.
const ADDITIVE_COLORMAP_EXT = new AdditiveColormapExtension();

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

export function buildImageLayerProps(args) {
  return trace('buildImageLayerProps', () => _build(args));
}

function _build({
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

  // Build selections that match the actual axis labels of the source.
  // Remote OME-Zarr stores may omit the time axis (e.g. axes=['c','z','y','x']).
  // Passing { t: ... } for such a source throws "Invalid indexer key: t" inside
  // Viv's ZarrPixelSource._indexer and the layer renders nothing.
  // The AnywidgetPixelSource always has labels=['t','c','z','y','x'].
  const sourceLabels = sources?.[0]?.labels ?? ['t', 'c', 'z', 'y', 'x'];
  const hasT = sourceLabels.includes('t');
  const hasZ = sourceLabels.includes('z');
  const selections = clipped.map((ch) => {
    const sel = { c: ch.index };
    if (hasT) sel.t = currentT;
    if (hasZ) sel.z = currentZ;
    return sel;
  });
  const colors = clipped.map((ch) => hexToRgb(ch.color));
  const contrastLimits = clipped.map(contrastFor);
  const channelsVisible = clipped.map(() => true);

  const lutChannel = clipped.find((ch) => ch.color_kind === 'lut');

  // Only override Viv's default extension when we actually want a colormap.
  // Passing `extensions: undefined` overrides the default array with undefined
  // and breaks MultiscaleImageLayer initialization ("extensions is not iterable").
  const props = {
    loader: sources,
    selections,
    colors,
    contrastLimits,
    channelsVisible,
  };
  if (lutChannel) {
    props.extensions = [ADDITIVE_COLORMAP_EXT];
    props.colormap = lutChannel.lut || 'viridis';
  }
  return props;
}
