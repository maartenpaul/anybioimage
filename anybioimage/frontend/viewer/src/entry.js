// anybioimage/frontend/viewer/src/entry.js
// Viv backend entry: build main's full Canvas2D chrome (toolbar, channel
// panel, sliders — its renderCanvas()/requestTiles() self-guard when a zarr
// URL is active), then mount the Viv WebGL canvas in the same wrapper.
// Exactly one canvas is visible at a time, switched on _zarr_source.
import chrome from './canvas2d-chrome.js'; // both files live in src/
import React from 'react';
import { createRoot } from 'react-dom/client';
import { VivCanvas } from './render/VivCanvas.jsx';

async function render({ model, el }) {
  const cleanupChrome = await chrome.render({ model, el });

  const wrapper = el.querySelector('.canvas-wrapper');
  const c2dCanvas = el.querySelector('canvas.viewer-canvas');
  if (!wrapper) {
    console.error('anybioimage viv entry: .canvas-wrapper not found; Canvas2D only');
    return cleanupChrome;
  }
  if (!wrapper.style.position) wrapper.style.position = 'relative';

  const mount = document.createElement('div');
  mount.style.cssText = 'position:absolute;inset:0;';
  wrapper.appendChild(mount);
  const root = createRoot(mount);
  root.render(React.createElement(VivCanvas, { model }));

  const syncMode = () => {
    const viv = Boolean((model.get('_zarr_source') || {}).url);
    if (c2dCanvas) c2dCanvas.style.display = viv ? 'none' : '';
    mount.style.display = viv ? '' : 'none';
  };
  model.on('change:_zarr_source', syncMode);
  syncMode();

  return () => {
    model.off('change:_zarr_source', syncMode);
    root.unmount();
    mount.remove();
    if (typeof cleanupChrome === 'function') cleanupChrome();
  };
}

export default { render };
