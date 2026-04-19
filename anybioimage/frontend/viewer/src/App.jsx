// anybioimage/frontend/viewer/src/App.jsx
import React, { useState, useRef, useMemo, useEffect } from 'react';
import { Toolbar } from './chrome/Toolbar.jsx';
import { DimControls } from './chrome/DimControls.jsx';
import { StatusBar } from './chrome/StatusBar.jsx';
import { LayersPanel } from './chrome/LayersPanel/LayersPanel.jsx';
import { DeckCanvas } from './render/DeckCanvas.jsx';
import { installKeyboard } from './interaction/keyboard.js';
import { makeHoverHandler } from './render/onHoverPixelInfo.js';

export function App({ model }) {
  const [panelOpen, setPanelOpen] = useState(false);
  const [hover, setHover] = useState(null);
  const sourcesRef = useRef(null);
  const selectionsRef = useRef(null);
  const deckRef = useRef(null);

  const onHover = useMemo(
    () => makeHoverHandler({
      getSources: () => sourcesRef.current,
      getSelections: () => selectionsRef.current,
      setHover,
    }),
    []);

  useEffect(() => installKeyboard(model), [model]);

  return (
    <div className="bioimage-viewer" tabIndex={0}>
      <Toolbar model={model} onToggleLayers={() => setPanelOpen((v) => !v)} panelOpen={panelOpen} />
      <DimControls model={model} />
      <div className="content-area" style={{ display: 'flex', flex: 1, minHeight: 500 }}>
        <div className="viewport-slot" style={{ position: 'relative', flex: 1, minHeight: 500, background: '#000' }}>
          <DeckCanvas model={model} onHover={onHover}
                      deckRef={deckRef}
                      sourcesRef={sourcesRef}
                      selectionsRef={selectionsRef} />
        </div>
        {panelOpen && <LayersPanel model={model} />}
      </div>
      <StatusBar model={model} hover={hover} />
    </div>
  );
}
