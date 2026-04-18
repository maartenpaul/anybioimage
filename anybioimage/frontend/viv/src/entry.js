// anybioimage/frontend/viv/src/entry.js
import React from 'react';
import { createRoot } from 'react-dom/client';
import { VivCanvas } from './VivCanvas.jsx';
import canvas2dSource from '../../shared/canvas2d.js';

let canvas2dModulePromise = null;

async function loadCanvas2dModule() {
  if (!canvas2dModulePromise) {
    const blob = new Blob([canvas2dSource], { type: 'text/javascript' });
    const url = URL.createObjectURL(blob);
    canvas2dModulePromise = import(/* @vite-ignore */ url);
  }
  return canvas2dModulePromise;
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
    const mod = await loadCanvas2dModule();
    return mod.default.render({ model, el });
  }
  return renderViv({ model, el });
}

export default { render };
