// anybioimage/frontend/viewer/src/App.jsx
import React, { useState, useCallback } from 'react';
import { Toolbar } from './chrome/Toolbar.jsx';
import { DimControls } from './chrome/DimControls.jsx';
import { StatusBar } from './chrome/StatusBar.jsx';
import { LayersPanel } from './chrome/LayersPanel/LayersPanel.jsx';
import { DeckCanvas } from './render/DeckCanvas.jsx';
import { installKeyboard } from './interaction/keyboard.js';

export function App({ model }) {
  const [panelOpen, setPanelOpen] = useState(false);
  const [hover, setHover] = useState(null);
  const onHover = useCallback(({ coordinate }) => {
    if (!coordinate) { setHover(null); return; }
    const [x, y] = coordinate;
    setHover({ x: Math.floor(x), y: Math.floor(y) });
  }, []);

  React.useEffect(() => installKeyboard(model), [model]);

  return (
    <div className="bioimage-viewer" tabIndex={0}>
      <Toolbar model={model} onToggleLayers={() => setPanelOpen((v) => !v)} panelOpen={panelOpen} />
      <DimControls model={model} />
      <div className="content-area" style={{ display: 'flex', flex: 1, minHeight: 500 }}>
        <div className="viewport-slot" style={{ position: 'relative', flex: 1, minHeight: 500, background: '#000' }}>
          <DeckCanvas model={model} onHover={onHover} />
        </div>
        {panelOpen && <LayersPanel model={model} />}
      </div>
      <StatusBar model={model} hover={hover} />
    </div>
  );
}
