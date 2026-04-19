// anybioimage/frontend/viv/src/entry.js
import React from 'react';
import { createRoot } from 'react-dom/client';
import { getChannelStats } from '@hms-dbmi/viv';
import { VivCanvas } from './VivCanvas.jsx';
import { buildChrome } from '../../shared/chrome.js';

function renderFallbackNotice(el) {
  const notice = document.createElement('div');
  notice.style.cssText = 'padding:12px;background:#fff4e5;border:1px solid #ffcc80;border-radius:4px;color:#7a4500;font-family:system-ui,sans-serif;font-size:13px';
  notice.innerHTML = (
    '<strong>Viv backend cannot render this input.</strong> ' +
    'The Viv backend only supports OME-Zarr. For TIFF/numpy/other inputs, ' +
    'construct the viewer with <code>render_backend="canvas2d"</code> (the default).'
  );
  el.appendChild(notice);
}

async function computeAutoContrast(sources, model, channelIndex) {
  if (!sources || !sources.length) return null;
  // Smallest pyramid level = fastest sample, still representative for percentiles.
  const level = sources[sources.length - 1];
  const t = model.get('current_t') || 0;
  const z = model.get('current_z') || 0;
  const { data } = await level.getRaw({ selection: { c: channelIndex, t, z } });
  const arr = Float32Array.from(data);
  const stats = getChannelStats(arr);
  const settings = model.get('_channel_settings') || [];
  const ch = settings[channelIndex] || {};
  const dmin = ch.data_min ?? 0;
  const dmax = ch.data_max ?? 65535;
  const span = Math.max(dmax - dmin, 1);
  return [
    (stats.contrastLimits[0] - dmin) / span,
    (stats.contrastLimits[1] - dmin) / span,
  ];
}

async function renderViv({ model, el }) {
  const refs = {
    reset: { fn: null },
    sources: { current: null },
  };

  const { viewportEl, dispose: disposeChrome } = buildChrome({ model, el }, {
    onReset: () => { if (refs.reset.fn) refs.reset.fn(); },
    onAutoContrast: (idx) => computeAutoContrast(refs.sources.current, model, idx),
  });

  const root = createRoot(viewportEl);
  root.render(React.createElement(VivCanvas, {
    model,
    resetViewRef: refs.reset,
    sourcesRef: refs.sources,
  }));
  return () => {
    root.unmount();
    disposeChrome();
  };
}

async function render({ model, el }) {
  const mode = model.get('_viv_mode') || 'viv';
  if (mode === 'canvas2d-fallback') {
    renderFallbackNotice(el);
    return;
  }
  return renderViv({ model, el });
}

export default { render };
