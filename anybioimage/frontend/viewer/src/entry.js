// anybioimage/frontend/viewer/src/entry.js
import React from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App.jsx';

async function render({ model, el }) {
  // WebGL2 gate.
  const canvas = document.createElement('canvas');
  const hasWebGL2 = !!canvas.getContext('webgl2');
  if (!hasWebGL2) {
    el.innerHTML = '<div style="padding:16px;font-family:system-ui;background:#fff4e5;border:1px solid #ffcc80;border-radius:4px;color:#7a4500">' +
      '<strong>WebGL2 required.</strong> anybioimage needs a browser with WebGL2 enabled. ' +
      'Chrome/Edge/Firefox ≥ 120 and Safari ≥ 17 support this out of the box. ' +
      'Check <code>about:gpu</code> if you see this message on a modern browser.</div>';
    return;
  }
  const root = createRoot(el);
  root.render(React.createElement(App, { model }));
  return () => root.unmount();
}

export default { render };
