// anybioimage/frontend/viv/src/entry.js
import React from 'react';
import { createRoot } from 'react-dom/client';
import { VivCanvas } from './VivCanvas.jsx';

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

async function renderViv({ model, el }) {
  const mount = document.createElement('div');
  mount.className = 'viv-root';
  el.appendChild(mount);
  const root = createRoot(mount);
  root.render(React.createElement(VivCanvas, { model }));
  return () => root.unmount();
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
